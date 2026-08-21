"""Markdown knowledge-base generation."""

from __future__ import annotations

import html
import re
from collections import defaultdict
from typing import Any

from .schema import CATEGORIES, PRIORITIES
from .timeutil import now_iso

RUN_HEADING = re.compile(r"^## Run:.*$", re.MULTILINE)
USER_CUSTOM = "## User customizations"


def _esc(text: Any) -> str:
    return html.escape(str(text if text is not None else ""), quote=False).replace("\n", " ")


def _clip(text: Any, width: int = 140) -> str:
    value = " ".join(str(text or "").split())
    if len(value) <= width:
        return value
    return value[: width - 1] + "…"


def extract_run_sections(existing: str) -> list[str]:
    if not existing:
        return []
    matches = list(RUN_HEADING.finditer(existing))
    if not matches:
        return []
    sections = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else _section_end(existing, start)
        block = existing[start:end].strip()
        if block:
            sections.append(block)
    return sections


def _section_end(text: str, start: int) -> int:
    markers = [
        text.find("\n## Unique comments", start + 1),
        text.find("\n## Raw ledger", start + 1),
        text.find("\n## Per-PR", start + 1),
        text.find("\n## Per-MR", start + 1),
        text.find("\n## Checkpoint", start + 1),
    ]
    valid = [m for m in markers if m != -1]
    return min(valid) if valid else len(text)


def extract_user_customizations(existing: str) -> str:
    if not existing or USER_CUSTOM not in existing:
        return ""
    return existing.split(USER_CUSTOM, 1)[1]


def _pr_list(uniques: list[dict[str, Any]]) -> list[int]:
    numbers = set()
    for item in uniques:
        for occ in item.get("occurrences") or []:
            if occ.get("pr_number") is not None:
                numbers.add(int(occ["pr_number"]))
    return sorted(numbers)


