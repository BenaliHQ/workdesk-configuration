---
name: define-rule
description: Meta-skill — scaffold a new behavioral constraint at config/rules/{name}.md. Rules are non-negotiable across all skills (no-fabrication, source-documentation, etc.). Use when a correction repeats in ≥2 skills' learnings within 30 days, or when an absolute constraint needs to apply everywhere.
---

# /define-rule

Skills can have learnings. Rules don't bend. This skill writes a new rule and wires it into the system.

> **Operates under [[type-scaffolding]]** — design every required field, section, and structure deliberately. A rule is a contract, not a paragraph dump. Apply the senior-teammate cold-pickup test, mark required vs optional sections explicitly, and validate by walking a real instance before locking the schema.

## When to run

- Operator corrects the same behavior in ≥2 distinct skills' `learnings.md` within 30 days (per `claude-md-coevolution` rule)
- A single correction is severe enough to be promoted immediately ("never send drafts without review")
- During `/onboarding` if the operator names a constraint they know they want

## Detection clause

Surface proactively when:
- The same correction appears in ≥2 skills' `learnings.md` within 30 days
- A correction is tagged `[CRITICAL]` or `[HARD]`
- The operator says "always" or "never" while correcting Claude

Ask: *"This correction came up in {skill A} and {skill B} recently. Want to promote it to a rule so it applies everywhere?"*

## Interview

1. **State the rule.** Imperative or prohibitive. "Never invent attribution." "Always link to the source meeting."
2. **When does it apply?** All sessions, certain workflows, certain zones.
3. **What failure mode does it prevent?** The bad outcome.
4. **What's the test?** How does Claude verify it's being followed?
5. **Any exceptions?** Rare. If many exceptions exist, it's not a rule.

## Scaffold

Create `config/rules/{rule-name}.md`:

```markdown
# {Rule Name}

{One-paragraph statement of the rule and why it exists. The "why" matters.}

## When this applies

- {scenario 1}
- {scenario 2}

## What to do

- {imperative bullet}

## What NOT to do

- {prohibited bullet}

## Test

{How Claude verifies the rule is being followed}
```

## Update CLAUDE.md

Add the rule name to the rules list. Universal rules go under "Universal", conditional under "Conditional". Don't paste the body — link only.

## Promote source learnings

If promoted from `learnings.md` entries, append `[PROMOTED → config/rules/{rule-name}.md]` to each source entry with today's date. Don't delete originals — they're history.

## Log

Hook fires `declaration-changed` automatically when the rule file is written.

## Verify

- [ ] Could Claude evaluate the test deterministically?
- [ ] Are exceptions named precisely (or absent)?
- [ ] Is the "why" present? Rules without rationale rot.

## What NOT to do

- Don't define a rule that overlaps an existing one. Read `config/rules/` first.
- Don't soften a rule with vague exceptions. If it has many exceptions, it's a guideline, and guidelines belong in skills.
- Don't promote a single-skill correction. One skill, one correction = stays in `learnings.md`.
- Don't skip "What NOT to do". Negative space defines the rule.
