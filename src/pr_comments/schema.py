"""Normalized comment rows written to CSV, JSON, and the dashboard."""

from __future__ import annotations

from typing import Any

COMMENT_KINDS = (
    "conversation",
    "inline_review",
    "review_summary",
)

AUTHOR_TYPES = ("user", "bot", "deleted")

# Column order for comments.csv — documentation-first, not API-first.
CSV_FIELDS = (
    "repo",
    "pr_number",
    "pr_title",
    "pr_state",
    "pr_created_at",
    "pr_merged_at",
    "pr_author",
    "commit_id",
    "original_commit_id",
    "comment_date",
    "comment_updated_at",
    "comment_by",
    "author_type",
    "comment_kind",
    "is_reply",
    "in_reply_to",
    "thread_id",
    "path",
    "line",
    "side",
    "comment",
    "comment_url",
    "pr_url",
)

JSON_EXTRA_FIELDS = (
    "id",
    "provider",
    "host",
    "native_id",
    "pr_head_sha",
    "merge_commit_sha",
    "diff_hunk",
)


def empty_row() -> dict[str, Any]:
    row = {field: None for field in CSV_FIELDS}
    for field in JSON_EXTRA_FIELDS:
        row[field] = None
    return row
