---
name: commit-hooks
description: Install and reason about git-native hooks and Claude Code hooks that enforce Conventional Commits and warn or block when comment-intelligence P0 findings are unresolved. Use when setting up pre-commit, Lefthook, commit-msg, or agent PreToolUse hooks around git commit and git push.
metadata:
  version: "1.0.0"
  author: framedparadox
---

<!-- comment-intel:generated:true -->

# commit-hooks

Two complementary layers. Offer both; do not install silently.

## Git-native hooks

Work for humans, CI, and every agent. Prefer **Lefthook** in polyglot repos or **pre-commit** when Python is already the toolchain. Husky only if the repo is already JS-native.

Minimum `commit-msg` policy: Conventional Commits type prefix.

Optional `pre-push` policy: if `.comment-intelligence/repos/*/unique.json` contains actionable `P0` items, print them and fail unless `COMMENT_INTEL_ALLOW_P0=1`.

Example Lefthook snippet (do not apply without confirmation):

```yaml
# lefthook.yml
commit-msg:
  commands:
    conventional:
      run: grep -qE '^(feat|fix|docs|refactor|test|chore|perf|ci|build)(\(.+\))?: .+' {1}
pre-push:
  commands:
    p0-gate:
      run: python3 .agents/skills/ingest-comments/scripts/ingest.py --help >/dev/null
```

For a real P0 gate, query `unique.json` rather than calling ingest. A one-liner:

```bash
python3 -c "import json,glob,sys; hits=[u for p in glob.glob('.comment-intelligence/repos/*/unique.json') for u in json.load(open(p)) if u.get('priority')=='P0' and u.get('actionable')];
sys.exit(1 if hits else 0)"
```

## Claude Code / agent hooks

Agent-scoped complement, not a replacement. Example skill-frontmatter or `.claude/settings.json` matcher: `PreToolUse` on `Bash(git push *)` — if unique.json has unresolved P0, deny with the list so the agent can fix or explain.

Do not block a human `git push` via agent hooks; that is what git-native hooks are for.

## Pattern library

Repo-specific hook triggers mined from comments live in [references/patterns.md](references/patterns.md).

## User customizations

Record the chosen hook framework and any local exceptions below. generate-skills will preserve them.
