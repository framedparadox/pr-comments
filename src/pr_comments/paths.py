"""Locate export directories. This pack never creates per-agent skill folders."""

from __future__ import annotations

import re
from pathlib import Path

EXPORT_ROOT = "pr-comments-export"


def _clean(part: str) -> str:
    part = part.replace("/", "--")
    part = re.sub(r"[^A-Za-z0-9._-]+", "-", part)
    return part.strip("-.")[:80] or "unknown"


def repo_slug(host: str, owner: str, repo: str) -> str:
    return f"{_clean(host)}--{_clean(owner)}--{_clean(repo)}"


def default_output_dir(start: Path, host: str, owner: str, repo: str) -> Path:
    return Path(start).resolve() / EXPORT_ROOT / repo_slug(host, owner, repo)


def package_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "skills").is_dir():
            return parent
    return here.parents[1]
