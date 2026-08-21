---
name: git-checkin
description: Write Conventional Commits with trailers that trace back to review comments addressed by the change, and warn when P0 comment-intelligence findings are still open. Use when committing, drafting a commit message, or checking in work after a review.
metadata:
  version: "1.0.0"
  author: framedparadox
---

<!-- comment-intel:generated:true -->

# git-checkin

Produce a structured, traceable commit. Do not commit until the message is written.

## Workflow

1. Inspect the staged diff (`git diff --cached`). If nothing is staged, say so and stop.
2. Read [references/patterns.md](references/patterns.md) and, if present, `.comment-intelligence/repos/*/unique.json` for open P0 items (`actionable` and `priority` P0).
3. **Warn** (do not silently block) if P0 uniques exist that this diff does not obviously address.
4. Write a Conventional Commits subject:
   - `type(scope): summary`
   - Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `ci`, `build`.
5. Add trailers for review comments this commit addresses:

```
Comment-Id: github:owner/repo:pr:150:review_comment:48212
Addresses: #150
```

6. Keep the subject ≤ 72 characters. Body explains *why*.

## User customizations

Add extra trailer keys or commit policy below. generate-skills will preserve them.
