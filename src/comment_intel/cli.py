"""Command-line interface for the comment intelligence pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from .pipeline import generate, ingest, orchestrate, refine, resolve_identity


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pr-comments",
        description="Ingest, refine, and mine git host PR/MR comments.",
    )
    parser.add_argument("--git-dir", help="Git working tree (defaults to cwd)")
    parser.add_argument("--repo", help="Override owner/name (or group/name)")
    parser.add_argument(
        "--host",
        help="Hosting provider or hostname: github, gitlab, bitbucket, gitea, or example.com",
    )
    parser.add_argument("--base-branch", help="PR/MR target branch if detection is ambiguous")
    parser.add_argument("--local-json", help="Import comments from a JSON/JSONL dump")
    parser.add_argument("--cutoff", help="Override resume cutoff (ISO-8601 UTC)")
    parser.add_argument(
        "command",
        nargs="?",
        default="orchestrate",
        choices=("ingest", "refine", "generate", "orchestrate"),
        help="Pipeline step (default: orchestrate)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "orchestrate":
        result = orchestrate(
            git_dir=args.git_dir,
            host=args.host,
            repo=args.repo,
            base_branch=args.base_branch,
            local_json=args.local_json,
        )
        print(json.dumps(result, indent=2))
        return 0

    identity = resolve_identity(
        args.git_dir,
        args.host,
        args.repo,
        args.base_branch,
        args.local_json,
    )
    if args.command == "ingest":
        result = ingest(identity, cutoff=args.cutoff, local_json=args.local_json)
        print(
            json.dumps(
                {
                    "artifact_dir": str(result["artifact_dir"]),
                    "new_comments": len(result["new_records"]),
                    "total_comments": len(result["all_comments"]),
                    "cutoff_used": result["cutoff_used"],
                },
                indent=2,
            )
        )
        return 0
    if args.command == "refine":
        result = refine(identity)
        print(
            json.dumps(
                {
                    "artifact_dir": str(result["artifact_dir"]),
                    "unique_comments": len(result["uniques"]),
                    "new_uniques": len(result["new_uniques"]),
                    "cutoff": result["checkpoint"].get("cutoff"),
                },
                indent=2,
            )
        )
        return 0
    if args.command == "generate":
        result = generate(identity)
        print(json.dumps(result, indent=2))
        return 0
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
