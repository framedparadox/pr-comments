"""Checkpoint and report cutoff handling."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .timeutil import now_iso

CUTOFF_RE = re.compile(r"comment-intel:cutoff:([0-9T:\-]+Z)")
REPO_RE = re.compile(r"comment-intel:repo:([^\s]+)")
BASE_RE = re.compile(r"comment-intel:base:([^\s]+)")

CHECKPOINT_VERSION = 1


def default_checkpoint(identity: dict[str, Any] | None = None) -> dict[str, Any]:
    identity = identity or {}
    return {
        "schema_version": CHECKPOINT_VERSION,
        "repo": identity.get("repo"),
        "host": identity.get("host"),
        "owner": identity.get("owner"),
        "provider": identity.get("provider"),
        "base_branch": identity.get("base_branch"),
        "last_run_at": None,
        "cutoff": None,
        "last_pr_number": None,
        "comment_count": 0,
        "unique_count": 0,
        "last_generated_at": None,
    }


def read_checkpoint(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_checkpoint(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(data)
    payload["schema_version"] = CHECKPOINT_VERSION
    payload["last_run_at"] = payload.get("last_run_at") or now_iso()
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_report_markers(text: str) -> dict[str, str | None]:
    cutoff = None
    match = CUTOFF_RE.search(text)
    if match:
        cutoff = match.group(1)
    repo = None
    match = REPO_RE.search(text)
    if match:
        repo = match.group(1)
    base = None
    match = BASE_RE.search(text)
    if match:
        base = match.group(1)
    return {"cutoff": cutoff, "repo": repo, "base_branch": base}


def load_cutoff(artifact_dir: Path) -> str | None:
    checkpoint = read_checkpoint(artifact_dir / "checkpoint.json")
    if checkpoint and checkpoint.get("cutoff"):
        return checkpoint["cutoff"]
    report = artifact_dir / "REPORT.md"
    if report.is_file():
        return parse_report_markers(report.read_text(encoding="utf-8")).get("cutoff")
    return None
