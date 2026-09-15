---
name: create-spec
description: Guided spec authoring for builds and deliverables. Produces a spec another agent (or Claude in a later session) can execute against. Use when /pobo produces a deliverable that needs more granularity, or when an operator wants to hand off a build.
---

# /create-spec

A spec is a contract between planner and builder. It must be executable without follow-up questions.

## When to run

- A `/pobo` Organize phase produces a deliverable described in 1-2 sentences but with implementation vague
- The operator wants to hand off to another session, agent, or person
- A project's `status.md` lists "spec needed" as the next action

## Detection clause

Surface proactively when:
- A `/pobo` Organize phase names a deliverable without acceptance criteria
- The operator says "I want to build X" without specifying success criteria

Ask: *"Want me to spec this before we build? It'll take 5 minutes and means the build can run unattended."*

## Phases

### 1. Anchor

Read the project's `brief.md`, `status.md`, and `plan.md`. The spec lives downstream — link, don't restate.

### 2. Interview

In order:

1. **Deliverable** — one sentence
2. **Location** — vault path, repo path, or external
3. **Success** — acceptance criteria (each independently verifiable)
4. **Inputs** — sources, references, prerequisites
5. **Out of scope** — bullet list
6. **Constraints** — time, format, voice, dependencies
7. **Review** — who, how

### 3. Draft

Write to `{project-path}/specs/{slug}.md`:

```yaml
---
type: spec
project: {project-name}
status: ready
created: 2026-04-26
deliverable: {one-sentence}
version: 1.0
---
```

Body sections:
- Deliverable
- Location
- Acceptance criteria (bulleted, verifiable)
- Inputs (with wikilinks)
- Out of scope
- Constraints
- Review
- Notes for the builder

### 4. Verify

Test against:
- [ ] Could a builder who's never seen this project execute the spec without asking?
- [ ] Are acceptance criteria independently verifiable?
- [ ] Is every input linked, not just named?
- [ ] Is out-of-scope specific enough to prevent scope creep?

If any "no", revise. Don't ship a spec the builder will have to interpret.

### 5. Update status

Append to project `status.md`:
- Spec path in recent decisions or open items
- If spec unblocks the next action, update "Next action"

## What NOT to do

- Don't include "TBD" in acceptance criteria. If TBD, the spec isn't ready.
- Don't write a spec the builder will have to interpret. Specs are imperative.
- Don't bury the deliverable in prose. Top of file, one sentence.
