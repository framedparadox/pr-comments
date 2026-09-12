#!/usr/bin/env python3
"""Locate the pr-comments CLI after npx skills add or a git checkout."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

INSTALL_HINT = """pr-comments is not installed. Install the pack with:
  npx skills add framedparadox/pr-comments
  pip install pr-comments
  uv tool install pr-comments
  uvx pr-comments
"""


def ensure_import() -> None:
    try:
        import pr_comments  # noqa: F401

        return
    except ImportError:
        pass
    for parent in Path(__file__).resolve().parents:
        src = parent / "src"
        if (src / "pr_comments").is_dir():
            sys.path.insert(0, str(src))
            return
    raise SystemExit(INSTALL_HINT)


def run_cli(argv: list[str]) -> int:
    binary = shutil.which("pr-comments")
    if binary:
        return subprocess.call([binary, *argv])
    try:
        ensure_import()
        from pr_comments.cli import main

        return main(argv)
    except SystemExit as exc:
        if exc.code not in (None, 0) and shutil.which("uvx"):
            return subprocess.call(
                ["uvx", "--from", "git+https://github.com/framedparadox/pr-comments", "pr-comments", *argv]
            )
        raise
