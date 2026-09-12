# GitHub comment sources

Git stores no pull request comments. This skill always talks to the GitHub API (`gh` preferred, otherwise `GH_TOKEN` / `GITHUB_TOKEN`).

| Kind | Endpoint | Notes |
| --- | --- | --- |
| Conversation | `/repos/{owner}/{repo}/issues/comments` | PR discussion tab. Kept only if the issue number is a PR targeting the base branch. |
| Inline review + replies | `/repos/{owner}/{repo}/pulls/comments` | Diff comments. `in_reply_to_id` marks replies; `commit_id` / `original_commit_id` are populated. |
| Review summary | `/repos/{owner}/{repo}/pulls/{n}/reviews` | Review body text. Empty “reviewed” events are skipped. `commit_id` is the review head. |

Deactivated users: GitHub returns `"user": null`. Map to `comment_by=ghost`, `author_type=deleted`. Never drop the row.

Credentials:

| Tool | When |
| --- | --- |
| `gh` CLI | Preferred. Reuses `gh auth login`. |
| `GH_TOKEN` / `GITHUB_TOKEN` | REST fallback, including GitHub Enterprise via `--host`. |
