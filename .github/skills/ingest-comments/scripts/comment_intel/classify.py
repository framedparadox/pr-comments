"""Heuristic comment classification.

The agent may override low-confidence labels. Existing unique records are never
reclassified by this module — only new dedup keys are scored.
"""

from __future__ import annotations

import re
from typing import Any

from .schema import CATEGORIES, PRIORITIES

CONVENTIONAL_LABELS = (
    "praise",
    "nitpick",
    "suggestion",
    "issue",
    "question",
    "thought",
    "todo",
    "chore",
)

_CONVENTIONAL = re.compile(
    r"^\s*(?:[:\-]\s*)?(?P<label>"
    + "|".join(CONVENTIONAL_LABELS)
    + r")(?:\s*\((?P<deco>[^)]+)\))?\s*:\s*",
    re.IGNORECASE,
)

KEYWORD_MAP: list[tuple[str, tuple[str, ...], str]] = [
    ("security", ("secret", "token", "password", "xss", "csrf", "injection", "sqli", "authz", "authorization", "cve", "rce", "path traversal", "ssrf", "credential"), "secret-or-auth"),
    ("performance", ("n+1", "n+1 query", "latency", "slow", "cache", "hot path", "timeout", "o(n^2)", "memory leak", "allocat"), "hot-path"),
    ("testing", ("unit test", "missing test", "coverage", "spec", "fixture", "flaky", "assert", "testdata"), "missing-test"),
    ("documentation", ("readme", "docs", "documentation", "typo", "comment the", "jsdoc", "docstring"), "missing-docs"),
    ("UX", ("accessibility", "a11y", "aria-", "screen reader", "usability", "copy", "placeholder", "mobile layout"), "a11y"),
    ("workflow", ("changelog", "rebase", "ci ", "github action", "pipeline", "commit message", "conventional commit"), "ci-process"),
    ("architecture", ("layer", "coupling", "bounded context", "abstraction", "circular import", "dependency direction", "hexagonal"), "boundaries"),
    ("maintainability", ("duplicat", "magic number", "dead code", "complexity", "refactor", "god class", "hard to follow"), "duplication"),
    ("style", ("nit:", "nitpick", "formatting", "whitespace", "rename to", "import order", "lint"), "formatting"),
    ("clarification", ("what does", "why is", "can you explain", "unclear", "i'm not sure", "not sure i follow", "?"), "question"),
    ("correctness", ("null check", "npe", "crash", "race", "off-by", "does not", "bug", "broken", "exception", "validate", "overflow", "undefined"), "logic-bug"),
]

PRIORITY_KEYWORDS = {
    "P0": ("p0", "critical", "severity: critical", "data loss", "rce", "production outage", "security vulnerability", "secrets in"),
    "P1": ("p1", "blocking", "must fix", "high priority", "will 500", "broken", "bug:", "issue:"),
    "P2": ("p2", "should", "suggestion", "consider ", "minor"),
    "P3": ("p3", "nit", "nitpick", "optional", "style only", "typo", "trivial"),
}

DECORATION_PRIORITY = {
    "blocking": "P1",
    "non-blocking": "P3",
    "if-minor": "P3",
}

LABEL_CATEGORY = {
    "praise": "clarification",
    "nitpick": "style",
    "suggestion": "maintainability",
    "issue": "correctness",
    "question": "clarification",
    "thought": "architecture",
    "todo": "workflow",
    "chore": "workflow",
}

LABEL_PRIORITY = {
    "praise": "P3",
    "nitpick": "P3",
    "suggestion": "P2",
    "issue": "P1",
    "question": "P2",
    "thought": "P3",
    "todo": "P2",
    "chore": "P2",
}


def _contains(text: str, needle: str) -> bool:
    if needle == "?":
        return "?" in text
    needle = needle.strip()
    if len(needle) <= 5:
        return re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", text) is not None
    return needle in text


def classify_comment(record: dict[str, Any]) -> dict[str, Any]:
    body = record.get("body") or ""
    normalized = (record.get("body_normalized") or body.lower()).strip()
    tags: list[str] = []
    category = "clarification"
    subcategory = "general"
    priority = "P2"
    confidence = "low"

    conventional = _CONVENTIONAL.match(body)
    if conventional:
        label = conventional.group("label").lower()
        deco = (conventional.group("deco") or "").lower()
        tags.append(label)
        category = LABEL_CATEGORY.get(label, category)
        priority = LABEL_PRIORITY.get(label, priority)
        subcategory = label
        confidence = "high"
        for part in [p.strip() for p in deco.split(",") if p.strip()]:
            tags.append(part)
            if part in DECORATION_PRIORITY:
                priority = DECORATION_PRIORITY[part]
                confidence = "high"

    for cat, keywords, sub in KEYWORD_MAP:
        if any(_contains(normalized, kw) for kw in keywords):
            # Conventional praise/nitpick stay unless a stronger domain match exists
            if conventional and category in {"style", "clarification"} and cat in {"security", "correctness", "performance"}:
                category = cat
                subcategory = sub
                confidence = "high"
            elif not conventional:
                category = cat
                subcategory = sub
                confidence = "medium" if confidence == "low" else confidence
            elif conventional and cat != category:
                tags.append(cat)
            else:
                subcategory = sub
            if cat == "security":
                tags.append("security")
            break

    for level, keywords in PRIORITY_KEYWORDS.items():
        if any(_contains(normalized, kw) for kw in keywords):
            priority = level
            if confidence == "low":
                confidence = "medium"
            break

    if "security" in tags and priority not in {"P0", "P1"}:
        priority = "P1"

    author_type = record.get("author_type")
    if author_type == "bot":
        tags.append("bot")
        if category == "clarification":
            category = "workflow"
            subcategory = "bot-report"
            priority = "P3"
            if confidence == "low":
                confidence = "medium"

    actionable = True
    if "praise" in tags:
        actionable = False
    if category == "clarification" and subcategory in {"question", "general"} and priority in {"P2", "P3"}:
        actionable = "?" in body or "please" in normalized
    if author_type == "bot" and subcategory == "bot-report" and not any(
        k in normalized for k in ("fail", "error", "must")
    ):
        actionable = False

    if category not in CATEGORIES:
        category = "clarification"
    if priority not in PRIORITIES:
        priority = "P2"

    seen: set[str] = set()
    uniq_tags = []
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            uniq_tags.append(tag)

    return {
        "category": category,
        "subcategory": subcategory,
        "tags": uniq_tags,
        "priority": priority,
        "actionable": bool(actionable),
        "confidence": confidence,
    }
