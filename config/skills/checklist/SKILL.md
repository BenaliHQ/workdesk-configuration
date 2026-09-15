---
name: checklist
description: Materialize a recurring checklist (gtd/recurring/checklists/) as a sequence of actions in gtd/actions/. Each step becomes its own action with parent pointing back at the checklist. Use when running a procedure like a publish workflow or expense close.
---

# /checklist

Recurring checklists are templates. This skill stamps them out as actions.

## Invocation

- `/checklist {slug}` — materialize the checklist at `gtd/recurring/checklists/{slug}.md`
- `/checklist {slug} --resume` — find existing in-progress materialization and skip already-completed items

## Phases

### 1. Read the checklist

Read `gtd/recurring/checklists/{slug}.md`. Verify `status: active`. Read the body — each `- [ ] item` becomes one action.

### 2. Decide parent for materialized actions

Default: `parent: "[[gtd/recurring/checklists/{slug}]]"`. If the operator passes a specific project context, override.

### 3. Materialize

For each unchecked item, create:

`gtd/actions/{slug}-{step-slug}-{YYYY-MM-DD}.md`

```yaml
---
type: action
status: next
context: []
parent: "[[gtd/recurring/checklists/{slug}]]"
source: "[[gtd/recurring/checklists/{slug}]]"
created: 2026-04-26
---
{step-text}
```

Items already checked `- [x]` are skipped (or all-resumed if `--resume`).

### 4. Surface

Print to chat:
- Number of actions created
- Paths
- Suggested execution order (top to bottom of checklist)

### 5. No checklist mutation

Do NOT modify the checklist file itself. Materialization is a copy operation — the source template stays unchanged.

## What NOT to do

- Don't materialize a `status: paused` or `status: retired` checklist. Tell the operator and stop.
- Don't write inside `gtd/recurring/checklists/`. The checklist is the source of truth; actions are the executions.
- Don't deduplicate against existing materialized actions unless `--resume`. Two runs in one day produce two sets of actions; that's intentional.
