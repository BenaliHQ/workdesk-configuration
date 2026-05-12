---
name: define-object
description: Meta-skill — scaffold a new atlas object type via a JTBD-first interview. Object types are structural patterns (book, vendor, deal, etc.) with consistent frontmatter, folder, format, source rule, detection, and matching. Use when an emergent type pattern surfaces or operator says "I want to track X".
---

# /define-object

Object types are the structural primitives of `atlas/`. This skill defines new types — schema, location, source rule, detection, matching — without touching code.

> **Operates under [[type-scaffolding]]** — design every required field, section, and structure deliberately. A type definition is a contract, not a folder layout. Apply the senior-teammate cold-pickup test, mark required vs optional explicitly, and validate by walking a real instance before locking the schema.

## Detection clause

Run proactively when:
- ≥3 inbox/intake captures within 14 days share a recognizable shape but have no matching type
- Operator references a category that doesn't have a folder
- vault-improvements surfaces a "repeated unstructured shape" pattern

Ask: *"I'm seeing repeated captures that don't have a home. Want to define a `{type}` object so they have somewhere to land?"*

## JTBD-first interview

Don't ask about schema first. Ask about the work.

1. **What are you trying to track?** Free response. Listen for the noun.
2. **Why do you want to track it?** Job-to-be-done. What problem does this solve?
3. **What do instances look like in real life?** Examples — name a few.
4. **When does a new instance show up?** This becomes the detection clause.
5. **What changes when one of these shows up?** Other notes that need updating — the matching rule.

Then formalize:

6. **Atomic or container?** Single notes per instance, or folders with their own structure?
7. **Where in atlas?** Folder name (default plural).
8. **Required frontmatter?** `type`, `created`, `source` always; what else is type-specific?
9. **Body template?** Sections every instance should have.
10. **Naming?** Default kebab-case slug; confirm or override (e.g., `YYYY-MM-DD-topic`).
11. **Lifecycle?** Status values, transitions, archive policy.

## Scaffold

Create:

```
atlas/{location}/                       # the directory itself
atlas/{location}/_template.md           # template starting point
config/objects/{type}.md             # the type declaration
```

### `config/objects/{type}.md` shape

```markdown
---
type: object-type-definition
name: {type-name}
zone: atlas
location: {folder-path}
shape: atomic | container
folder-structure: 4-item | 8-item | n/a
naming: {kebab-slug | date-prefixed | custom}
version: 1.0
---

# Object Type: {type-name}

## Format

{Required frontmatter + body sections}

## Source rule

{Primary source field; inline footnote convention if multi-source over time}

## Detection

{When Claude proposes creating one — deterministic, evaluable}

## Matching

{What else updates when this changes}

## Lifecycle

{Status values, transitions, archive rules}
```

## Update CLAUDE.md (if universal)

Only universal types (used across all personas) belong in `CLAUDE.md`. Type-specific or persona-specific types stay in `config/objects/`.

## Verify

Test:
- [ ] Could Claude evaluate the detection clause without asking the operator?
- [ ] Is the format complete enough that an instance can be created without additional questions?
- [ ] Does the matching rule name specific other notes that update?

If any "no", revise.

## What NOT to do

- Don't define a type that already exists in `config/objects/`.
- Don't define overlapping types (e.g., `client` and `customer` unless the distinction is real and used).
- Don't write detection clauses as moods. Rules are evaluable.
- Don't auto-trigger creation. Detection clauses propose; operator approves.
