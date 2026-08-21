# Comment taxonomy

Two independent axes plus tags. Every unique comment gets exactly one category, one subcategory, one priority, an actionable flag, tags, and provenance.

Conventional Comments labels (`praise`, `nitpick`, `suggestion`, `issue`, `question`, `thought`, `todo`, `chore`) are **tags**, not categories. Decorations such as `(blocking)` inform priority.

## Categories

| Category | Use when the comment is mainly about |
| --- | --- |
| `correctness` | Logic bugs, validation, races, crashes, API contracts |
| `security` | Authn/z, injection, secrets, XSS/CSRF, untrusted input |
| `performance` | Latency, N+1, allocations, caching, hot paths |
| `maintainability` | Duplication, complexity, naming that blocks change |
| `architecture` | Boundaries, layering, coupling, module direction |
| `testing` | Missing, flaky, or weak tests |
| `documentation` | Docs, comments, READMEs, public API wording |
| `style` | Formatting, import order, nits with no behavior change |
| `UX` | Accessibility, copy, layout, interaction |
| `workflow` | CI, git process, changelogs, bots, merge hygiene |
| `clarification` | Questions or open discussion with no clear change yet |

## Priority

| Level | Meaning |
| --- | --- |
| `P0` | Critical: vuln, data loss, prod outage, secret leak |
| `P1` | High: real bug or merge-blocking design flaw |
| `P2` | Medium: should-fix, limited blast radius |
| `P3` | Low: nit, optional, style, praise |

Map informal severity: critical→P0, major→P1, minor→P2, trivial→P3.

## Actionable

`true` when a code, test, docs, or process change is expected. Praise is not actionable. Pure questions are actionable only if they request a reply or clarification in-repo.

## Subcategory

Short kebab-case hint used as the derived-skill pattern id suffix (`null-check`, `missing-test`, `bot-report`, …). Heuristic only; agents may rename low-confidence values.

## Few-shot

`Null check missing before user.roles access; will 500 on anonymous requests.`
→ category `correctness` (also tag `security` if authz-related), subcategory `null-check`, priority `P1`, actionable `true`.

`nit: rename to userCount`
→ category `style`, tag `nitpick`, priority `P3`, actionable `true`.

`Consider extracting this helper — three call sites duplicate the same 6 lines.`
→ category `maintainability`, tag `suggestion`, priority `P2`, actionable `true`.

`**LGTM** nice tests`
→ category `clarification`, tag `praise`, priority `P3`, actionable `false`.

## Stability

Never reclassify an existing `dedup_key`. Only new unique comments go through the heuristic (or an agent override). Log agent overrides in the report's `## User customizations` section if you change a label by hand.
