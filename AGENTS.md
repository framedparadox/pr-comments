# Agent notes

This repository is a portable **comment intelligence** skill pack.

When the user asks to ingest PR/MR comments, refine a comment history, generate review skills, or run the full pipeline, use the orchestrator skill:

- Canonical: `.agents/skills/orchestrate-repo-comment-intelligence/SKILL.md`
- Command: `python3 .agents/skills/orchestrate-repo-comment-intelligence/scripts/run_pipeline.py`

Composable skills:

- `.agents/skills/ingest-comments/SKILL.md`
- `.agents/skills/refine-comments/SKILL.md`
- `.agents/skills/generate-skills/SKILL.md`

Derived skills (updated from the comment corpus, merge-only):

- `.agents/skills/code-review/SKILL.md`
- `.agents/skills/git-checkin/SKILL.md`
- `.agents/skills/commit-hooks/SKILL.md`

`.agents/skills/` is the source of truth. After editing canonical skills, run:

```bash
python3 .agents/skills/orchestrate-repo-comment-intelligence/scripts/mirror_skills.sh
```

Do not hand-edit `.claude/skills` or `.github/skills`.
