#!/usr/bin/env python3
"""Run a pipeline command, using a checkout or an installed package."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_import() -> None:
    try:
        import comment_intel  # noqa: F401

        return
    except ImportError:
        pass
    for parent in Path(__file__).resolve().parents:
        src = parent / "src"
        if (src / "comment_intel").is_dir():
            sys.path.insert(0, str(src))
            return
    raise SystemExit(
        "pr-comments is not installed. Install the pack with:\n"
        "  npx skills add framedparadox/pr-comments\n"
        "  uv tool install git+https://github.com/framedparadox/pr-comments\n"
        "  uvx --from git+https://github.com/framedparadox/pr-comments pr-comments\n"
    )
