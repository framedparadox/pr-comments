#!/usr/bin/env python3
import sys

import _ensure

_ensure.ensure_import()
from comment_intel.cli import main

raise SystemExit(main(["refine", *sys.argv[1:]]))
