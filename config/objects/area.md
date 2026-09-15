---
type: object-type-definition
name: area
zone: atlas
location: atlas/areas/
shape: container
folder-structure: 4-item
naming: kebab-slug
version: 1.0
---

# Object Type: area

Standing responsibility that isn't relationship-shaped. Permanent until retired. Universal — every persona uses areas. Recurring maintenance for an area lives in `gtd/recurring/`, not as projects.

Examples by persona:
- consultant: client-independent admin (finance, pipeline, health)
- founder: hiring, runway, legal, ops
- employee: role, career, team, manager relationship
- researcher: methods, teaching, reading, lab ops
- creative: studio, audience, publishing
- parent: household, family, school, health

## Folder structure (4-item)

```
atlas/areas/{slug}/
  brief.md       # what this area covers, why it's a standing concern
  status.md      # current state, recent activity, open threads
  notes/          # ongoing observations
  _archive/       # retired material
```

## Frontmatter on `brief.md`

```yaml
---
type: area
status: active                              # active | retired
expected-cadence: weekly                    # default weekly; "none" disables stale checks
last-touched: 2026-04-26
source: "operator-instruction"
created: 2026-04-26
last_updated: 2026-04-26
author: claude | operator
---
```

## Lifecycle

- Created during `/onboarding` Phase 3 (always, regardless of role mix)
- Retired via status flip to `retired` — folder stays in place, dropped from active scans
- Areas are permanent by default — don't archive eagerly

## Detection

Areas are operator-named during onboarding. After onboarding, propose new areas via `[REVIEW]` only when:
- Recurring items (`gtd/recurring/`) accumulate without an area parent
- Multiple `gtd/projects/` over time share the same standing-concern theme (e.g., 3 projects under `health`)
- Confidence ≥0.7

## Matching

- New `brief.md` → emit `object-created`
- Recurring items SHOULD set `parent:` to the area's `brief.md`
