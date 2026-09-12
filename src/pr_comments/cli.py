"""Command-line interface for the pull request comment extractor."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .extract import extract
from .serve import serve


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pr-comments",
        description=(
            "Fetch every comment and reply on pull requests targeting the main "
            "branch, write a local CSV, and generate a review dashboard."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    extract_p = sub.add_parser("extract", help="Fetch comments and write CSV + dashboard")
    extract_p.add_argument("--git-dir", help="Git working tree (defaults to cwd)")
    extract_p.add_argument("--repo", help="owner/name, if not inferred from origin")
    extract_p.add_argument("--host", default=None, help="github.com or GitHub Enterprise hostname")
    extract_p.add_argument("--base-branch", help="PR target branch (default: repo default / main)")
    extract_p.add_argument("--out", dest="output_dir", help="Directory to write CSV, JSON, and dashboard")
    extract_p.add_argument("--since", help="Only keep comments at or after this ISO-8601 timestamp")
    extract_p.add_argument("--max-prs", type=int, help="Limit how many PRs to scan (debug)")
    extract_p.add_argument("--local-json", help="Skip the API and load already-fetched comment rows")

    serve_p = sub.add_parser("serve", help="Serve a previously generated dashboard")
    serve_p.add_argument("--out", dest="output_dir", required=True, help="Directory that contains dashboard.html")
    serve_p.add_argument("--bind", default="127.0.0.1", help="Bind address")
    serve_p.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    raw = list(argv) if argv is not None else sys.argv[1:]
    if not raw or raw[0] not in {"extract", "serve", "-h", "--help"}:
        raw = ["extract", *raw]
    parser = build_parser()
    args = parser.parse_args(raw)

    if args.command == "serve":
        serve(Path(args.output_dir), host=args.bind, port=args.port)
        return 0

    result = extract(
        git_dir=args.git_dir,
        host=args.host,
        repo=args.repo,
        base_branch=args.base_branch,
        output_dir=args.output_dir,
        since=args.since,
        max_prs=args.max_prs,
        local_json=args.local_json,
    )
    print(json.dumps(result, indent=2))
    print(
        f"\nWrote {result['comment_count']} comments from {result['pull_request_count']} PRs\n"
        f"  CSV:       {result['csv']}\n"
        f"  JSON:      {result['json']}\n"
        f"  Dashboard: {result['dashboard']}\n"
        f"Open the dashboard file in a browser, or run:\n"
        f"  pr-comments serve --out {result['output_dir']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
