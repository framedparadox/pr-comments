"""Comment record construction and author handling."""

from __future__ import annotations

import re
from typing import Any

from .schema import empty_row

_ISSUE_OR_PR = re.compile(r"/(?:issues|pulls)/(\d+)(?:$|[?#])")


def isoformat(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("+00:00"):
        return text[:-6] + "Z"
    return text


def number_from_url(url: str | None) -> int | None:
    if not url:
        return None
    match = _ISSUE_OR_PR.search(url)
    if match:
        return int(match.group(1))
    part = str(url).rstrip("/").rsplit("/", 1)[-1]
    if part.isdigit():
        return int(part)
    return None


def author_type_from(login: str | None, type_name: str | None, extra: dict[str, Any] | None = None) -> str:
    extra = extra or {}
    if not login or login in {"ghost", "ghost-user", "[deleted]"}:
        return "deleted"
    type_l = (type_name or extra.get("type") or "").lower()
    if type_l == "bot":
        return "bot"
    if login.endswith("[bot]"):
        return "bot"
    return "user"


def login_from_user(user: Any) -> tuple[str | None, str | None]:
    if user is None:
        return None, None
    if isinstance(user, str):
        return user, None
    return user.get("login") or user.get("name"), user.get("type")


def make_id(provider: str, repo: str, pr_number: int | str, kind: str, comment_id: Any) -> str:
    return f"{provider}:{repo}:pr:{pr_number}:{kind}:{comment_id}"


def make_row(
    *,
    provider: str,
    host: str,
    repo: str,
    pr_number: int,
    pr_title: str | None,
    pr_state: str | None,
    pr_created_at: Any,
    pr_merged_at: Any = None,
    pr_author: str | None = None,
    pr_url: str | None = None,
    pr_head_sha: str | None = None,
    merge_commit_sha: str | None = None,
    kind: str,
    native_id: Any,
    commit_id: str | None = None,
    original_commit_id: str | None = None,
    comment_date: Any,
    comment_updated_at: Any = None,
    author: str | None,
    author_type: str,
    body: str | None,
    path: str | None = None,
    line: int | None = None,
    side: str | None = None,
    url: str | None = None,
    in_reply_to: Any = None,
    thread_id: Any = None,
    diff_hunk: str | None = None,
) -> dict[str, Any]:
    row = empty_row()
    reply_to = None if in_reply_to in (None, "", 0, "0") else str(in_reply_to)
    thread = str(thread_id) if thread_id not in (None, "") else (reply_to or str(native_id))
    row.update(
        {
            "id": make_id(provider, repo, pr_number, kind, native_id),
            "provider": provider,
            "host": host,
            "repo": repo,
            "pr_number": int(pr_number),
            "pr_title": pr_title or "",
            "pr_state": (pr_state or "").lower() or None,
            "pr_created_at": isoformat(pr_created_at),
            "pr_merged_at": isoformat(pr_merged_at),
            "pr_author": pr_author or "ghost",
            "pr_url": pr_url,
            "pr_head_sha": pr_head_sha,
            "merge_commit_sha": merge_commit_sha,
            "commit_id": commit_id or "",
            "original_commit_id": original_commit_id or "",
            "comment_date": isoformat(comment_date),
            "comment_updated_at": isoformat(comment_updated_at) or isoformat(comment_date),
            "comment_by": author or "ghost",
            "author_type": author_type,
            "comment_kind": kind,
            "is_reply": bool(reply_to),
            "in_reply_to": reply_to,
            "thread_id": thread,
            "path": path,
            "line": line,
            "side": side,
            "comment": body or "",
            "comment_url": url,
            "native_id": None if native_id is None else str(native_id),
            "diff_hunk": diff_hunk,
        }
    )
    return row
