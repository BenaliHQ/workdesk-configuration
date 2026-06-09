---
type: object-type-definition
name: action
zone: gtd
location: gtd/actions/
shape: atomic
naming: kebab-slug
version: 1.0
---

# Object Type: action

Single-session unit of work. The atom of GTD. Anything multi-session is a project at `gtd/projects/`.

## Format

```yaml
---
type: action
status: next                                           # next | waiting | someday | done
context: [work, calls, errands]                        # GTD context tags
parent: "[[gtd/projects/acme-corp-msa-review/_brief]]" # polymorphic, see below
waiting-on: "[[atlas/people/...]]"                     # only if status: waiting
source: "[[atlas/meetings/2026-04-22-acme-corp-weekly]]"  # logged session OR processed material
created: 2026-04-26
---
```

Body: one paragraph — what needs to happen and why. Outcomes-shaped, not vague.

## Polymorphic `parent:`

One field, points to whatever owns the action. Allowed:

- `[[gtd/projects/{slug}/_brief]]` — multi-session project
- `[[gtd/recurring/schedules/{slug}]]` — promoted from recurring
- empty string — standalone

If the operator has added other container types via `/define-object` (e.g. `atlas/areas/`, `atlas/clients/`), wikilinks to those `_brief` notes are also valid `parent:` values. Claude dereferences the link to figure out the parent's type — no schema updates needed when new container types ship.

## Lifecycle (status changes = file moves)

- `next/` → `waiting/` → `gtd/archive/actions/{YYYY-MM}/`
- Agent moves files programmatically; operator drags in Obsidian
- On move out of `next/` or `waiting/` into `archive/actions/`, hook emits `action-completed`

## Detection

Surface `[REVIEW]` proposals to create an action when:
- Processing a transcript and a sentence contains a clear ask directed at the operator ("the operator will send the proposal", "I need to follow up with X")
- Confidence ≥0.7 (per inbox flood guard)
- Below threshold: ask inline or stay silent

## Matching

When an action is created from a transcript:
- Update the transcript's `processed-into:` backlink list
- If `parent:` resolves to an active project, surface in that project's next `_status.md` update
