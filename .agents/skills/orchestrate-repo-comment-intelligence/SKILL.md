---
name: orchestrate-repo-comment-intelligence
description: Run the full git-repository comment intelligence pipeline end to end — discover the repo, ingest PR/MR comments from inception or the last checkpoint, refine and classify, regenerate the Markdown knowledge base, merge derived skills, and mirror them for Claude Code, Copilot, and Codex. Use when the user wants one command to backfill or update comment history and review skills.
metadata:
  version: "1.0.0"
  author: framedparadox
compatibility: Requires git, python3, and gh/glab or REST tokens (or --local-json)
---

# orchestrate-repo-comment-intelligence

Single entrypoint for the portable comment-intelligence pack.

## Command

```bash
python3 .agents/skills/orchestrate-repo-comment-intelligence/scripts/run_pipeline.py \
  [--git-dir PATH] [--repo owner/name] [--host github|gitlab|bitbucket|gitea] \
  [--base-branch BRANCH] [--local-json dump.json] [--cutoff ISO] [--skip-mirror]
```

Mirror only:

```bash
.agents/skills/orchestrate-repo-comment-intelligence/scripts/mirror_skills.sh
```

## Pipeline

1. **ingest-comments** — detect repo/host, honor checkpoint cutoff, fetch comments, append jsonl.
2. **refine-comments** — dedup, classify new uniques, write `REPORT.md` + `checkpoint.json`.
3. **generate-skills** — merge patterns into `code-review`, `git-checkin`, `commit-hooks`.
4. **mirror** — copy `.agents/skills/` → `.claude/skills/` and `.github/skills/`. Codex already reads `.agents/skills/`.

Read each child skill if a step fails. Do not skip the cutoff read. Do not overwrite `## User customizations`.

## Repeated runs

- Same cutoff and no new comments ⇒ no duplicate jsonl rows, no new unique keys, no spurious pattern ids.
- Mirror still runs so tool paths stay in sync with canonical files.
- If the base branch cannot be determined, stop and ask. Default order is API default, `origin/HEAD`, `main`, `master`.

## Artifacts

`.comment-intelligence/repos/<host>--<owner>--<repo>/`

- `REPORT.md`
- `comments.jsonl` / `comments.json`
- `unique.json`
- `checkpoint.json`

## Composable alternatives

Run the child scripts instead of this orchestrator when the user only wants one stage. Canonical source of truth is always `.agents/skills/`; never edit mirrors by hand.
