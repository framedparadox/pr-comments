"""Timezone-aware timestamp helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(str(value)[: len("YYYY-MM-DDTHH:MM:SS") if "T" in fmt else 10], fmt)
                    break
                except ValueError:
                    dt = None
            if dt is None:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_iso() -> str:
    return to_iso(datetime.now(timezone.utc))  # type: ignore[arg-type]


def is_after(value: Any, cutoff: Any) -> bool:
    left = parse_dt(value)
    right = parse_dt(cutoff)
    if left is None or right is None:
        return True
    return left > right


def max_iso(values: list[Any]) -> str | None:
    parsed = [parse_dt(v) for v in values]
    parsed = [p for p in parsed if p is not None]
    if not parsed:
        return None
    return to_iso(max(parsed))
