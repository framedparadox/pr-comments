# Agent notes

This repository **publishes** a pull request comment extractor skill pack. It is not a per-agent workspace. Do not create `.claude/`, `.agents/`, or `.github/skills/` here.

Install into a coding agent. `npx skills add owner/repo` reads the GitHub default branch (`main`), not this working branch:

```bash
npx skills add framedparadox/pr-comments
# until the pack is on main:
npx skills add https://github.com/framedparadox/pr-comments.git#cursor/pr-comment-extractor-0e39
npx skills add .
uv tool install git+https://github.com/framedparadox/pr-comments
```

When the user wants every PR comment on the main (or default) branch documented:

```bash
pr-comments extract --repo owner/name --out ./pr-comments-export
pr-comments serve --out ./pr-comments-export
```

Skill source: `skills/*/SKILL.md`. CLI source: `src/pr_comments/`.
