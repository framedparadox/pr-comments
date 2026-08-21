# Pattern library

This file is maintained by `generate-skills`. New evidence is merged into existing pattern ids; the section below is never replaced wholesale.

## Patterns

<!-- comment-intel:pattern:security:secret-or-auth -->
### security: secret-or-auth
- **Category:** security
- **Priority:** P0
- **Actionable:** yes
- **Rule:** Never merge secrets, tokens, or broken authz checks. Treat auth bypass and leaked credentials as P0.
- **Anti-pattern:** Hard-coded tokens, missing authorization on new endpoints, trusting client-supplied roles.
- **Examples:**
  - Token or password committed in source
  - Missing authorization on a new route
- **Provenance:** seed
- **Confirmed in:** —
- **Seen:** 0

<!-- comment-intel:pattern:correctness:logic-bug -->
### correctness: logic-bug
- **Category:** correctness
- **Priority:** P1
- **Actionable:** yes
- **Rule:** Guard nullable values and reject changes that reintroduce crash paths reviewers have already flagged.
- **Anti-pattern:** Member access on values that can be null/undefined; unvalidated input reaching business logic.
- **Examples:**
  - Null check missing before nested field access
- **Provenance:** seed
- **Confirmed in:** —
- **Seen:** 0

## User customizations
