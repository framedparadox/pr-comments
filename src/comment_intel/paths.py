"""Locate shipped skill directories and per-repo artifacts.

This package never creates agent-specific folders (.claude, .agents, .github).
Those appear only when a user installs the pack with `npx skills add`.
"""

from __future__ import annotations

import os
import re
from importlib import resources
from pathlib import Path

ARTIFACT_ROOT = ".comment-intelligence/repos"
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


def package_root() -> Path:
    """Checkout root when developing; otherwise the installed package dir."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file() and (parent / "skills").is_dir():
            return parent
    return here.parents[1]


def bundled_skills_dir() -> Path:
    env = os.environ.get("COMMENT_INTEL_SKILLS_DIR")
    if env:
        return Path(env)
    root = package_root()
    checkout = root / "skills"
    if checkout.is_dir():
        return checkout
    try:
        data = resources.files("comment_intel") / "data" / "skills"
        if data.is_dir():
            return Path(str(data))
    except (FileNotFoundError, ModuleNotFoundError, TypeError):
        pass
    return checkout


def _append_unique(found: list[Path], candidate: Path) -> None:
    if not (candidate / "SKILL.md").is_file():
        return
    resolved = candidate.resolve()
    if resolved not in {path.resolve() for path in found}:
        found.append(candidate)


def installed_skill_dirs(git_root: Path, name: str) -> list[Path]:
    """Existing copies of a skill. Never creates agent-specific directories."""
    found: list[Path] = []
    env = os.environ.get("COMMENT_INTEL_SKILLS_DIR")
    if env:
        _append_unique(found, Path(env) / name)
        if found:
            return found

    root = Path(git_root)
    _append_unique(found, root / "skills" / name)
    if root.is_dir():
        for child in root.iterdir():
            if child.name.startswith(".") and child.is_dir():
                _append_unique(found, child / "skills" / name)

    if found:
        return found

    bundled = bundled_skills_dir() / name
    if (bundled / "SKILL.md").is_file():
        try:
            same_pack = root.resolve() == package_root().resolve()
        except OSError:
            same_pack = False
        if same_pack:
            found.append(bundled)
    return found


def derived_skill_dir(git_root: Path, name: str) -> Path:
    dirs = installed_skill_dirs(git_root, name)
    if dirs:
        return dirs[0]
    target = bundled_skills_dir() / name
    return target
