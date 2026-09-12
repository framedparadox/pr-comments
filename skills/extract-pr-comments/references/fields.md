# CSV and JSON fields

`comments.csv` columns (Excel-safe UTF-8 with BOM):

| Column | Meaning |
| --- | --- |
| `repo` | `owner/name` |
| `pr_number` | Pull request number |
| `pr_title` | Title at extract time |
| `pr_state` | `open`, `closed`, or `merged` |
| `pr_created_at` | When the PR was opened (the “date” of the PR) |
| `pr_merged_at` | Merge timestamp, if any |
| `pr_author` | PR author (`ghost` if the account is gone) |
| `commit_id` | SHA the comment is attached to (inline/review). Empty for conversation comments. |
| `original_commit_id` | SHA when an inline comment was first posted |
| `comment_date` | When the comment was created |
| `comment_updated_at` | Last edit |
| `comment_by` | Comment author. `ghost` for deactivated accounts |
| `author_type` | `user`, `bot`, or `deleted` |
| `comment_kind` | `conversation`, `inline_review`, or `review_summary` |
| `is_reply` | True when `in_reply_to` is set |
| `in_reply_to` | Parent inline-comment id |
| `thread_id` | Root of the inline thread |
| `path` / `line` / `side` | Diff location for inline comments |
| `comment` | Full comment body |
| `comment_url` | GitHub HTML URL for the comment |
| `pr_url` | GitHub HTML URL for the pull request |

JSON/JSONL also include `id`, `provider`, `host`, `native_id`, `pr_head_sha`, `merge_commit_sha`, and `diff_hunk`.
