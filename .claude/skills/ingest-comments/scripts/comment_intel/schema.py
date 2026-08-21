"""Normalized comment and unique-comment record shapes."""

from __future__ import annotations

from typing import Any, Iterable

PROVIDERS = ("github", "gitlab", "bitbucket", "gitea", "local")

KINDS = (
    "issue_comment",
    "review_comment",
    "review_summary",
    "note",
    "diff_note",
)

AUTHOR_TYPES = ("user", "bot", "deleted")

CATEGORIES = (
    "correctness",
    "security",
    "performance",
    "maintainability",
    "architecture",
    "testing",
    "documentation",
    "style",
    "UX",
    "workflow",
    "clarification",
)

PRIORITIES = ("P0", "P1", "P2", "P3")

COMMENT_FIELDS = (
    "id",
    "provider",
    "host",
    "repo",
    "pr_number",
    "pr_title",
    "kind",
    "thread_id",
    "author",
    "author_type",
    "created_at",
    "updated_at",
    "body",
    "body_normalized",
    "path",
    "line",
    "side",
    "url",
    "in_reply_to",
)

UNIQUE_FIELDS = (
    "dedup_key",
    "body",
    "body_normalized",
    "category",
    "subcategory",
    "tags",
    "priority",
    "actionable",
    "confidence",
    "seen_count",
    "first_seen",
    "last_seen",
    "occurrences",
    "provenance",
)


def empty_comment() -> dict[str, Any]:
    return {field: None for field in COMMENT_FIELDS}


def validate_comment(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("id", "provider", "host", "repo", "pr_number", "kind", "created_at", "body"):
        if record.get(field) in (None, ""):
            errors.append(f"missing {field}")
    if record.get("provider") not in PROVIDERS:
        errors.append(f"unknown provider: {record.get('provider')}")
    if record.get("kind") not in KINDS:
        errors.append(f"unknown kind: {record.get('kind')}")
    return errors


def occurrence_from_comment(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("id"),
        "pr_number": record.get("pr_number"),
        "pr_title": record.get("pr_title"),
        "author": record.get("author"),
        "author_type": record.get("author_type"),
        "created_at": record.get("created_at"),
        "path": record.get("path"),
        "line": record.get("line"),
        "url": record.get("url"),
        "kind": record.get("kind"),
    }


def iter_required(records: Iterable[dict[str, Any]], fields: tuple[str, ...]) -> None:
    for record in records:
        for field in fields:
            record.setdefault(field, None)
