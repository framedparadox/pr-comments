#!/usr/bin/env python3
"""Find comment_intel on sys.path whether this wrapper is canonical or mirrored."""

from __future__ import annotations

import sys
from pathlib import Path


def bootstrap() -> None:
    here = Path(__file__).resolve().parent
    candidates = [here]
    for parent in here.parents:
        candidates.extend(
            [
                parent / "ingest-comments" / "scripts",
                parent / "skills" / "ingest-comments" / "scripts",
                parent / ".agents" / "skills" / "ingest-comments" / "scripts",
                parent / ".claude" / "skills" / "ingest-comments" / "scripts",
                parent / ".github" / "skills" / "ingest-comments" / "scripts",
            ]
        )
    for candidate in candidates:
        if (candidate / "comment_intel").is_dir():
            path = str(candidate)
            if path not in sys.path:
                sys.path.insert(0, path)
            return
    raise SystemExit("cannot find comment_intel package (ingest-comments/scripts)")


bootstrap()
