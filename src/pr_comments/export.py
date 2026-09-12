"""CSV and JSON artifact writers."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from .schema import CSV_FIELDS, JSON_EXTRA_FIELDS

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def csv_safe(value: Any) -> Any:
    """Neutralize spreadsheet formula injection without changing normal text."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    text = str(value)
    if text[:1] in FORMULA_PREFIXES:
        return "'" + text
    return text


def write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(CSV_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_safe(row.get(field)) for field in CSV_FIELDS})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(CSV_FIELDS) + list(JSON_EXTRA_FIELDS)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            record = {field: row.get(field) for field in fields}
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))
