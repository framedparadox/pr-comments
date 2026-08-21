# PR History Agent — build brief for Claude Code

This extends `comment-refiner` (already built — see `comment-refiner.zip` /
`github-comment-skill-prd.md` from the earlier planning) into a repo-wide,
resumable, self-improving agent. Reuses `comment-refiner`'s taxonomy rather
than forking a new one. This doc is written to be handed to Claude Code
directly.

## What it does (your spec, numbered to match)

1. Pull every PR targeting the repo's main/master branch — any state (open,
   closed, merged), not just merged.
2. Pull every comment on every one of those PRs — conversation, inline diff,
   review summaries — from any author, human or bot. No filtering.
3. Generate a running document per repo: unique comments, categorized,
   refined on every run.
   1. Refinement = the document gets more complete each run, not a full
      historical re-classification pass (see "Refined ≠ re-scanned" below).
   2. Organized by repository, then by the date each run happened. Each
      entry carries comment text, date, and author.
   3. Read the document first; only pull PRs/comments *after* the last
      recorded cutoff — never reprocess already-captured history.
   4. Newest run at the top of its repo's section.
4. Mine all the captured comments into a code-review skill.
   1. Every run, fold newly-seen unique patterns into that skill.

## How this relates to `comment-refiner`

Same taxonomy (`reference/taxonomy.md` — category × severity), same GitHub
comment sources, same `gh`-CLI-based fetch approach. What's different:

| | `comment-refiner` | `pr-history-agent` (this) |
|---|---|---|
| Scope | One PR/issue, on demand | Every PR on the repo, run repeatedly |
| State | None — stateless triage | Persistent document, resumes from last run |
| Output | Report in chat/PR comment | Growing markdown archive + a generated review skill |
| Trigger | "Triage PR #124" | Run manually or on a schedule; each run picks up where the last left off |

Don't fork the classification logic — point this agent's SKILL.md at
`comment-refiner/reference/taxonomy.md` (or copy it in verbatim and keep the
two in sync) so a comment gets the same category/severity regardless of
which skill classified it.

## Document schema

**One file per repo** (default — see alternative below):
`pr-history/{owner}-{repo}.md`

```markdown
<!-- pr-history-agent:cutoff:2026-08-15T14:32:00Z -->
# PR comment history — framedparadox/portfolio-pulse

## Run: 2026-08-15 — 23 new unique comments (PRs #142–#158)

| Category | Severity | Comment | Author | Date | PR | Seen |
|---|---|---|---|---|---|---|
| security | critical | Null check missing before `user.roles`... | @alice | 2026-08-12 | #150 | 1 |
| nitpick | trivial | "nit: rename to userCount" | @bob | 2026-08-10 | #148, #151, #152, #155 | 4 |

## Run: 2026-08-01 — 847 new unique comments (initial backfill, PRs #1–#141)

| ... |
```

Two dates matter and they're not the same thing:
- **The HTML comment cutoff** (`pr-history-agent:cutoff:...`) is the
  machine-parsed resume marker — the max `created_at` across every comment
  actually captured in the most recent run. Precise to the second, always
  reflects the true last run regardless of section headers below it.
- **The `## Run: DATE`** heading is for humans — when the agent happened to
  run, not when the data ends.

Always update the HTML comment at the very top; always prepend the new
`## Run:` section directly under the H1, above the previous top entry.

**Alternative to consider:** a single multi-repo document with one `##
Repo:` section per repo instead of one file per repo. Functionally
equivalent — pick whichever is easier to read given how many repos you'll
actually point this at. If it's more than ~5 repos, per-file is probably
easier to work with.

## Incremental resume — validated

