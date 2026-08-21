"""Copy canonical `.agents/skills` trees into tool-specific mirrors."""

from __future__ import annotations

import shutil
from pathlib import Path

from .paths import CANONICAL_SKILLS, MIRROR_SKILLS


def mirror_skills(git_root: Path) -> list[str]:
    src = Path(git_root) / CANONICAL_SKILLS
    if not src.is_dir():
        raise SystemExit(f"canonical skills directory missing: {src}")
    copied: list[str] = []
    for dest_rel in MIRROR_SKILLS:
        dest = Path(git_root) / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        copied.append(str(dest_rel))
    return copied
