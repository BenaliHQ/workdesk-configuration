---
name: define-signal
description: Meta-skill — scaffold a new intel signal type. Signals are Claude-generated synthesis (briefings, observations) drawing from multiple sources through operator-context. Define purpose, anchors, traversal, schedule, output, and detection.
---

# /define-signal

Signals are semantic, not mechanical (per the plan §"Signals are semantic, not mechanical"). The declaration captures intent and anchors; Claude executes the contextual lookup at runtime.

> **Operates under [[type-scaffolding]]** — design every required field, section, and structure deliberately. A type definition is a contract, not a folder layout. Apply the senior-teammate cold-pickup test, mark required vs optional explicitly, and validate by walking a real instance before locking the schema.

## Detection clause

Surface proactively when:
- The operator repeatedly asks for the same kind of synthesis ("what's coming up", "summarize my reading")
- vault-improvements detects a recurring synthesis pattern across daily-plan or weekly-review

Ask: *"You've asked for {kind of synthesis} a few times. Want to define it as a signal so it runs on schedule?"*

## JTBD-first interview

1. **What do you want Claude to keep an eye on for you?** Free response.
2. **Why does this matter?** What problem does the signal solve?
3. **What sources should it look at?** Calendar, atlas zones, system events, external APIs.
4. **How often should it run?** Daily, weekly, on-demand, triggered.
5. **What should it produce?** Output shape, location, length.

Then formalize:

6. **Anchors** — fixed sources the signal always reads
7. **Traversal** — runtime lookups (e.g., "for each person on calendar, fetch their note")
8. **Output format** — frontmatter + body sections
9. **Drop inbox pointers?** When the signal surfaces work needing operator action

## Scaffold

Create:

```
intel/{name}/                           # output folder
config/signals/{name}.md             # declaration
```

### `config/signals/{name}.md` shape

```markdown
---
type: signal-declaration
name: {name}
shape: briefing | observation | research | vault-improvement | {custom}
output-folder: intel/{folder}/
naming: "{YYYY-MM-DD}-{name}"
schedule: daily | weekly | on-demand | triggered
version: 1.0
---

# Signal: {name}

## Purpose

{One paragraph}

## Anchors

{Fixed sources}

## Traversal

{Runtime graph traversal rules}

## Output

{Frontmatter + body sections}

## Schedule mechanism

{How it fires — SessionStart trigger, on-demand only, etc.}

## Detection (ad-hoc)

{When Claude proposes generating one outside the schedule}

## ## Learnings

(Empty.)
```

## Schedule wiring

If schedule is `daily` or `weekly`:
- Add to `config/state/signals.json` with `last-fired: null`
- Update the SessionStart scan to include the new signal in due-signal checks

## Verify

- [ ] Production declaration is comprehensive (anchors + traversal explicit)
- [ ] Tools and zones degrade gracefully when missing
- [ ] No hardcoded time windows in traversal

## What NOT to do

- Don't write detection logic in the signal. Detection clauses fire ad-hoc generation; the schedule fires routine generation.
- Don't define overlapping signals (e.g., daily-plan and morning-briefing).
- Don't skip the "schedule mechanism" section. SessionStart is the only V1 trigger.
