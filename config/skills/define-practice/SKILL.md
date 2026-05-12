---
name: define-practice
description: Meta-skill — scaffold a new personal/ practice. Practices are operator-owned recurring habits (journal, reading log, gratitude, morning pages). The agent never writes here — practices are read-only from Claude's perspective.
---

# /define-practice

`personal/` is read-only. Practices declare what lives there so the agent knows how to read it during signal generation.

> **Operates under [[type-scaffolding]]** — design every required field, section, and structure deliberately. A type definition is a contract, not a folder layout. Apply the senior-teammate cold-pickup test, mark required vs optional explicitly, and validate by walking a real instance before locking the schema.

## Detection clause

Surface proactively when:
- The operator drops files into `personal/` in a recognizable pattern (e.g., `personal/journal/2026-04-26.md` weekly without a journal practice declared)
- vault-improvements detects a personal/ folder Claude doesn't know how to read

Ask: *"You're keeping {kind of practice} files in `personal/`. Want to declare it as a practice so signals can read them?"*

## JTBD-first interview

1. **What practice?** Journal, reading log, gratitude, morning pages — anything.
2. **What's the cadence?** Daily, weekly, on-demand.
3. **What does an entry look like?** Free text, structured template, hybrid.
4. **Should signals read this?** What does daily-plan or weekly-review do with it?
5. **Read policy** — when, by which signals, with what filter (most recent only, last 7 days, all).

## Scaffold

Create:

```
personal/{practice}/                    # operator-only folder
config/practices/{name}.md           # declaration
config/templates/{name}.md           # optional template scaffold (operator may copy)
```

The agent does NOT seed entries — the lock prevents writing to `personal/`. The template at `config/templates/` is a reference operators copy by hand or via an Obsidian daily-note plugin.

### `config/practices/{name}.md` shape

```markdown
---
type: practice-declaration
name: {name}
zone: personal
location: personal/{folder}/
naming: "{pattern}"
cadence: daily | weekly | on-demand
template: minimal | structured
read-policy: "{which signals read this and how}"
version: 1.0
---

# Practice: {name}

## Identity

{What this practice is, who owns it (always operator)}

## Read policy

{Signals that read it, and how}

## Template

{Reference to config/templates/{name}.md or "operator-defined"}

## Detection

{Optional — when daily-plan or weekly-review surfaces a missing entry as a hint, NOT as a [REVIEW] item (low-priority hint only)}

## Cadence

{daily/weekly/on-demand and any promotion rules — practices typically don't graduate to other types}
```

## Verify

- [ ] Read policy is explicit about which signals access this practice
- [ ] No agent-write paths included (lock enforces this regardless)
- [ ] Cadence + naming let signals find the right entry

## What NOT to do

- Don't write a practice that requires agent-write. The personal/ lock is non-negotiable.
- Don't drop `[REVIEW]` items for missing practice entries. Low-priority hints in daily-plan only.
- Don't auto-create entries from operator captures elsewhere. Practices are operator-driven; route captures via intake instead.
