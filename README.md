# PR comment extractor

An **installable Agent Skills pack** that documents every pull request comment on a repository — including replies and comments from accounts that were later deactivated — then saves a local CSV and a review dashboard.

It is not a Claude Code or Copilot project layout. Coding agents install the skills into *their* skill directories.

## Install

Any Agent Skills client (Claude Code, Codex, Copilot, Cursor, OpenCode, and others). `npx skills add owner/repo` clones the GitHub **default branch** (`main`). Use that command once this pack is on `main`.

```bash
npx skills add framedparadox/pr-comments
```

Until then, install from this branch (the `#` ref is required; a `/tree/…` URL is split on the slash in the branch name):

```bash
npx skills add https://github.com/framedparadox/pr-comments.git#cursor/pr-comment-extractor-0e39
```

From a local checkout of this pack:

```bash
npx skills add .
```

CLI:

```bash
uv tool install git+https://github.com/framedparadox/pr-comments
pr-comments extract --repo owner/name

uvx --from git+https://github.com/framedparadox/pr-comments pr-comments extract --repo owner/name
```

From a checkout of this pack:

```bash
uv run pr-comments extract --git-dir /path/to/the/repo
# or
npx . extract --git-dir /path/to/the/repo
```

## What it does

1. Lists every pull request that **targets the main / default branch** (open, closed, merged).
2. Fetches conversation comments, inline review comments, replies, and review summaries.
3. Keeps humans, bots, and later-deactivated accounts (`comment_by=ghost`).
4. Writes `comments.csv` (commit id, PR date, comment date, comment by, comment body, and related fields).
5. Writes a self-contained `dashboard.html` for filtering and reading threads.

## Skills

All skill source lives in [`skills/`](skills/) (the layout `npx skills add` discovers):

| Skill | Use when |
| --- | --- |
| `extract-pr-comments` | Fetch comments and write CSV + dashboard |
| `review-pr-comments` | Open or serve the local review dashboard |

## Artifacts

Default directory: `pr-comments-export/<host>--<owner>--<repo>/`

| File | Role |
| --- | --- |
| `comments.csv` | Spreadsheet archive (UTF-8 BOM, Excel-safe) |
| `comments.json` / `comments.jsonl` | Full records including diff hunks |
| `dashboard.html` | Local review UI (data embedded; works offline) |
| `meta.json` | Extract timestamp and counts |

```bash
pr-comments serve --out pr-comments-export/github.com--owner--repo
```

## Credentials

| Host | Preferred CLI | Environment fallback |
| --- | --- | --- |
| GitHub | `gh` | `GH_TOKEN` / `GITHUB_TOKEN` |

GitHub Enterprise: pass `--host your.ghe.example`.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Troubleshooting

### `No skills found`

`npx skills add framedparadox/pr-comments` clones `main`. If `main` only has the README, the CLI reports *No valid skills found. Skills require a SKILL.md with name and description.*

Install from the branch that contains `skills/*/SKILL.md`, or `npx skills add /path/to/this/checkout`. Verify with `--list` before installing:

```bash
npx skills add https://github.com/framedparadox/pr-comments.git#cursor/pr-comment-extractor-0e39 --list
```
