#!/usr/bin/env bash
# Mirror canonical .agents/skills into Claude Code and GitHub Copilot discovery paths.
set -euo pipefail
DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export PYTHONPATH="${DIR}:${PYTHONPATH:-}"
exec python3 - "$DIR" "$@" <<'PY'
import sys
from pathlib import Path

boot = Path(sys.argv[1])
sys.path.insert(0, str(boot))
import _boot  # noqa: F401
from comment_intel.cli import main

raise SystemExit(main(["mirror", *sys.argv[2:]]))
PY
