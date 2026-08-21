# Agent notes

This repository **publishes** a PR/MR comment-intelligence skill pack. It is not a per-agent workspace. Do not create `.claude/`, `.agents/`, or `.github/skills/` here.

Install into a coding agent:

```bash
npx skills add framedparadox/pr-comments
uv tool install git+https://github.com/framedparadox/pr-comments
```

When the user wants to ingest comments, refine history, or generate review skills, run:

```bash
pr-comments orchestrate --git-dir <analyzed-repo>
```

Skill source: `skills/*/SKILL.md`. CLI source: `src/comment_intel/`.
