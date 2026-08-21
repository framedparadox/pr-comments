# review-mx

An **installable Agent Skills pack** that mines pull request / merge request review comments into a persistent per-repo knowledge base and derived coding skills. It is not a Claude Code or Copilot project layout. This repository ships skills, a CLI, and research — coding agents install it into *their* skill directories.

The GitHub source is currently `framedparadox/pr-comments`. After that repository is renamed to `review-mx`, use `framedparadox/review-mx` in the install commands below.

## Install

Any Agent Skills client (Claude Code, Codex, Copilot, Cursor, OpenCode, and others):

```bash
npx skills add framedparadox/pr-comments
```

That command copies the `skills/` folders into the agent the user selects. This repo does not contain `.claude/`, `.agents/`, or `.github/skills/` trees.

CLI (pipeline + reports), via uv:

```bash
uv tool install git+https://github.com/framedparadox/pr-comments
review-mx orchestrate

# one-shot without a tool install
uvx --from git+https://github.com/framedparadox/pr-comments review-mx orchestrate
```

From a checkout of this pack:

```bash
uv run review-mx orchestrate --git-dir /path/to/the/repo/you/are/analyzing
# or
npx . orchestrate --git-dir /path/to/repo
```

## What it does

1. Detects a git repo and hosting platform (GitHub, GitLab, Bitbucket, Gitea/Forgejo, or a local JSON dump).
2. Fetches conversation, review, inline, and thread comments from inception or the last checkpoint.
3. Keeps humans, bots, and later-deactivated accounts.
4. Normalizes, deduplicates, classifies, tags, and prioritizes unique comments.
5. Writes a per-repository Markdown knowledge base into the **analyzed** repo.
6. Merges new evidence into derived **code-review**, **git-checkin**, and **commit-hooks** skills without overwriting customizations.

## Skills

All skill source lives in [`skills/`](skills/) (the layout `npx skills add` discovers):

| Skill | Use when |
| --- | --- |
| `orchestrate-repo-comment-intelligence` | Full pipeline in one run |
| `ingest-comments` | Fetch and normalize comments only |
| `refine-comments` | Classify + regenerate `REPORT.md` |
| `generate-skills` | Fold unique comments into derived skills |
| `code-review` | Review a change using mined patterns |
| `git-checkin` | Commit with trailers back to review comments |
| `commit-hooks` | Git-native or agent hooks gated on P0 comments |

## Layout

```text
skills/                  # Agent Skills (install these)
src/comment_intel/       # Python CLI used by those skills
bin/review-mx.js         # npx entry that delegates to uv/python
pyproject.toml           # uv / pip
package.json             # npx
research/                # design briefs, not runtime
```

## Analyzed-repo artifacts

When you run the CLI against a git repository, files are written **there**, not into this pack:

`.comment-intelligence/repos/<host>--<owner>--<repo>/`

| File | Role |
| --- | --- |
| `REPORT.md` | Human-readable knowledge base (newest run at the top) |
| `comments.jsonl` | Append-only normalized ledger |
| `comments.json` | Full ledger export |
| `unique.json` | Deduplicated, classified corpus |
| `checkpoint.json` | Resume marker |

Repeated runs read the checkpoint first and only fetch comments newer than the cutoff.

### Credentials

| Host | Preferred CLI | Environment fallback |
| --- | --- | --- |
| GitHub | `gh` | `GH_TOKEN` / `GITHUB_TOKEN` |
| GitLab | `glab` | `GITLAB_TOKEN` |
| Bitbucket | — | `BITBUCKET_TOKEN` |
| Gitea / Forgejo | — | `GITEA_TOKEN` |

## Taxonomy

Every unique comment is tagged with category, subcategory, tags, P0–P3 priority, actionability, and provenance. See [`skills/refine-comments/references/taxonomy.md`](skills/refine-comments/references/taxonomy.md).

## Tests

```bash
python3 -m unittest discover -s tests -v
```

## Research

- [Comment Refiner PRD](research/github-comment-skill-prd.md)
- [PR History Agent build brief](research/pr-history-agent-BUILD-BRIEF.md)
