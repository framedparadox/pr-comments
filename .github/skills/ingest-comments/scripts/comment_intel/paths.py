"""Artifact and skill filesystem layout."""

from __future__ import annotations

import re
from pathlib import Path

ARTIFACT_ROOT = ".comment-intelligence/repos"
CANONICAL_SKILLS = ".agents/skills"
MIRROR_SKILLS = (".claude/skills", ".github/skills")
DERIVED_SKILLS = ("code-review", "git-checkin", "commit-hooks")
PIPELINE_SKILLS = (
    "ingest-comments",
    "refine-comments",
    "generate-skills",
    "orchestrate-repo-comment-intelligence",
)


def _clean_slug_part(part: str) -> str:
    part = part.replace("/", "--")
    part = re.sub(r"[^A-Za-z0-9._-]+", "-", part)
    return part.strip("-.")[:80] or "unknown"


def repo_slug(host: str, owner: str, repo: str) -> str:
    return f"{_clean_slug_part(host)}--{_clean_slug_part(owner)}--{_clean_slug_part(repo)}"


def artifact_dir(git_root: Path, host: str, owner: str, repo: str) -> Path:
    return Path(git_root) / ARTIFACT_ROOT / repo_slug(host, owner, repo)


def canonical_skills_dir(git_root: Path) -> Path:
    return Path(git_root) / CANONICAL_SKILLS


def derived_skill_dir(git_root: Path, name: str) -> Path:
    return canonical_skills_dir(git_root) / name
