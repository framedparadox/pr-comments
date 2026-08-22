---
name: extract-pr-comments
description: Fetch every pull request comment and reply on PRs targeting the repo default/main branch — including comments from bots and later-deactivated GitHub accounts — then save a local CSV and generate a review dashboard. Use when documenting PR history, exporting review comments, archiving feedback, or building a comment CSV.
metadata:
  version: "1.0.0"
  author: framedparadox
compatibility: Requires python3 and either the gh CLI or GH_TOKEN/GITHUB_TOKEN. Install with npx skills add framedparadox/pr-comments or uv tool install.
---

# extract-pr-comments

Document **all** pull request comments on a repository: conversation comments, inline diff comments, review summaries, and replies. Do not drop bots or `ghost` (deactivated) authors.

## Install

```bash
npx skills add framedparadox/pr-comments
uv tool install git+https://github.com/framedparadox/pr-comments
uvx --from git+https://github.com/framedparadox/pr-comments pr-comments extract
```

This pack does not create `.claude/`, `.agents/`, or `.github/skills/` trees. `npx skills add` copies these folders into the agent the user selects.

## Command

```bash
pr-comments extract \
  [--repo owner/name] [--git-dir PATH] [--host github.com] \
  [--base-branch main] [--out DIR] [--since 2024-01-01T00:00:00Z]
```

Checkout fallback:

```bash
python3 skills/extract-pr-comments/scripts/extract.py --repo owner/name
```

## Workflow

1. Resolve the repository: `--repo owner/name`, or `origin` of `--git-dir` / cwd.
2. Resolve the base branch: `--base-branch` → GitHub default branch → `origin/HEAD` → `main`. Only PRs **targeting that branch** are included (open, closed, and merged).
3. Fetch three GitHub sources (see [references/sources.md](references/sources.md)):
   - `GET /repos/{owner}/{repo}/issues/comments` — conversation comments on those PRs
   - `GET /repos/{owner}/{repo}/pulls/comments` — inline review comments and replies
   - `GET /repos/{owner}/{repo}/pulls/{n}/reviews` — review summary bodies (empty bodies skipped)
4. Keep every author. If GitHub returns `"user": null`, store `comment_by=ghost` and `author_type=deleted`.
5. Write artifacts under `--out` or `pr-comments-export/<host>--<owner>--<repo>/`:
   - `comments.csv` — spreadsheet archive
   - `comments.json` / `comments.jsonl` — full records
   - `dashboard.html` — local review UI
   - `meta.json` — extract timestamp and counts
6. Tell the user the CSV and dashboard paths. To browse, they can open `dashboard.html` or run the `review-pr-comments` skill.

## Fields

See [references/fields.md](references/fields.md). CSV always includes commit id, PR created date, comment date, comment by, and comment body.

## Do not

- Filter out bots, Dependabot, or deactivated accounts
- Limit to open or merged PRs only
- Fetch PRs that target a branch other than the resolved base
- Create per-agent skill directories in this repository
