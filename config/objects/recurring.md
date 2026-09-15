---
type: object-type-definition
name: recurring
zone: gtd
location: gtd/recurring/
shape: atomic
naming: kebab-slug
version: 1.0
---

# Object Type: recurring

Repeating commitment. Two shapes — schedule (cadence-bound) and checklist (procedure, not cadence-bound). Lives in `gtd/recurring/schedules/` or `gtd/recurring/checklists/`.

## Schedule format

```yaml
---
type: recurring
shape: schedule
status: active                                          # active | paused | retired
cadence: weekly                                         # daily | weekly | monthly | quarterly | yearly | custom
next_due: 2026-05-01
parent: "[[gtd/projects/website-rebuild/brief]]"       # project, operator-added container, or empty
source: ""
created: 2026-04-26
---
Weekly school logistics review — confirm pickups, lunches, after-school.
```

## Checklist format

```yaml
---
type: recurring
shape: checklist
status: active
parent: "[[atlas/areas/publishing/brief]]"
source: ""
created: 2026-04-26
---
# Publish workflow

- [ ] Final read-through
- [ ] Run spellcheck
- [ ] Generate share image
- [ ] Schedule social posts
- [ ] Cross-post to mailing list
```

## Lifecycle

- **Schedule promotion** — operator-confirmed (or auto when `cadence: daily` and operator opts in). Creates a transient action in `gtd/actions/` with `parent: "[[gtd/recurring/schedules/{slug}]]"`. Action completion rolls `next_due` forward by the cadence.
- **Checklist materialization** — operator runs `/checklist {slug}`. Materializes each item as a sequence of actions in `gtd/actions/` with `parent: "[[gtd/recurring/checklists/{slug}]]"`.
- **Pause** (`status: paused`) — drops out of all scans; `next_due` does not roll. Resume by setting `status: active`.
- **Retire** (`status: retired`) — terminal; drops out of all scans permanently. File stays in place for history; not moved to archive in V1.

## Filters used by signals

- `weekly-review` — `status: active` AND `next_due <= today + 7d`
- `daily-plan` — `status: active` AND `next_due <= today`
- `vault-improvements` — `status: active` AND `next_due` past today by > one cadence interval (overdue)

## Detection

`[REVIEW]` proposal when:
- The same task description appears in transcripts on a regular cadence (e.g., "weekly payroll" mentioned in 3 consecutive Mondays)
- Confidence ≥0.7
