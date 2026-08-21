---
name: refine-comments
description: Deduplicate ingested PR/MR comments, classify them by category, tags, P0–P3 priority, and actionability, then write the per-repository Markdown knowledge base. Use when refining comment history, regenerating REPORT.md, or resuming from the last processed checkpoint without re-fetching old comments.
metadata:
  version: "1.0.0"
  author: framedparadox
compatibility: Requires python3 and an existing comments.jsonl from ingest-comments. Install this pack with npx skills add or uv.
---

# refine-comments

Turn the append-only ledger into a deduplicated, classified corpus and a regenerable Markdown report.

## Command

```bash
review-mx refine \
  [--git-dir PATH] [--repo owner/name] [--host github|gitlab|bitbucket|gitea] \
  [--base-branch BRANCH]
```

Checkout fallback: `python3 skills/refine-comments/scripts/refine.py`

## Workflow

1. Read `checkpoint.json` / `REPORT.md` cutoff if the user asked whether reprocessing is needed. Ingest already honored the cutoff; refine must still refuse to *reclassify* old unique keys.
2. Load `comments.jsonl` and existing `unique.json` under the **analyzed repo's** `.comment-intelligence/` directory.
3. Dedup on `normalize(body) + repo`. Identical bot boilerplate becomes one row with `seen_count` and an occurrence list.
4. Classify **new keys only** using [references/taxonomy.md](references/taxonomy.md). Heuristic first. Then review `confidence: low` items and override only those.
5. Write `unique.json`, `comments.json`, `checkpoint.json`, and `REPORT.md`.

## REPORT.md rules

- HTML comments at the top: `comment-intel:cutoff`, `repo`, `base`.
- `## Checkpoint` always regenerated from current data.
- Newest `## Run:` section first; previous run sections preserved.
- Unique comments grouped by category, then priority.
- Raw ledger of every ingested comment.
- Per-PR / per-MR timeline.
- Preserve `## User customizations`.

Do not rewrite history tables for old unique keys. Do not drop older run sections.
