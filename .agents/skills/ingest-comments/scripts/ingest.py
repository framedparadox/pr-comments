#!/usr/bin/env python3
import sys

import _boot  # noqa: F401
from comment_intel.cli import main

raise SystemExit(main(["ingest", *sys.argv[1:]]))
