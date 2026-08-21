# PR Comment Intelligence

A portable [Agent Skills](https://agentskills.io/specification) pack that turns pull request / merge request discussion history into a living knowledge base and a set of derived coding skills.

It works with any git repository whose host exposes PR/MR comments (GitHub, GitLab, Bitbucket, Gitea/Forgejo) or with a local JSON mirror when there is no API.

## What it does

1. Detects the local git repo and hosting platform.
2. Fetches conversation comments, review comments, inline comments, and thread metadata from inception (or from the last checkpoint).
3. Keeps humans, bots, and later-deactivated accounts.
4. Normalizes, deduplicates, classifies, tags, and prioritizes unique comments.
5. Maintains a per-repository Markdown report plus JSON/JSONL exports.
6. Merges new evidence into derived **code-review**, **git-checkin**, and **commit-hooks** skills without overwriting customizations.
7. Mirrors canonical skills into Claude Code and GitHub Copilot discovery paths.

## Skills

| Skill | Use when |
| --- | --- |
| `orchestrate-repo-comment-intelligence` | You want the full pipeline in one run |
| `ingest-comments` | You only need to fetch and normalize comments |
| `refine-comments` | You already have a ledger and want classification + the Markdown report |
| `generate-skills` | You want to fold new unique comments into derived skills |
| `code-review` | Reviewing a change using patterns mined from this repo's comment history |
| `git-checkin` | Writing a commit that should trace back to review comments |
| `commit-hooks` | Installing git-native or agent hooks that gate on unresolved P0 comments |

Canonical copies live under [`.agents/skills/`](.agents/skills/). Codex discovers that path natively. Generated mirrors:

- [`.claude/skills/`](.claude/skills/) — Claude Code
- [`.github/skills/`](.github/skills/) — GitHub Copilot

Do not edit the mirrors. Edit `.agents/skills/` and run the mirror step.

## Quick start

From the git repository you want to analyze (this pack can live in that repo, or you can point `--git-dir` at another checkout):

```bash
python3 .agents/skills/orchestrate-repo-comment-intelligence/scripts/run_pipeline.py
```

Composable steps:

```bash
python3 .agents/skills/ingest-comments/scripts/ingest.py
python3 .agents/skills/refine-comments/scripts/refine.py
python3 .agents/skills/generate-skills/scripts/generate.py
python3 .agents/skills/orchestrate-repo-comment-intelligence/scripts/mirror_skills.sh
```

If the default branch is ambiguous, pass `--base-branch`. If the remote host cannot be detected, pass `--host github|gitlab|bitbucket|gitea` or import a dump with `--local-json path/to/comments.json`.

### Credentials

| Host | Preferred CLI | Environment fallback |
| --- | --- | --- |
| GitHub | `gh` (already authenticated) | `GH_TOKEN` / `GITHUB_TOKEN` |
| GitLab | `glab` | `GITLAB_TOKEN` |
| Bitbucket | — | `BITBUCKET_TOKEN` (workspace:repo via remote URL) |
| Gitea / Forgejo | — | `GITEA_TOKEN` |

## Artifacts

Each analyzed repository gets a directory under `.comment-intelligence/repos/<host>--<owner>--<repo>/`:

| File | Role |
| --- | --- |
| `REPORT.md` | Human-readable knowledge base (newest run at the top) |
| `comments.jsonl` | Append-only normalized ledger |
| `comments.json` | Full ledger export for automation |
| `unique.json` | Deduplicated, classified corpus |
| `checkpoint.json` | Resume marker (`cutoff`, last PR/MR, counts) |

Repeated runs read the checkpoint first and only fetch comments newer than the cutoff.

## Taxonomy

Every unique comment is tagged with:

- **category** — correctness, security, performance, maintainability, architecture, testing, documentation, style, UX, workflow, clarification
- **subcategory** — short heuristic label
- **tags** — including Conventional Comments labels when present (`nitpick`, `suggestion`, …)
- **priority** — P0 critical, P1 high, P2 medium, P3 low
- **actionable** — whether a code or process change is expected
- **provenance** — host, repo, PR/MR number, comment id, path/line, author, timestamp

See [`.agents/skills/refine-comments/references/taxonomy.md`](.agents/skills/refine-comments/references/taxonomy.md).

## Tests

```bash
python3 -m unittest discover -s tests -v
```

No live network is required. Fixtures cover GitHub/GitLab payloads, dedup, checkpoints, report generation, skill merging, and mirroring.

## Research

Prior design notes (not runtime format) are in [`research/`](research/):

- [Comment Refiner PRD](research/github-comment-skill-prd.md)
- [PR History Agent build brief](research/pr-history-agent-BUILD-BRIEF.md)
