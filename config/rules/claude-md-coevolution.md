---
date: 2026-04-16
last_updated: 2026-04-16
---

# CLAUDE.md Co-Evolution

When the same correction appears in ≥2 skills' `learnings.md` within 30 days, promote it to a rule or to CLAUDE.md. Without co-evolution, learnings silo — the same fix gets entered 5 times across 5 skills instead of once at the rules/ or CLAUDE.md level.

## When this applies

- **A correction happens.** Claude records it immediately with
  `config/scripts/learnings-capture.sh --skill <slug> --tag <TAG> --text "..."`.
  This is the step that makes everything else possible — a correction that isn't
  captured cannot be promoted, and the session transcript is not a capture.
- **The Stop hook fires.** `config/scripts/learnings-scan.sh` reads every
  `config/skills/*/learnings.md`, looks for the same correction in two or more
  skills within 30 days, and writes a `[REVIEW]` inbox item proposing promotion.
  It exits in milliseconds unless a `learnings.md` actually changed.
- **`/weekly-review` runs** — the manual backstop for patterns the fuzzy matcher
  missed (see § Matching, and what it can't do).

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

## Matching, and what it can't do

`learnings-scan.sh` compares corrections by **fuzzy token overlap** — the overlap
coefficient over normalised, stop-worded tokens — not by semantic similarity.

It catches the shape this rule was written for: *"don't use leverage"* against
*"avoid leverage in drafts"*. It will **not** catch two corrections that mean the
same thing in entirely different words. That's a real ceiling, and `/weekly-review`
is the named backstop for it.

False positives are the cheaper error and the matcher is tuned accordingly. Every
proposal is operator-reviewed, nothing is ever auto-applied, and a cluster the
operator declines is recorded in `config/state/learnings-scan.json` and never
surfaced again.

## Implementation

| Piece | File | Role |
|---|---|---|
| Capture | `config/scripts/learnings-capture.sh` | Claude calls it when a correction happens. Appends to the skill's `learnings.md`; `STYLE` entries also land in `config/rules/writing-style.md`. |
| Scan | `config/scripts/learnings-scan.sh` | Stop hook. Cross-skill clustering → `[REVIEW]` inbox proposal. |
| Wiring | `config/settings.json` → `hooks.Stop` | Runs alongside `stop-session-snapshot.sh`. |
| State | `config/state/learnings-scan.json` | `last-scan`, `proposed`, `rejected`. |

Entry format in `learnings.md` is load-bearing — `learnings-scan.sh` parses it:

```markdown
- 2026-08-01 `[STYLE]` don't use the word leverage in drafts
```

Tags: `STYLE`, `PROCESS`, `TOOL`, `FACT`, `OTHER`.

> [!warning] The capture step is not automatic
> Nothing detects a correction on its own. A hook sees tool calls, not intent —
> only Claude knows the operator just corrected something. If Claude doesn't call
> `learnings-capture.sh`, the correction is lost at end of session and the scan has
> nothing to find. Treat capture as part of responding to a correction, not as
> cleanup for later.

## What NOT to do

- Do not apply promotions silently. Every promotion requires operator approval.
- Do not promote single-skill corrections — those stay in `learnings.md`.
- Do not promote before 2 skills show the same correction. One skill, one correction = local, not cross-cutting.
- Do not re-propose clusters the operator has rejected.
- Do not let a correction pass without capturing it. This rule described an
  automatic Stop-hook mechanism for months while no `learnings.md` existed
  anywhere and the configured Stop hook had no learnings logic — every correction
  in that window was lost. A documented mechanism that doesn't run is worse than
  an honest manual one, because nobody goes looking.
