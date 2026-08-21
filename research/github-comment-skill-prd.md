# Comment Refiner — a skill system for triaging GitHub PR/issue comments

**Status:** Phase 0 (research + plan) complete · Phase 1 (skill scaffold) delivered
**Owner:** Ak / Framed Paradox
**Date:** 2026-08-11

---

## 1. What this is

A Claude Agent Skill (`comment-refiner`) that pulls every comment off a GitHub
pull request or issue — conversation comments, inline diff comments, review
summaries — and turns them into a prioritized, actionable report: what's
blocking merge, what's a nice-to-have, what's just noise.

It's designed to manage two companion skills as part of its own operation:

- **`git-checkin`** — structured, traceable commit messages (which review
  comments did this commit address?), optionally gated on outstanding
  blockers.
- **`commit-hooks`** — automated enforcement, both as git-native hooks
  (work regardless of which tool touches the repo) and as Claude Code hooks
  (agent-level automation scoped to Claude's own tool calls).

On invocation, `comment-refiner` checks whether these two exist yet in the
skills directory; if not, it offers to scaffold them; if they do, it diffs
against its bundled reference copy and offers to update rather than
duplicating. See §5.4.

## 2. Scope & assumptions (stated up front — flag anything wrong)

- **"Comments" = discussion/review comments** (PR conversation, inline diff
  comments, review-summary bodies), not in-repo `TODO`/`FIXME` source
  comments. Those are a plausible Phase 5 add-on (§7) but a genuinely
  different extraction path (`grep`/`ripgrep` over files, not the GitHub API),
  so keeping them separate avoids conflating "what a person said about this
  code" with "what a person wrote inside this code."
- **GitHub is the primary target.** "Other similar repositories" (GitLab,
  Bitbucket, Gitea) is handled by keeping the fetch layer behind a thin
  adapter interface so a second backend is a new adapter, not a rewrite —
  not built in Phase 1.
- **Delivered as an Anthropic Agent Skill** (the `SKILL.md` format), so it
  runs in Claude Code, Claude.ai, and the API without modification.
- **Auth via the `gh` CLI**, reusing whatever session `gh auth login` already
  has, rather than the skill managing its own PAT/OAuth flow.

## 3. Prior art

Nothing here does exactly this end-to-end (extract → classify by
category *and* severity → manage its own companion tooling), but three
adjacent patterns are well established and worth borrowing from directly
rather than re-inventing.

### 3.1 Comment/commit labeling conventions

| Convention | Standardizes | Categories | Severity signal |
|---|---|---|---|
| [Conventional Comments](https://conventionalcomments.org/) | Review comment format: `<label> [decorations]: <subject> [discussion]` | `praise`, `nitpick`, `suggestion`, `issue`, `question`, `thought`, `todo`, `chore` | decorations: `(blocking)`, `(non-blocking)`, `(if-minor)` |
| [Conventional Commits](https://www.conventionalcommits.org/) | Commit message format: `<type>(<scope>): <description>` | `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `ci`, `build` | `BREAKING CHANGE` footer only |

Conventional Comments is the closest existing spec to "categories with
levels of importance" — it's plain-text, tool-free, and already
machine-parseable (the spec's own examples show it serialized straight to
JSON). The taxonomy below is a superset of it, adding an explicit severity
axis that Conventional Comments only gestures at through decorations.

### 3.2 Automated / AI PR-review tools

| Tool | License | Categorization approach |
|---|---|---|
| [PR-Agent](https://github.com/The-PR-Agent/pr-agent) | Apache 2.0, community-owned (transferred out of Qodo, April 2026) | Slash-command review (`/review`, `/improve`); config-driven severity thresholds (blocking / warning / advisory) |
| Qodo (commercial evolution of PR-Agent) | Commercial | Every finding ranked by severity, "Action Required" vs "Informational" thresholds, generates fix-ready prompts per finding |
| [Danger](https://danger.systems/) | MIT | Rule-as-code: `message()` / `warn()` / `fail()` — a genuine 3-tier severity model, just expressed as function calls instead of labels |
| [reviewdog](https://github.com/reviewdog/reviewdog) | MIT | Wraps any linter's output as inline PR comments; severity = the linter's own `info` / `warning` / `error`, passed through its `rdjson` format |

The common thread: every serious tool in this space treats **severity as a
first-class, separate axis from category** — "what kind of comment" and
"how urgent" are different questions, and conflating them (e.g. one big list
of labels ordered loosely by importance) is what makes ad hoc PR feedback
hard to triage in the first place. That's the main design lesson carried
into §4.

### 3.3 The Claude Skill layer

- [Anthropic's Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
  use **progressive disclosure**: `name` + `description` (~100 tokens) stay
  loaded at all times; the `SKILL.md` body (keep under ~500 lines / 5,000
  tokens) loads only when the description matches the task; anything in
  `scripts/`, `reference/`, or `assets/` loads only when the body actually
  points to it. This is why `comment-refiner` ships a short `SKILL.md` plus
  a separate `reference/taxonomy.md` instead of one long file.
- The format is an [open standard](https://agentskills.io/specification)
  (portable to Codex, Gemini CLI, and others), with required frontmatter
  `name` + `description` and optional `license`, `compatibility`, `metadata`,
  `allowed-tools`.
- Anthropic's own [`anthropics/skills`](https://github.com/anthropics/skills)
  repo ships a `skill-creator` example skill — worth a look before iterating
  further on this one, since it encodes Anthropic's own authoring checklist.
- **Claude Code hooks are their own, separate, well-developed feature** —
  not to be confused with git hooks. They're configured either in
  `.claude/settings.json` (project/user/org-wide) or **directly in a skill's
  own YAML frontmatter**, scoped to that skill's lifetime. Events include
  `PreToolUse` (can block a tool call outright — e.g. block `git push` while
  `critical` comments are unresolved), `PostToolUse`, `UserPromptSubmit`,
  `Stop`, and about 30 others. This second option — hooks embedded straight
  into a skill's frontmatter — is a genuinely good fit for `commit-hooks`
  and is detailed in §5.3.

### 3.4 Git-native hook frameworks

For enforcement that has to hold regardless of which tool (Claude, a human,
CI) touches the repo, three frameworks dominate: **pre-commit** (Python,
language-agnostic, largest library of ready-made hooks, steeper setup),
**Husky** (JS-native, simplest if the repo already has `package.json`),
**Lefthook** (Go, fastest, parallel execution, no runtime dependency, works
in polyglot repos without adding npm infra). Given your repos span Python
(FastAPI) and JS/TS, **pre-commit or Lefthook are the better defaults** —
Husky makes sense only for the purely-JS projects.

---

## 4. Proposed taxonomy

Two independent axes, plus an optional lifecycle status. Independent means a
comment is always tagged with exactly one of each — a `nitpick` can't be
`critical` (if it's critical it's not a nitpick, by definition), but
`suggestion` × `major` is a normal, valid combination.

### 4.1 Category — *what kind of comment*

| Category | Meaning |
|---|---|
| `blocking` | Must be resolved before merge — broken logic, failing requirement |
| `security` | Security-relevant; always surfaced separately even if it's also `blocking`, so it can't get buried in a long list |
| `performance` | Perf-relevant, not necessarily blocking |
| `suggestion` | Improvement idea, not mandatory |
| `nitpick` | Trivial style/preference — safe to ignore |
| `question` | Needs an answer, not necessarily a code change |
| `chore` | Small required housekeeping (rebase, changelog, add a test) |
| `praise` | Positive feedback — kept visible on purpose; it's the first thing that gets lost in a wall of critique |
| `discussion` | Open design conversation, no single resolution expected |

### 4.2 Severity — *how urgent*

| Severity | Meaning |
|---|---|
| `critical` | Security vulnerability, data loss, breaks build/prod |
| `major` | Real bug or significant design flaw |
| `minor` | Small bug or edge case, limited blast radius |
| `trivial` | Style/wording only |

### 4.3 Status — *lifecycle (optional, useful once you're tracking over time)*

`open` → `addressed` / `wontfix` / `needs-discussion`

### 4.4 Rendered format

Borrowing Conventional Comments' `label [decorations]: subject` shape,
adapted to two axes:

```
🔴 [blocking · critical] pulls/comments#48212 — auth.py:112
   Null check missing before `user.roles` access; will 500 on anonymous
   requests. — @reviewer

🟡 [suggestion · minor] issues/comments#9931
   Consider extracting this into a helper — three call sites now
   duplicate the same 6 lines. — @reviewer
```

---

## 5. Architecture

```
GitHub PR / Issue
   │  gh api repos/{o}/{r}/issues/{n}/comments        (conversation)
   │  gh api repos/{o}/{r}/pulls/{n}/comments          (inline diff comments)
   │  gh api repos/{o}/{r}/pulls/{n}/reviews           (review summaries)
   ▼
scripts/fetch_comments.sh  →  one normalized JSON array
   ▼
Claude reads reference/taxonomy.md, classifies each comment
   (category × severity, using diff context — path/line — where available)
   ▼
Refined report (grouped by severity, then category; duplicates collapsed)
   ▼
   ├─→ single summary comment posted back to the PR   (gh pr comment)
   ├─→ Linear issues for blocking/critical items        (you already run
   │                                                      projects in Linear)
   └─→ Slack ping for critical items                    (matches your
                                                           existing alert
                                                           pattern)
```

*(See the architecture diagram in the chat response for the visual version
of this, including how `comment-refiner` relates to its two companions.)*

### 5.1 `comment-refiner` (this skill — **delivered in Phase 1**, see §8)

Fetch → classify → refine → report, plus the "offer, don't auto-act" output
integrations above.

### 5.2 `git-checkin` (Phase 2 — **designed, not yet built**)

Conventional-Commits-formatted commit messages, generated from the staged
diff, with an optional trailer linking back to which review-comment IDs the
commit addresses (traceability from feedback → fix). Can consult
`comment-refiner`'s last output and warn (not silently block) if `critical`
items are still open.

### 5.3 `commit-hooks` (Phase 2/3 — **designed, not yet built**)

"Hook" is genuinely ambiguous between two real, non-overlapping mechanisms —
this skill should offer both and let you pick per-repo:

- **Git-native hooks** (via pre-commit or Lefthook — see §3.4): enforce a
  Conventional Commits `commit-msg` format, run regardless of which tool
  touches the repo, work for human contributors too.
- **Claude Code hooks**, defined either in `.claude/settings.json` or
  directly in `commit-hooks`' own frontmatter (see §3.3) — e.g. a
  `PreToolUse` hook matched on `Bash(git push *)` that shells out to check
  for unresolved `critical`-severity comments and denies the push with a
  reason Claude can see and act on. This is agent-scoped: it fires for
  Claude's own tool calls, not for a human running `git push` directly, so
  it's a complement to the git-native hook, not a replacement for it.

### 5.4 Self-update / idempotency design

Each skill in the trio carries a `version` field in `metadata` (frontmatter)
and a `CHANGELOG.md`. On invocation, before scaffolding a companion skill,
`comment-refiner` checks whether one already exists at the target path:

- **Absent →** offer to create it (never silently).
- **Present →** diff the bundled reference copy against what's on disk;
  anything under a `## User customizations` heading in the existing file is
  preserved verbatim; everything else is offered as an update, not applied
  automatically.

"Keep refining" is deliberately **not** fully autonomous self-modification —
a `reference/REFINEMENT_LOG.md` records edge cases the classifier got wrong
(logged by you, or by Claude noticing a pattern), and taxonomy changes get
proposed against that log for you to accept, rather than the skill silently
rewriting its own instructions. Skills that quietly rewrite the rules
they're graded against are a bad pattern to build into something that gates
your own commits.

## 6. Output integrations (all opt-in, confirmed before acting)

- **Post-back:** one summary comment on the PR (`gh pr comment`), not one
  comment per finding — matches how Danger/reviewdog avoid spamming a PR.
- **Linear:** create/update issues for `blocking`/`critical` items. You're
  already running Linear-tracked projects for other tooling, so this is a
  natural sink for anything that needs to survive past the PR being closed.
- **Slack:** notify on `critical` only, via webhook — same shape as the
  alert path in the Portfolio Pulse stock-alert PRD.

## 7. Roadmap

- [x] **Phase 0** — research + this plan
- [x] **Phase 1** — `comment-refiner` scaffold: `SKILL.md`,
      `reference/taxonomy.md`, `scripts/fetch_comments.sh` (delivered below)
- [ ] **Phase 2** — output integrations (PR post-back, Linear, Slack) +
      `git-checkin` skill
- [ ] **Phase 3** — `commit-hooks` skill (git-native + Claude Code hooks)
- [ ] **Phase 4** — self-refinement loop (`REFINEMENT_LOG.md`, versioning,
      idempotent re-scaffold logic in practice, not just designed)
- [ ] **Phase 5 (stretch)** — GitLab/Bitbucket adapters; optional in-repo
      `TODO`/`FIXME` extraction as a second, clearly-separate source

## 8. What's actually in this delivery

```
comment-refiner/
├── SKILL.md                    — triggers, workflow, output format, companion-skill management
├── reference/
│   └── taxonomy.md             — full category/severity definitions + few-shot classification examples
└── scripts/
    └── fetch_comments.sh       — gh + jq: pulls & normalizes all three comment sources into one JSON array
```

Zipped as `comment-refiner.zip` — unzip into `.claude/skills/` (personal) or
`.claude/skills/` at the project root (shareable, commit it) and it's live
next session. `fetch_comments.sh` was checked against a live GitHub API
response during this build (field names for `.user.login`, `.body`,
`.html_url`, `.created_at` confirmed against `issues/comments`).

## 9. Open decisions for you

- [ ] `commit-hooks`: git-native, Claude Code hooks, or both? (default plan
      above is "both, configurable per-repo")
- [ ] Auto-post the refined summary back to the PR by default, or keep it
      local-only until asked?
- [ ] Sync `blocking`/`critical` items to Linear automatically, or only on
      request?
- [ ] This will likely live in a `framedparadox` repo — apply your existing
      proprietary `LICENSE.md` convention to it?
- [ ] Working name is `comment-refiner`. "Marginalia" was the other
      candidate that came up — closer to the brand voice (comments as
      notes in the margin), if you'd rather rename before this goes further.

## References

- Conventional Comments — https://conventionalcomments.org/
- Conventional Commits — https://www.conventionalcommits.org/
- PR-Agent (open source) — https://github.com/The-PR-Agent/pr-agent
- Danger — https://danger.systems/
- reviewdog — https://github.com/reviewdog/reviewdog
- Anthropic Agent Skills overview — https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview
- Agent Skills open specification — https://agentskills.io/specification
- Anthropic's public skills repo (incl. `skill-creator`) — https://github.com/anthropics/skills
- Claude Code hooks reference — https://code.claude.com/docs/en/hooks
- GitHub REST API — issue comments — https://docs.github.com/en/rest/issues/comments
- GitHub REST API — PR review comments — https://docs.github.com/en/rest/pulls/comments
- GitHub REST API — PR reviews — https://docs.github.com/en/rest/pulls/reviews
