"""Build a self-contained HTML dashboard for reviewing extracted comments."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TEMPLATE_PATH = Path(__file__).with_name("dashboard.html")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_payload(
    *,
    host: str,
    repo: str,
    base_branch: str,
    comments: list[dict[str, Any]],
    extracted_at: str | None = None,
    pull_request_count: int | None = None,
) -> dict[str, Any]:
    authors = sorted({c.get("comment_by") or "ghost" for c in comments})
    kinds = sorted({c.get("comment_kind") for c in comments if c.get("comment_kind")})
    deleted = sum(1 for c in comments if c.get("author_type") == "deleted")
    bots = sum(1 for c in comments if c.get("author_type") == "bot")
    replies = sum(1 for c in comments if c.get("is_reply"))
    prs = sorted({int(c["pr_number"]) for c in comments if c.get("pr_number") is not None})
    pr_total = pull_request_count if pull_request_count is not None else len(prs)
    return {
        "host": host,
        "repo": repo,
        "base_branch": base_branch,
        "extracted_at": extracted_at or utc_now(),
        "stats": {
            "comments": len(comments),
            "pull_requests": pr_total,
            "authors": len(authors),
            "deleted_authors": deleted,
            "bots": bots,
            "replies": replies,
        },
        "authors": authors,
        "kinds": kinds,
        "comments": comments,
    }


def render_dashboard(payload: dict[str, Any]) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    data = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    if "__PR_COMMENTS_DATA__" not in template:
        raise SystemExit("dashboard.html is missing the __PR_COMMENTS_DATA__ placeholder")
    return template.replace("__PR_COMMENTS_DATA__", data)


def write_dashboard(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_dashboard(payload), encoding="utf-8")