```bash
REPO="owner/name"
DEFAULT_BRANCH=$(gh repo view "$REPO" --json defaultBranchRef -q .defaultBranchRef.name)
DOC="pr-history/${REPO//\//-}.md"

if [[ -f "$DOC" ]]; then
  CUTOFF=$(grep -m1 -oP 'pr-history-agent:cutoff:\K[0-9T:-]+Z' "$DOC")
  # candidate PRs: anything with new activity since cutoff (covers both
  # brand-new PRs and new comments on old PRs)
  gh pr list --repo "$REPO" --base "$DEFAULT_BRANCH" --state all \
    --search "updated:>=${CUTOFF}" --limit 1000 \
    --json number,title,author,createdAt,updatedAt,mergedAt,state,url
else
  # first run — full backfill, no lower bound
  gh pr list --repo "$REPO" --base "$DEFAULT_BRANCH" --state all \
    --limit 100000 \
    --json number,title,author,createdAt,updatedAt,mergedAt,state,url
fi
```

`--search "updated:>=DATE"` is a real GitHub search qualifier — checked
against a live repo during this build (`repo:cli/cli is:pr
updated:>=2026-08-01` correctly returned only PRs updated on/after that
date). For each candidate PR, fetch its three comment sources (reuse
`comment-refiner/scripts/fetch_comments.sh`) and then filter client-side to
comments where `created_at` is after the cutoff — a PR can be a "candidate"
because of one new comment while still holding plenty of already-captured
older ones.

## Dedup — "unique comments" (assumption, please confirm)

Default: normalize comment body (trim whitespace, strip markdown
formatting) and treat identical normalized text *within the same repo* as
one comment — this is what collapses the same bot boilerplate posted on 50
PRs into a single row with a "Seen" count and the list of PRs it appeared
on. If you'd rather list every occurrence verbatim regardless of
repetition, drop the normalization step — the rest of the design doesn't
depend on it either way.

## Review-skill generation and update loop

This part isn't a script — it's Claude reasoning over the document, because
"is this a genuinely new pattern or a repeat of something already
captured" is a judgment call, not a string match.

Each run, after the document is updated:
1. Look at this run's new unique comments, weighted toward `blocking` /
   `security` / `major` (these represent things the codebase has actually
   gotten wrong, which is exactly what a review skill should pre-empt).
2. Compare against what the review skill already encodes. Genuinely new →
   add a guidance line, citing the PR(s) it came from. Reinforcing an
   existing line → bump a "confirmed again in PR #N" note rather than
   duplicating the guidance.
3. Keep the skill itself lean (progressive disclosure — same principle as
   `comment-refiner`): a short `SKILL.md` with the review workflow, and the
   actual accumulated pattern library in `reference/patterns.md`, grouped by
   category, each entry with a one-line rule plus the PRs that established
   it.
4. Every update is a normal file edit inside a git repo — that's the review
   mechanism. No separate approval gate needed; `git diff` on the skill
   before committing is the check.

**Open question:** one generated review skill per repo (repo-specific
conventions, e.g. this WordPress repo's patterns won't be the same as a
FastAPI one), or one consolidated skill across everything under
framedparadox? Per-repo is the default assumption above — flag it if you'd
rather consolidate.

## Suggested layout

```
pr-history-agent/
├── SKILL.md                      — orchestrates fetch → dedup → document update → skill update
├── scripts/
│   ├── fetch_prs.sh               — the incremental-vs-backfill logic above
│   └── fetch_comments.sh          — same as comment-refiner's, or a symlink/copy
├── reference/
│   └── taxonomy.md                — same content as comment-refiner's (keep in sync)
pr-history/
└── {owner}-{repo}.md              — one generated doc per repo (git-tracked)
{repo}-review/
└── SKILL.md, reference/patterns.md — the generated review skill, one per repo
```

## First prompt for Claude Code

> Read `pr-history-agent-BUILD-BRIEF.md`. Build the `pr-history-agent` skill
> as specified — reuse `comment-refiner/reference/taxonomy.md` rather than
> duplicating it. Start with `<owner>/<repo>` as the first repo to backfill,
> so I can check the document format before you point it at anything else.
