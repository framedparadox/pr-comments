---
name: code-review
description: Review code changes using recurring patterns mined from this repository's pull request and merge request comment history. Use when reviewing a diff, a PR/MR, or staged changes, or when the user asks for a code review that should match prior reviewer feedback.
metadata:
  version: "1.0.0"
  author: framedparadox
---

<!-- comment-intel:generated:true -->

# code-review

Review the current diff the way this repo's reviewers actually comment — not a generic style guide.

## Workflow

1. Read [references/patterns.md](references/patterns.md). Prefer `P0`/`P1` and `security` / `correctness` rules.
2. Inspect the change (`git diff`, the PR, or the files the user named).
3. For each matching anti-pattern, comment with: category, priority, path/line, why it failed, and the provenance PRs that established the rule.
4. Do not restate nits already fixed in the diff. Do not invent rules that are not in the pattern library or `## User customizations`.
5. If comment intelligence artifacts exist under `.comment-intelligence/repos/`, skim open P0/P1 uniques before finishing.

## Output

Group findings P0 → P3. Mark each as blocking or non-blocking. Cite pattern ids (`category:subcategory`).

## User customizations

Add repo-specific review exceptions below this heading. generate-skills will preserve them.
