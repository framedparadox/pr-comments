# PR comment extractor

An **installable Agent Skills pack** that documents every pull request comment on a repository — including replies and comments from accounts that were later deactivated — then saves a local CSV and a review dashboard.

It is not a Claude Code or Copilot project layout. Coding agents install the skills into *their* skill directories.

## Install

Any Agent Skills client (Claude Code, Codex, Copilot, Cursor, OpenCode, and others):

```bash
npx skills add framedparadox/pr-comments
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

All skill source lives in [`skills/`](skills/) (the layout `npx skills add` discovers). Coding agents load these when you ask to archive PR comments or browse the local dashboard.

### `extract-pr-comments`

Fetches **every** comment on pull requests that target the repository’s main / default branch and writes a local archive. Use it when documenting PR history, exporting review feedback, or building a comment CSV.

It resolves the repo from `--repo owner/name` or from `origin` of `--git-dir` / the current checkout, then resolves the base branch (`--base-branch` → GitHub default → `origin/HEAD` → `main`). Only PRs targeting that branch are included — open, closed, and merged.

Three GitHub sources are merged:

| Kind | What is kept |
| --- | --- |
| Conversation | Discussion-tab comments on those PRs |
| Inline review | Diff comments and their replies (`commit_id`, path, line) |
| Review summary | Non-empty review bodies (empty “reviewed” events are skipped) |

Authors are never filtered. Humans, bots (including Dependabot), and later-deactivated accounts are all kept. When GitHub returns `"user": null`, the row is stored as `comment_by=ghost` with `author_type=deleted`.

```bash
pr-comments extract \
  [--repo owner/name] [--git-dir PATH] [--host github.com] \
  [--base-branch main] [--out DIR] [--since 2024-01-01T00:00:00Z]
```

Checkout fallback: `python3 skills/extract-pr-comments/scripts/extract.py --repo owner/name`.

CSV columns always include commit id, PR created date, comment date, comment by, and comment body (see [`skills/extract-pr-comments/references/fields.md`](skills/extract-pr-comments/references/fields.md)). After the extract, the agent should report the CSV and dashboard paths; browsing is the `review-pr-comments` skill.

### `review-pr-comments`

Opens the archive produced by `extract-pr-comments`. It does **not** call GitHub again unless you ask for a fresh extract. Use it to browse, filter, or re-read comments — including `ghost` / deleted authors.

`dashboard.html` is self-contained (comment data is embedded) and works offline. Prefer opening that file in a browser. If `file://` is blocked, serve the export directory:

```bash
pr-comments serve --out pr-comments-export/<host>--<owner>--<repo>
```

Then open `http://127.0.0.1:8765/dashboard.html`. Checkout fallback: `python3 skills/review-pr-comments/scripts/serve.py --out DIR`.

In the dashboard you can:

- Filter by comment by, author type (`user` / `bot` / `deleted`), kind, PR, and comment date
- Search text, path, and commit SHA
- Expand a row for the full body, commit SHA, PR created date, links, and thread replies
- Toggle light and dark mode with the header logo
- Download the current filtered view as CSV (the full archive remains `comments.csv`)

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
