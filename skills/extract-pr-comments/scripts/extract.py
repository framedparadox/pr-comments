#!/usr/bin/env python3
"""Extract PR comments for the main branch into CSV + dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ensure import run_cli

if __name__ == "__main__":
    raise SystemExit(run_cli(["extract", *sys.argv[1:]]))
