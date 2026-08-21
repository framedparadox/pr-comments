---
name: generate-skills
description: Fold newly classified unique PR/MR comments into derived code-review, git-checkin, and commit-hooks skills without overwriting stable rules or user customizations. Use when updating review skills from comment history, merging new evidence into pattern libraries, or refreshing hook/check-in guidance from recurring review feedback.
metadata:
  version: "1.0.0"
  author: framedparadox
compatibility: Requires python3 and unique.json from refine-comments
---

# generate-skills

Mine the unique-comment corpus and merge evidence into derived skills.

## Command

```bash
python3 .agents/skills/generate-skills/scripts/generate.py \
  [--git-dir PATH] [--repo owner/name] [--host HOST] [--base-branch BRANCH]
```

## Targets (canonical)

- `.agents/skills/code-review/references/patterns.md`
- `.agents/skills/git-checkin/references/patterns.md`
- `.agents/skills/commit-hooks/references/patterns.md`

`SKILL.md` workflow text stays stable. Only pattern libraries grow. Anything under `## User customizations` is copied verbatim.

## Merge rules

1. Weight `P0` / `P1`, then `security` and `correctness`.
2. Pattern id = `{category}:{subcategory}`.
3. If the id exists, append PR refs to **Confirmed in** and bump **Seen**. Do not duplicate the rule.
4. If the id is new, append a block with rule, anti-pattern, examples, and provenance (`host/repo#PR`).
5. Skip non-actionable P2/P3 clarification/praise noise.

## After the script

Read the diff. If a new pattern is too specific (one-off wording), generalize the **Rule** line by hand under `## User customizations` rather than deleting the generated block. Prefer citing PRs over rewriting history.

Then run the orchestrator mirror step (or `mirror_skills.sh`) so Claude Code and Copilot see the same patterns.
