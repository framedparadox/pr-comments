---
name: orchestrate-repo-comment-intelligence
description: Run the full review-mx pipeline end to end — discover the repo, ingest PR/MR comments from inception or the last checkpoint, refine and classify, regenerate the Markdown knowledge base, and merge derived skills. Use when the user wants one command to backfill or update comment history and review skills. Install this pack with npx skills add framedparadox/pr-comments or uv tool install.
metadata:
  version: "1.0.0"
  author: framedparadox
compatibility: Requires git, python3, and gh/glab or REST tokens (or --local-json)
---

# orchestrate-repo-comment-intelligence

Single entrypoint for the review-mx pack.

## Install

```bash
npx skills add framedparadox/pr-comments
uv tool install git+https://github.com/framedparadox/pr-comments
uvx --from git+https://github.com/framedparadox/pr-comments review-mx
```

`npx skills add` places these skills into whichever coding agent the user selects. This repository itself does not ship `.claude/` or `.agents/` copies.

## Command

```bash
review-mx orchestrate \
  [--git-dir PATH] [--repo owner/name] [--host github|gitlab|bitbucket|gitea] \
  [--base-branch BRANCH] [--local-json dump.json] [--cutoff ISO]
```

Checkout fallback: `python3 skills/orchestrate-repo-comment-intelligence/scripts/run_pipeline.py`

## Pipeline

1. **ingest-comments** — detect repo/host, honor checkpoint cutoff, fetch comments, append jsonl.
2. **refine-comments** — dedup, classify new uniques, write `REPORT.md` + `checkpoint.json` in the analyzed repo.
3. **generate-skills** — merge patterns into installed `code-review`, `git-checkin`, `commit-hooks` copies.

Read each child skill if a step fails. Do not skip the cutoff read. Do not overwrite `## User customizations`. Do not create per-agent skill directories.

## Repeated runs

- Same cutoff and no new comments ⇒ no duplicate jsonl rows, no new unique keys, no spurious pattern ids.
- If the base branch cannot be determined, stop and ask. Default order is API default, `origin/HEAD`, `main`, `master`.

## Artifacts

Written into the **analyzed git repository** (not into this pack):

`.comment-intelligence/repos/<host>--<owner>--<repo>/`

- `REPORT.md`
- `comments.jsonl` / `comments.json`
- `unique.json`
- `checkpoint.json`
