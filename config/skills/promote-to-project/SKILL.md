---
name: promote-to-project
description: Upgrade an action in gtd/actions/ into a full project folder under gtd/projects/. Re-runs the relevant POBO phases minimally and rewrites references.
---

# /promote-to-project

The "default to action" rule says: when ambiguous, create an action; promote later if it earns it. This skill is the promotion path.

## Invocation

- `/promote-to-project {action-slug}` — promote a specific action
- `/promote-to-project --auto` — scan `gtd/actions/` for actions older than 14 days with multiple touch events; propose candidates

## Phases

### 1. Read the action

Read `gtd/actions/{slug}.md`. Note `parent:`, `source:`, body description.

### 2. Confirm target

All promotions land at `{project-home}/{slug}/`. Projects live in GTD; there is no separate atlas-side initiative folder.

### 3. Run mini-POBO

Walk the operator through a compressed POBO:

- **Outcome** — what does success look like? (Carry over from action body if explicit.)
- **Principles** — any non-negotiables? (May be empty.)
- **Brainstorm** — what else needs to happen beyond the next action?
- **Organize** — what are the 2-5 phases? Which is current?

Confirm whether to use `--lite` shape (3 fields only) or full POBO.

### 4. Scaffold

Create the 8-item folder under `{project-home}/{slug}/`. Populate `brief.md`, `status.md`, `plan.md` from the mini-POBO output. The promoted action is the current next action; carry it into `status.md`.

Frontmatter on `brief.md`: `expected-cadence: biweekly`.

### 5. Rewrite the original action

The original `gtd/actions/{slug}.md` becomes a child of the new project:
- Update `parent:` to point at the new `brief.md`
- Keep `source:` as-is

### 6. Rewrite inbound references

Find any other notes referencing the original action via `[[...]]` and update them to reference the new `brief.md` if the original meaning was "the project this action belongs to" rather than "this specific action." Operator confirms ambiguous cases.

### 7. Log

Hooks fire `project-created` automatically. No manual logging.

## What NOT to do

- Don't promote actions younger than ~7 days unless the operator explicitly asks. The default-to-action principle is intentional.
- Don't drop the original action. The promoted action is the project's first next action.

## Project home and navigation

Use config/rules/workdesk-ontology.md. Choose the owning initiative or client when established; otherwise use gtd/projects for personal/standalone work. Preserve unassigned existing business project homes. Add index.md, AGENTS.md and CLAUDE.md with pointers to the shared policy and the real brief/status. An initiative adds projects/; a project does not. Do not infer business ownership.
