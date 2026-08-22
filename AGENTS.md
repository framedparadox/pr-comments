# Agent notes

This repository **publishes** a pull request comment extractor skill pack. It is not a per-agent workspace. Do not create `.claude/`, `.agents/`, or `.github/skills/` here.

Install into a coding agent:

```bash
npx skills add framedparadox/pr-comments
uv tool install git+https://github.com/framedparadox/pr-comments
```

When the user wants every PR comment on the main (or default) branch documented:

```bash
pr-comments extract --repo owner/name --out ./pr-comments-export
pr-comments serve --out ./pr-comments-export
```

Skill source: `skills/*/SKILL.md`. CLI source: `src/pr_comments/`.
