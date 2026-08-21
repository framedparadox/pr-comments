"""Local JSON / JSONL dump adapter for air-gapped or unsupported forges."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..normalize import make_record, normalize_body
from ..timeutil import is_after
from . import Adapter, IngestRequest, PullRequest, register
from .github import records_from_pr_bundle
from .gitlab import records_from_discussions


def _load(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    return json.loads(text)


def _already_normalized(item: dict[str, Any]) -> bool:
    return all(k in item for k in ("id", "provider", "body", "pr_number", "created_at"))


def records_from_dump(identity_host: str, identity_repo: str, payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and "comments" in payload:
        payload = payload["comments"]
    if not isinstance(payload, list):
        raise SystemExit("local JSON dump must be a list or an object with a comments array")
    out: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        if _already_normalized(item):
            record = dict(item)
            record["body_normalized"] = record.get("body_normalized") or normalize_body(record.get("body"))
            out.append(record)
            continue
        if "notes" in item and ("id" in item):
            pr = PullRequest(
                number=int(item.get("iid") or item.get("pr_number") or 0),
                title=item.get("title") or "",
                state=item.get("state") or "",
                url=item.get("web_url"),
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
            )
            out.extend(records_from_discussions(identity_host, identity_repo, pr, [item]))
            continue
        if item.get("html_url") and ("pull_request_url" in item or "diff_hunk" in item or "path" in item):
            pr_number = int(item.get("pull_request_number") or item.get("pr_number") or 0)
            pr = PullRequest(number=pr_number, title="", state="", url=None, created_at=None, updated_at=None)
            out.extend(records_from_pr_bundle(identity_host, identity_repo, pr, [], [item], []))
            continue
        if item.get("body") is not None:
            pr_number = int(item.get("pr_number") or item.get("number") or 0)
            out.append(
                make_record(
                    provider=item.get("provider") or "local",
                    host=item.get("host") or identity_host,
                    repo=item.get("repo") or identity_repo,
                    pr_number=pr_number,
                    pr_title=item.get("pr_title") or "",
                    kind=item.get("kind") or "note",
                    comment_id=item.get("id") or item.get("comment_id") or len(out),
                    thread_id=item.get("thread_id"),
                    author=(item.get("author") or {}).get("login") if isinstance(item.get("author"), dict) else item.get("author"),
                    author_type=item.get("author_type") or "user",
                    created_at=item.get("created_at"),
                    updated_at=item.get("updated_at"),
                    body=item.get("body") or "",
                    path=item.get("path"),
                    line=item.get("line"),
                    url=item.get("url"),
                    in_reply_to=item.get("in_reply_to"),
                )
            )
    return out


class LocalJsonAdapter(Adapter):
    name = "local"

    def fetch(self, request: IngestRequest) -> list[dict[str, Any]]:
        if not request.local_json:
            raise SystemExit("local adapter requires --local-json PATH")
        path = Path(request.local_json)
        if not path.is_file():
            raise SystemExit(f"local JSON dump not found: {path}")
        ident = request.identity
        records = records_from_dump(ident.host, ident.slug, _load(path))
        if request.cutoff:
            records = [r for r in records if is_after(r.get("created_at"), request.cutoff)]
        return records


register(LocalJsonAdapter())
