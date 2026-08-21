"""Merge comment corpus evidence into derived skill pattern libraries."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from .paths import DERIVED_SKILLS, derived_skill_dir

USER_CUSTOM = "## User customizations"
PATTERN_RE = re.compile(
    r"<!-- comment-intel:pattern:(?P<id>[^ ]+) -->\s*(?P<body>.*?)(?=(?:<!-- comment-intel:pattern:)|\Z)",
    re.DOTALL,
)
CONFIRMED_RE = re.compile(r"^- \*\*Confirmed in:\*\* (?P<val>.+)$", re.MULTILINE)
SEEN_RE = re.compile(r"^- \*\*Seen:\*\* (?P<val>\d+)", re.MULTILINE)
PROVENANCE_RE = re.compile(r"^- \*\*Provenance:\*\* (?P<val>.+)$", re.MULTILINE)

WEIGHT = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


def slug_id(category: str, subcategory: str) -> str:
    cat = re.sub(r"[^a-z0-9]+", "-", (category or "general").lower()).strip("-")
    sub = re.sub(r"[^a-z0-9]+", "-", (subcategory or "general").lower()).strip("-")
    return f"{cat}:{sub}"


def _split_custom(text: str) -> tuple[str, str]:
    if USER_CUSTOM in text:
        head, tail = text.split(USER_CUSTOM, 1)
        return head.rstrip() + "\n", USER_CUSTOM + tail
    return text.rstrip() + "\n", f"{USER_CUSTOM}\n\n"


def _pr_refs(item: dict[str, Any]) -> list[str]:
    refs = []
    for occ in item.get("occurrences") or []:
        if occ.get("pr_number") is not None:
            refs.append(f"#{int(occ['pr_number'])}")
    # preserve order, unique
    seen: set[str] = set()
    out = []
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            out.append(ref)
    return out


def _rule_text(item: dict[str, Any]) -> str:
    body = " ".join((item.get("body") or "").split())
    cat = item.get("category")
    sub = item.get("subcategory")
    if cat == "security":
        return f"Treat {sub} findings as merge-blocking until disproven. Typical signal: {body[:180]}"
    if cat == "correctness":
        return f"Reject changes that reintroduce {sub} issues. Typical signal: {body[:180]}"
    if cat == "testing":
        return f"Require tests when {sub} comes up in review. Typical signal: {body[:180]}"
    return f"Watch for recurring {cat}/{sub} feedback. Typical signal: {body[:180]}"


def _anti_pattern(item: dict[str, Any]) -> str:
    return (item.get("body") or "").strip().split("\n")[0][:220]


def render_pattern(pattern_id: str, members: list[dict[str, Any]]) -> str:
    members = sorted(members, key=lambda m: WEIGHT.get(m.get("priority") or "P3", 9))
    head = members[0]
    prs: list[str] = []
    for item in members:
        prs.extend(_pr_refs(item))
    # unique prs
    uniq_prs = list(dict.fromkeys(prs))
    provenance = head.get("provenance") or {}
    repo = provenance.get("repo") or ""
    host = provenance.get("host") or ""
    loc = f"{host}/{repo}" if host and repo else repo
    examples = []
    for item in members[:3]:
        clip = " ".join((item.get("body") or "").split())[:160]
        if clip:
            examples.append(f"  - {clip}")
    example_block = "\n".join(examples) if examples else "  - _(none)_"
    return "\n".join(
        [
            f"<!-- comment-intel:pattern:{pattern_id} -->",
            f"### {head.get('category')}: {head.get('subcategory')}",
            f"- **Category:** {head.get('category')}",
            f"- **Priority:** {head.get('priority')}",
            f"- **Actionable:** {'yes' if head.get('actionable') else 'no'}",
            f"- **Rule:** {_rule_text(head)}",
            f"- **Anti-pattern:** {_anti_pattern(head)}",
            f"- **Examples:**",
            example_block,
            f"- **Provenance:** {loc} {', '.join(uniq_prs[:8])}".rstrip(),
            f"- **Confirmed in:** {', '.join(uniq_prs) if uniq_prs else '—'}",
            f"- **Seen:** {sum(int(m.get('seen_count') or 1) for m in members)}",
            "",
        ]
    )


def parse_patterns(text: str) -> dict[str, str]:
    found = {}
    for match in PATTERN_RE.finditer(text):
        found[match.group("id")] = match.group(0).rstrip() + "\n"
    return found


def merge_pattern_block(existing: str, incoming_members: list[dict[str, Any]]) -> str:
    extra_prs = []
    extra_seen = 0
    for item in incoming_members:
        extra_prs.extend(_pr_refs(item))
        extra_seen += int(item.get("seen_count") or 1)
    extra_prs = list(dict.fromkeys(extra_prs))

    def add_refs(match: re.Match[str]) -> str:
        current = [p.strip() for p in match.group("val").split(",") if p.strip() and p.strip() != "—"]
        merged = list(dict.fromkeys(current + extra_prs))
        return f"- **Confirmed in:** {', '.join(merged) if merged else '—'}"

    updated = CONFIRMED_RE.sub(add_refs, existing, count=1)
    seen_match = SEEN_RE.search(updated)
    if seen_match:
        current = int(seen_match.group("val"))
        updated = SEEN_RE.sub(f"- **Seen:** {max(current, extra_seen)}", updated, count=1)
    return updated if updated.endswith("\n") else updated + "\n"


def group_for_patterns(uniques: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in uniques:
        if not item.get("actionable") and item.get("priority") in {"P2", "P3"}:
            # keep P0/P1 even if not flagged actionable
            if item.get("priority") not in {"P0", "P1"}:
                continue
        if item.get("category") in {"clarification"} and item.get("priority") in {"P2", "P3"}:
            continue
        groups[slug_id(item.get("category") or "general", item.get("subcategory") or "general")].append(item)
    return groups


def merge_patterns_markdown(existing: str, uniques: list[dict[str, Any]]) -> tuple[str, int]:
    header, custom = _split_custom(existing if existing.strip() else _default_patterns())
    # Keep the intro (everything before the first pattern comment or User customizations)
    intro_end = header.find("<!-- comment-intel:pattern:")
    intro = header if intro_end == -1 else header[:intro_end]
    if "## Patterns" not in intro:
        intro = intro.rstrip() + "\n\n## Patterns\n\n"
    existing_patterns = parse_patterns(header)
    groups = group_for_patterns(uniques)
    changed = 0
    for pattern_id, members in sorted(groups.items()):
        if pattern_id in existing_patterns:
            before = existing_patterns[pattern_id]
            after = merge_pattern_block(before, members)
            if after != before:
                existing_patterns[pattern_id] = after
                changed += 1
        else:
            existing_patterns[pattern_id] = render_pattern(pattern_id, members)
            changed += 1
    body = intro.rstrip() + "\n\n" + "\n".join(existing_patterns[k] for k in sorted(existing_patterns))
    return body.rstrip() + "\n\n" + custom.lstrip() + ("\n" if not custom.endswith("\n") else ""), changed


def _default_patterns() -> str:
    return (
        "# Pattern library\n\n"
        "This file is maintained by `generate-skills`. New evidence is merged into existing "
        "pattern ids; the section below is never replaced wholesale.\n\n"
        "## Patterns\n\n"
        f"{USER_CUSTOM}\n\n"
    )


def preserve_user_customizations(original: str, replacement: str) -> str:
    _, custom = _split_custom(original)
    head, _ = _split_custom(replacement)
    return head.rstrip() + "\n\n" + custom.lstrip() + ("\n" if not custom.endswith("\n") else "")


def update_derived_skills(git_root: Path, uniques: list[dict[str, Any]]) -> dict[str, int]:
    stats = {}
    for name in DERIVED_SKILLS:
        skill_dir = derived_skill_dir(git_root, name)
        patterns_path = skill_dir / "references" / "patterns.md"
        skill_path = skill_dir / "SKILL.md"
        existing = patterns_path.read_text(encoding="utf-8") if patterns_path.is_file() else _default_patterns()
        merged, changed = merge_patterns_markdown(existing, uniques)
        patterns_path.parent.mkdir(parents=True, exist_ok=True)
        if merged != existing:
            patterns_path.write_text(merged, encoding="utf-8")
        if skill_path.is_file():
            original = skill_path.read_text(encoding="utf-8")
            # Do not rewrite workflow text; only guarantee customizations survive if a template is applied later.
            # Touch a generated marker after frontmatter when missing.
            if "comment-intel:generated" not in original:
                updated = original.replace("\n---\n", "\n---\n\n<!-- comment-intel:generated:true -->\n", 1)
                skill_path.write_text(updated, encoding="utf-8")
        stats[name] = changed
    return stats
