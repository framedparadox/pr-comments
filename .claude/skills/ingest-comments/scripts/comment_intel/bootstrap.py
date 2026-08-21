"""Locate the shared comment_intel package from any skill scripts/ directory."""

from __future__ import annotations

import sys
from pathlib import Path


def bootstrap() -> Path:
    here = Path(__file__).resolve()
    searched: list[Path] = []
    for parent in [here.parent, *here.parents]:
        candidates = [
            parent / "ingest-comments" / "scripts",
            parent / "skills" / "ingest-comments" / "scripts",
            parent / ".agents" / "skills" / "ingest-comments" / "scripts",
            parent / ".claude" / "skills" / "ingest-comments" / "scripts",
            parent / ".github" / "skills" / "ingest-comments" / "scripts",
        ]
        if parent.name == "scripts":
            candidates.append(parent)
        for candidate in candidates:
            searched.append(candidate)
            if (candidate / "comment_intel").is_dir():
                path = str(candidate)
                if path not in sys.path:
                    sys.path.insert(0, path)
                return candidate
    raise SystemExit("cannot find comment_intel package; expected ingest-comments/scripts/comment_intel")
