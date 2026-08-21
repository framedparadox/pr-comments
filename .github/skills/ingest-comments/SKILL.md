---
name: ingest-comments
description: Detect a git repository and hosting platform, then fetch all pull request / merge request discussion comments, review comments, inline comments, and threads from inception or the last checkpoint. Use when ingesting PR/MR comments, backfilling review history, or collecting bot and human comments from GitHub, GitLab, Bitbucket, Gitea, or a local JSON dump.
metadata:
  version: "1.0.0"
  author: framedparadox
compatibility: Requires git, python3, and gh/glab or host REST tokens (or --local-json)
---

# ingest-comments

Fetch every accessible PR/MR comment for a git repository and write normalized records. Do not classify or rewrite derived skills here — that is `refine-comments` / `generate-skills`.

## When to use

- The user wants comment history from a local checkout or a supported remote host.
- You need a raw ledger before refinement.
- A previous run already exists and you must resume from the checkpoint rather than re-fetching everything.

## Command

```bash
python3 .agents/skills/ingest-comments/scripts/ingest.py \
  [--git-dir PATH] [--repo owner/name] [--host github|gitlab|bitbucket|gitea] \
  [--base-branch BRANCH] [--cutoff 2026-08-01T00:00:00Z] [--local-json dump.json]
```

## Workflow

1. Resolve the git root (`git rev-parse --show-toplevel` or `--git-dir`).
2. Detect provider/host/owner/repo from `origin`. If unknown, ask for `--host` or `--local-json`.
3. Resolve the base branch: API default → `origin/HEAD` → `main` → `master`. If still ambiguous, **stop and ask** for `--base-branch`. Never guess between two live defaults.
4. Read `.comment-intelligence/repos/<host>--<owner>--<repo>/checkpoint.json` and the `<!-- comment-intel:cutoff:... -->` marker in `REPORT.md` **before** calling any API.
5. List PRs/MRs targeting that base (any state). If a cutoff exists, only consider items updated on/after that date, then client-filter comments with `created_at > cutoff`.
6. Collect conversation comments, inline/diff comments, review summaries, and thread ids. Keep bots and deactivated accounts (`author_type: deleted`, login `ghost` if missing).
7. Append **new ids only** to `comments.jsonl`. Rewrite `comments.json` as the full ledger snapshot. Write `ingest_run.json` for the refine step.

## Gotchas

- Git stores no PR comments. A local clone without API credentials cannot backfill unless `--local-json` is provided.
- `gh api --paginate` may concatenate JSON arrays; the bundled parser repairs `][`.
- GitHub search `updated:>=` uses the date prefix; exact resume still happens client-side via `created_at`.
- Do not filter out bots, Dependabot, or `ghost` users.
- Do not update `checkpoint.json` in this skill; refine owns the cutoff after records are classified.

## Outputs

See [references/sources.md](references/sources.md) and [references/comment-record.schema.json](references/comment-record.schema.json).
