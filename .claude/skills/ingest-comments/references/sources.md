# Normalized comment record

Each ingested comment is written as one JSON object per line in `comments.jsonl`.

Required identity fields:

- `id` — `{provider}:{owner/repo}:pr:{n}:{kind}:{native_id}`
- `provider` — `github` | `gitlab` | `bitbucket` | `gitea` | `local`
- `host`, `repo`, `pr_number`, `kind`, `created_at`, `body`

Provenance fields (kept even when the account is later deactivated):

- `author` (falls back to `ghost`)
- `author_type` — `user` | `bot` | `deleted`
- `path`, `line`, `side`, `thread_id`, `url`, `in_reply_to`

See [comment-record.schema.json](comment-record.schema.json).
