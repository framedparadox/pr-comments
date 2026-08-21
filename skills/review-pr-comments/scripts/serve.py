#!/usr/bin/env python3
"""Serve a previously generated PR comment dashboard."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ensure import run_cli

if __name__ == "__main__":
    raise SystemExit(run_cli(["serve", *sys.argv[1:]]))
