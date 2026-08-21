# Pattern library

This file is maintained by `generate-skills`. Recurring comments that should fail a hook (P0 security/correctness) or a commit-msg check land here.

## Patterns

<!-- comment-intel:pattern:security:secret-or-auth -->
### security: secret-or-auth
- **Category:** security
- **Priority:** P0
- **Actionable:** yes
- **Rule:** Block push when unique.json still lists actionable P0 secret or authz comments that this branch did not address.
- **Anti-pattern:** Pushing while a P0 security thread is open.
- **Examples:**
  - Unresolved credential leak comment
- **Provenance:** seed
- **Confirmed in:** —
- **Seen:** 0

## User customizations