def render_report(
    *,
    host: str,
    repo: str,
    base_branch: str,
    cutoff: str | None,
    last_pr: int | None,
    comments: list[dict[str, Any]],
    uniques: list[dict[str, Any]],
    new_uniques: list[dict[str, Any]],
    previous_markdown: str | None,
    run_at: str | None = None,
    include_run: bool = True,
) -> str:
    run_at = run_at or now_iso()
    repo_label = f"{host}/{repo}"
    previous_runs = extract_run_sections(previous_markdown or "")
    custom = extract_user_customizations(previous_markdown or "")
    new_prs = _pr_list(new_uniques)
    pr_span = ""
    if new_prs:
        pr_span = f" (PRs #{new_prs[0]}–#{new_prs[-1]})" if len(new_prs) > 1 else f" (PR #{new_prs[0]})"

    lines: list[str] = [
        f"<!-- comment-intel:cutoff:{cutoff or run_at} -->",
        f"<!-- comment-intel:repo:{repo_label} -->",
        f"<!-- comment-intel:base:{base_branch} -->",
        f"# PR/MR comment history — {repo_label}",
        "",
        "## Checkpoint",
        "",
        f"- Repository: `{repo_label}`",
        f"- Base branch: `{base_branch}`",
        f"- Last run: `{run_at}`",
        f"- Cutoff: `{cutoff or run_at}`",
        f"- Last PR/MR: `{last_pr if last_pr is not None else 'n/a'}`",
        f"- Unique comments: `{len(uniques)}`",
        f"- Ledger comments: `{len(comments)}`",
        "",
    ]
    if include_run:
        lines.append(f"## Run: {run_at} — {len(new_uniques)} new unique comments{pr_span}")
        lines.append("")
        if new_uniques:
            lines.extend(_unique_table(new_uniques))
            lines.append("")
        else:
            lines.append("No new unique comments in this run.")
            lines.append("")

    for block in previous_runs:
        if block.startswith(f"## Run: {run_at}"):
            continue
        lines.append(block)
        lines.append("")

    lines.extend(["## Unique comments", ""])
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for item in uniques:
        grouped[item.get("category") or "clarification"][item.get("priority") or "P3"].append(item)
    for category in CATEGORIES:
        if category not in grouped:
            continue
        lines.append(f"### {category}")
        lines.append("")
        for priority in PRIORITIES:
            items = grouped[category].get(priority) or []
            if not items:
                continue
            lines.append(f"#### {priority}")
            lines.append("")
            lines.extend(_unique_table(items))
            lines.append("")

    lines.extend(["## Raw ledger", ""])
    lines.extend(_ledger_table(comments))
    lines.append("")
    lines.extend(["## Per-PR / Per-MR timeline", ""])
    lines.extend(_timeline(comments))
    lines.append("")

    if custom.strip():
        lines.append(USER_CUSTOM)
        lines.append(custom if custom.startswith("\n") else "\n" + custom)
        if not lines[-1].endswith("\n"):
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _unique_table(items: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Category | Priority | Comment | Author | Date | PR | Seen |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in items:
        occs = item.get("occurrences") or []
        authors = ", ".join(sorted({str(o.get("author") or "") for o in occs if o.get("author")})) or "—"
        prs = ", ".join(f"#{n}" for n in sorted({int(o["pr_number"]) for o in occs if o.get("pr_number") is not None}))
        date = (item.get("last_seen") or "")[:10]
        lines.append(
            "| {cat} | {pri} | {body} | {authors} | {date} | {prs} | {seen} |".format(
                cat=_esc(item.get("category")),
                pri=_esc(item.get("priority")),
                body=_esc(_clip(item.get("body"))),
                authors=_esc(authors),
                date=_esc(date),
                prs=_esc(prs or "—"),
                seen=item.get("seen_count") or len(occs),
            )
        )
    return lines


def _ledger_table(comments: list[dict[str, Any]]) -> list[str]:
    ordered = sorted(comments, key=lambda c: c.get("created_at") or "", reverse=True)
    lines = [
        "| ID | Date | PR | Author | Kind | Path | Comment |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for item in ordered:
        path = item.get("path") or ""
        if item.get("line"):
            path = f"{path}:{item.get('line')}" if path else str(item.get("line"))
        lines.append(
            "| `{id}` | {date} | #{pr} | {author} | {kind} | {path} | {body} |".format(
                id=_esc(item.get("id")),
                date=_esc((item.get("created_at") or "")[:19]),
                pr=_esc(item.get("pr_number")),
                author=_esc(item.get("author")),
                kind=_esc(item.get("kind")),
                path=_esc(path or "—"),
                body=_esc(_clip(item.get("body"), 100)),
            )
        )
    if len(ordered) == 0:
        lines.append("| — | — | — | — | — | — | _empty_ |")
    return lines


def _timeline(comments: list[dict[str, Any]]) -> list[str]:
    by_pr: dict[int, list[dict[str, Any]]] = defaultdict(list)
    titles: dict[int, str] = {}
    for item in comments:
        number = int(item.get("pr_number") or 0)
        by_pr[number].append(item)
        if item.get("pr_title"):
            titles[number] = item["pr_title"]
    lines: list[str] = []
    for number in sorted(by_pr, reverse=True):
        items = sorted(by_pr[number], key=lambda c: c.get("created_at") or "")
        title = titles.get(number) or ""
        heading = f"### #{number}" + (f" — {title}" if title else "")
        lines.append(heading)
        lines.append("")
        for item in items:
            stamp = (item.get("created_at") or "")[:19]
            who = item.get("author") or "ghost"
            loc = ""
            if item.get("path"):
                loc = f" `{item['path']}"
                if item.get("line"):
                    loc += f":{item['line']}"
                loc += "`"
            lines.append(f"- `{stamp}` **@{who}** ({item.get('kind')}){loc}: {_clip(item.get('body'), 180)}")
        lines.append("")
    if not lines:
        lines.append("_No comments ingested yet._")
        lines.append("")
    return lines
