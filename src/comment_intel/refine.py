"""Deduplicate comments into a classified unique corpus."""

from __future__ import annotations

from typing import Any

from .classify import classify_comment
from .normalize import dedup_key
from .schema import occurrence_from_comment
from .timeutil import parse_dt


def merge_uniques(
    existing: list[dict[str, Any]],
    comments: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (all_uniques, newly_created_or_updated_this_pass).

    New dedup keys are classified. Existing keys keep their category/priority
    and only gain occurrences / seen_count.
    """
    by_key: dict[str, dict[str, Any]] = {}
    for item in existing:
        key = item.get("dedup_key")
        if key:
            by_key[key] = item

    known_occurrence_ids: dict[str, set[str]] = {
        key: {str(occ.get("id")) for occ in (item.get("occurrences") or []) if occ.get("id")}
        for key, item in by_key.items()
    }

    changed: list[dict[str, Any]] = []
    for comment in comments:
        if not (comment.get("body") or "").strip():
            continue
        repo = comment.get("repo") or ""
        key = comment.get("dedup_key") or dedup_key(repo, comment.get("body_normalized") or "")
        occ = occurrence_from_comment(comment)
        occ_id = str(occ.get("id") or "")
        if key in by_key:
            item = by_key[key]
            seen_ids = known_occurrence_ids.setdefault(key, set())
            if occ_id and occ_id in seen_ids:
                continue
            if occ_id:
                seen_ids.add(occ_id)
            item.setdefault("occurrences", []).append(occ)
            item["seen_count"] = len(item["occurrences"])
            if parse_dt(comment.get("created_at")) and (
                item.get("last_seen") is None
                or parse_dt(comment.get("created_at")) > parse_dt(item.get("last_seen"))
            ):
                item["last_seen"] = comment.get("created_at")
            if parse_dt(comment.get("created_at")) and (
                item.get("first_seen") is None
                or parse_dt(comment.get("created_at")) < parse_dt(item.get("first_seen"))
            ):
                item["first_seen"] = comment.get("created_at")
            changed.append(item)
            continue

        labels = classify_comment(comment)
        item = {
            "dedup_key": key,
            "body": comment.get("body"),
            "body_normalized": comment.get("body_normalized"),
            "category": labels["category"],
            "subcategory": labels["subcategory"],
            "tags": labels["tags"],
            "priority": labels["priority"],
            "actionable": labels["actionable"],
            "confidence": labels["confidence"],
            "seen_count": 1,
            "first_seen": comment.get("created_at"),
            "last_seen": comment.get("created_at"),
            "occurrences": [occ],
            "provenance": {
                "provider": comment.get("provider"),
                "host": comment.get("host"),
                "repo": comment.get("repo"),
            },
        }
        by_key[key] = item
        known_occurrence_ids[key] = {occ_id} if occ_id else set()
        changed.append(item)

    uniques = list(by_key.values())
    uniques.sort(key=lambda u: (u.get("priority") or "P9", u.get("category") or "", u.get("last_seen") or ""), reverse=False)
    uniques.sort(key=lambda u: u.get("priority") or "P9")
    return uniques, changed
