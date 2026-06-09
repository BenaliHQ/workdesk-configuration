---
date: 2026-04-16
last_updated: 2026-04-16
---

# CLAUDE.md Co-Evolution

When the same correction appears in ≥2 skills' `learnings.md` within 30 days, promote it to a rule or to CLAUDE.md. Without co-evolution, learnings silo — the same fix gets entered 5 times across 5 skills instead of once at the rules/ or CLAUDE.md level.

## When this applies

- Stop hook fires at session end
- Scans `.claude/skills/*/learnings.md` for cross-skill patterns
- Also invoked manually during `/weekly-review` as a fallback for patterns the hook missed

## Detection rule

A pattern qualifies for promotion when ALL three apply:

1. **Cross-skill.** The same correction appears in `learnings.md` of ≥2 distinct skills (e.g., `/daily-ops/learnings.md` and `/night-shift/learnings.md`).
2. **Recent.** All occurrences are within the last 30 days.
3. **Semantic match.** The corrections express the same underlying rule (fuzzy-matched, not exact string). Example: "don't use leverage" + "avoid leverage in drafts" → same rule.

If detected, propose a promotion to the operator. Do not apply automatically.

## Promotion targets

| Pattern shape | Target | Example |
|---|---|---|
| Voice / writing style correction | `.claude/rules/writing-style.md` (append to `[STYLE]` section) | "don't use 'leverage'" |
| Process / workflow correction applying across workflows | New or updated `.claude/rules/{rule-name}.md` | "always check project status before planning" |
| Vault-level architectural correction | the primary vault's CLAUDE.md | "always read index.md first on session start" |
| Recurring correction within a single skill | Promote to skill's `SKILL.md` body (not a rule) | "/daily-ops always starts with calendar check" |

## Proposal flow

1. Stop hook scans recent `learnings.md` entries across skills
2. Clusters by semantic similarity
3. For each cluster meeting the detection rule:
   - Present: "I noticed this correction in {skill-A} and {skill-B} in the last 30 days: [summary]. Should I promote to {proposed-target}?"
4. Operator responses:
   - `y` → apply the edit, log `schema-edit` to `system/log.md`
   - `n` → mark cluster as "operator-rejected"; future hooks skip it
   - `modify` → operator refines the proposed edit, then approves
5. After approval, the hook:
   - Applies the edit to the target file
   - Appends `[PROMOTED]` entry to each source `learnings.md` with back-link
   - Logs to `system/log.md`

## What stays in `learnings.md`

- Single-skill corrections (1 skill, not 2)
- Skill-internal procedural tweaks
- Recurring operator preferences that only apply in one workflow context

The hook surfaces candidates. It does not force promotion.

## Implementation

Stop hook logic is implemented in the skills plan. This rule file is the constraint. For the full framework, see `atlas/projects/vault-architecture/deliverables/karpathy-mechanics/claude-md-coevolution-spec.md`.

## What NOT to do

- Do not apply promotions silently. Every promotion requires operator approval.
- Do not promote single-skill corrections — those stay in `learnings.md`.
- Do not promote before 2 skills show the same correction. One skill, one correction = local, not cross-cutting.
- Do not re-propose clusters the operator has rejected.
