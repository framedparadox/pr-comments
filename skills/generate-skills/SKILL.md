---
name: generate-skills
description: Fold newly classified unique PR/MR comments into derived code-review, git-checkin, and commit-hooks skills without overwriting stable rules or user customizations. Use when updating review skills from comment history, merging new evidence into pattern libraries, or refreshing hook/check-in guidance from recurring review feedback.
metadata:
  version: "1.0.0"
  author: framedparadox
compatibility: Requires python3 and unique.json from refine-comments. Install this pack with npx skills add or uv.
---

# generate-skills

Mine the unique-comment corpus and merge evidence into derived skills that were installed from this pack.

## Command

```bash
pr-comments generate \
  [--git-dir PATH] [--repo owner/name] [--host HOST] [--base-branch BRANCH]
```

Checkout fallback: `python3 skills/generate-skills/scripts/generate.py`

## Targets

Updates existing copies of:

- `code-review/references/patterns.md`
- `git-checkin/references/patterns.md`
- `commit-hooks/references/patterns.md`

Search order: this pack's `skills/` directory, a project-level `skills/` directory, then any **already installed** agent skill copies. Never create `.claude/`, `.agents/`, or `.github/` folders — those come from `npx skills add`.

`SKILL.md` workflow text stays stable. Anything under `## User customizations` is copied verbatim.

## Merge rules

1. Weight `P0` / `P1`, then `security` and `correctness`.
2. Pattern id = `{category}:{subcategory}`.
3. If the id exists, append PR refs to **Confirmed in** and bump **Seen**. Do not duplicate the rule.
4. If the id is new, append a block with rule, anti-pattern, examples, and provenance.
5. Skip non-actionable P2/P3 clarification/praise noise.
