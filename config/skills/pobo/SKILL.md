---
name: pobo
description: "Plan, organize, and pressure-test multi-step projects with the GTD Natural Planning Model. A skill family: `/pobo` (guided plan), `/pobo organize` (restructure a brief/brainstorm into clean phases), `/pobo review` (adversarially pressure-test a plan). Use `/pobo --lite` for fast low-stakes planning."
---

# POBO

A planning skill family built on David Allen's Natural Planning Model — **P**urpose, **O**utcome, **B**rainstorm, **O**rganize. It produces *simple plans you can actually run*, not impressive-looking documents.

## Invocation — the family

| Command | Mode | What it does | Reads |
|---|---|---|---|
| `/pobo` · `/pobo plan` | **Plan** | Full guided interview (Frame → Organize). Produces a project: brief + plan + status. | `modes/plan.md` |
| `/pobo --lite` | **Plan (lite)** | 3-field fast plan for low-stakes work. | `modes/plan.md` |
| `/pobo organize [project]` | **Organize** | Take an existing brief/brainstorm (or a messy plan) and (re)structure it into clean one-session phases. | `modes/organize.md` |
| `/pobo review [project]` | **Review** | Adversarially pressure-test a plan against the quality bar; surface gaps + fixes. | `modes/review.md` |

**Routing:** look at the first argument. `review` → read and follow `modes/review.md`. `organize` → `modes/organize.md`. Anything else (empty, `plan`, `--lite`) → `modes/plan.md`. Read the mode file before doing the work; don't improvise from this router.

## The planning philosophy (applies to every mode)

These are the load-bearing lessons. They override the instinct to be thorough-looking.

1. **A plan you can run beats a plan that looks complete.** Resist adding structure. Every field, callout, or section must earn its place by changing what someone *does*. When in doubt, remove it. (Over-structuring is the most common failure — watch for tracks, cursors, rituals, nested fields creeping in.)
2. **One deliverable per phase = one work session.** A phase is a single thing a person or a Claude/Codex session produces start-to-finish. If a phase needs two sittings, split it. If three phases are really one move, merge them.
3. **The two-projects test.** If the phases split into *"decide what it is"* vs *"execute it across channels,"* that's **two projects**. Plan the first; let its final phase spawn the second — because the second can't be specified until the first exists. **Smell:** "skeleton" phases, "detail-on-unlock," or a plan that won't fit one mental model = you're holding a second project inside the first. Split it.
4. **Ship value early.** Prefer an early phase that produces a usable *provisional* output (built on whatever's already decided) over making the operator wait for the whole plan. Mark it provisional; a later phase supersedes it.
5. **Separate planning from running.** POBO produces the *plan*. Resuming across sessions is a light convention — a status checklist + a "next action" line + an optional paste-ready kickoff prompt per phase. **No cursors, no completion rituals, no parallel tracks.** If you're building a runner, stop.
6. **Why before what; outcome must be observable.** Purpose first (the decision filter). "Done" is something you can stand in front of and verify, not an aspiration.
7. **Honest about gaps.** Mark what isn't known yet rather than fabricating detail (per `no-fabrication`). A flagged gap beats a confident guess.
8. **Name the human-only parts.** Decisions and voice (a founder's manifesto, a pricing call) can't be manufactured by a prompt — the plan maximizes *prep* so the decision is fast, and says explicitly "this one's yours."

## The simple phase-card format (the standard output)

Every organized plan uses this. Nothing heavier.

```markdown
### Phase N — <one deliverable>
**Owner:** <who> · **Next:** Phase N+1
- **Goal:** the one thing this phase produces (+ where it's saved)
- **Steps:** 3–6 bullets (include any decision the operator must make)
- **Done when:** 2–3 objective, checkable conditions

> [!tip]- 🚀 Kickoff prompt
> ```
> Resume <project> Phase N. <read-first files>. <goal + the done-when bar.>
> Save to <path> and check Phase N off in _status.md.
> ```
```

And the status file is just: a **next-action line**, a **phase checklist**, and a one-line loop ("do the first unchecked phase, check it off, update next action"). See `modes/plan.md` for the full templates.

## What stays constant across modes

- **Project home:** `gtd/projects/{slug}/` with the 8-item (or 9-item for code) structure per `per-project-accounting`. Confirm the slug before creating; never clobber an existing folder.
- **Conversational, one question at a time.** No multiple-choice widgets; invite the operator to think in their own words (full detail in `modes/plan.md`).
- **Provenance + links:** follow `source-documentation` and `double-entry-knowledge`; verify wikilink targets exist (`config/scripts/check-wikilinks.sh`) before sign-off.
- **Durability:** this skill is upstream-tracked. Edits iterate in the vault, then ship via `/release` per `upstream-release-discipline` — vault-only edits die on `/update`.
