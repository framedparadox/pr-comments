"""Body normalization, record ids, and comment construction."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from .schema import empty_comment

_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MARKDOWN_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]+\)")
_CODE_FENCE = re.compile(r"```[\s\S]*?```")
_INLINE_CODE = re.compile(r"`([^`]+)`")
_EMPHASIS = re.compile(r"[*_~]{1,3}")
_HTML_TAG = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")


def normalize_body(text: str | None) -> str:
    if not text:
        return ""
    body = text.replace("\r\n", "\n").replace("\r", "\n")
    body = _CODE_FENCE.sub(" ", body)
    body = _MARKDOWN_IMAGE.sub(" ", body)
    body = _MARKDOWN_LINK.sub(r"\1", body)
    body = _INLINE_CODE.sub(r"\1", body)
    body = _HTML_TAG.sub(" ", body)
    body = _EMPHASIS.sub("", body)
    body = body.lower().strip()
    body = _WHITESPACE.sub(" ", body)
    return body


def dedup_key(repo: str, body_normalized: str) -> str:
    digest = hashlib.sha256(f"{repo}\n{body_normalized}".encode("utf-8")).hexdigest()[:16]
    return f"{repo}::{digest}"


def make_id(provider: str, repo: str, pr_number: int | str, kind: str, comment_id: Any) -> str:
    return f"{provider}:{repo}:pr:{pr_number}:{kind}:{comment_id}"


def isoformat(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("+00:00"):
        return text[:-6] + "Z"
    return text


def make_record(
    *,
    provider: str,
    host: str,
    repo: str,
    pr_number: int,
    pr_title: str | None,
    kind: str,
    comment_id: Any,
    thread_id: Any = None,
    author: str | None,
    author_type: str,
    created_at: Any,
    updated_at: Any = None,
    body: str | None,
    path: str | None = None,
    line: int | None = None,
    side: str | None = None,
    url: str | None = None,
    in_reply_to: Any = None,
) -> dict[str, Any]:
    record = empty_comment()
    body = body or ""
    record.update(
        {
            "id": make_id(provider, repo, pr_number, kind, comment_id),
            "provider": provider,
            "host": host,
            "repo": repo,
            "pr_number": int(pr_number),
            "pr_title": pr_title or "",
            "kind": kind,
            "thread_id": None if thread_id is None else str(thread_id),
            "author": author or "ghost",
            "author_type": author_type,
            "created_at": isoformat(created_at),
            "updated_at": isoformat(updated_at) or isoformat(created_at),
            "body": body,
            "body_normalized": normalize_body(body),
            "path": path,
            "line": line,
            "side": side,
            "url": url,
            "in_reply_to": None if in_reply_to is None else str(in_reply_to),
        }
    )
    return record


def author_type_from(login: str | None, type_name: str | None, extra: dict[str, Any] | None = None) -> str:
    extra = extra or {}
    if not login or login in {"ghost", "ghost-user", "[deleted]"}:
        return "deleted"
    type_l = (type_name or "").lower()
    if type_l == "bot" or extra.get("type") == "Bot":
        return "bot"
    if login.endswith("[bot]") or login.endswith("-bot") or "bot" in login.lower():
        if extra.get("force_user"):
            return "user"
        # GitHub Apps and Dependabot-style logins
        if login.endswith("[bot]") or type_l == "bot":
            return "bot"
    return "user"
