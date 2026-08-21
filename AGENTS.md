# Agent notes

This repository **publishes** the **review-mx** PR/MR comment-intelligence skill pack. It is not a per-agent workspace. Do not create `.claude/`, `.agents/`, or `.github/skills/` here.

Install into a coding agent:

```bash
npx skills add framedparadox/pr-comments
uv tool install git+https://github.com/framedparadox/pr-comments
```

The GitHub source is currently `framedparadox/pr-comments`. After it is renamed, use `framedparadox/review-mx`.

When the user wants to ingest comments, refine history, or generate review skills, run:

```bash
review-mx orchestrate --git-dir <analyzed-repo>
```

Skill source: `skills/*/SKILL.md`. CLI source: `src/comment_intel/`.
