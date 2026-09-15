---
type: object-type-definition
name: project
zone: gtd
location: "initiative, client, or GTD projects/; see workdesk-ontology rule"
shape: container
folder-structure: 8-item
naming: kebab-slug
version: 1.0
---

# Object Type: project

Multi-session operator attention. Bounded outcome with multiple steps and an explicit completion condition. Choose its owner: initiative, client, or personal/standalone GTD. Sustained improvement belongs to an initiative.

## Folder structure (8-item, per per-project-accounting rule)

```
gtd/projects/{slug}/
  brief.md       # Purpose, Principles, Outcome, Vision (POBO output)
  status.md      # Current phase, next action, open items, last_updated
  plan.md         # POBO plan snapshot — phases + intended steps
  notes/          # running captures
  reference/      # source material
  specs/          # build specs
  deliverables/   # final outputs
  _archive/       # retired material
```

Code projects add a 9th item: `repo/`.

## Frontmatter on `brief.md`

```yaml
---
type: project
status: active                              # active | archived | someday
expected-cadence: biweekly                  # weekly | biweekly | monthly | none
last-touched: 2026-04-26
source: "[[...]]"                           # how this project came into being
created: 2026-04-26
last_updated: 2026-04-26
author: claude | operator
---
```

`expected-cadence: none` disables stale-context checks. Default `biweekly`.

## Lifecycle

- Created via `/pobo` (full) or `/pobo --lite` (3-field stub)
- `brief.md` immutable once written; updates flow through `status.md`
- Archive: `mv gtd/projects/{slug} gtd/archive/projects/{year}/{slug}` — agent rewrites inbound `parent:` links in same operation

## Detection

`[REVIEW]` to propose creation when:
- An action created two sessions in a row carries the same parent intention (e.g., "draft proposal for Acme") — propose promotion to project via `/promote-to-project`
- Operator says "I want to start working on X" and X is multi-session

## Matching

- New `brief.md` written → emit `project-created` event
- Status changes update only `status.md`, never `brief.md`
- POBO `plan.md` updates increment `last_updated`

## Navigation and entry points

Every project adds index.md, AGENTS.md, and CLAUDE.md to its existing accounting structure. Read [[../rules/workdesk-ontology]] for all supported homes and compatibility rules.
