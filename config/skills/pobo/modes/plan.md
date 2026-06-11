# POBO — Plan mode

The full guided interview. Walk the operator from a fuzzy "I've got this thing" to a simple, runnable plan: a project folder with `_brief.md`, `_status.md`, and `plan.md` (phases in the simple-card format). Read the philosophy + phase-card format in `SKILL.md` first — they govern this mode.

`/pobo --lite` → jump to **Lite mode** at the bottom.

## Interview style (non-negotiable)

- **One open-ended question at a time.** Wait for the answer before the next. Never present multiple-choice widgets — invite the operator to think in their own words.
- **Coach, don't transcribe.** Challenge vague answers ("what specifically would that look like?"), offer concrete suggestions when they're stuck, reflect back in sharper language, push for specificity.
- **Do the heavy lifting at Organize.** Don't make the operator structure from scratch — propose the phase breakdown and let them react.
- **Pull real context first.** Before planning anything with vault history (a business, client, person), read the relevant `_brief`/`_status`/recent meetings so you're not asking what's already known. Use legacy/Drive/transcripts when relevant.

## Phase 0 — Meet them where they are

Open with: *"Tell me what's going on — what's the project or situation you're trying to figure out?"* Don't lead with framework language.

Listen, then silently map what they said to P / O / B / O and reflect it back organized: *"Here's what I'm picking up — the why is X, 'done' sounds like Y, you've already named pieces A/B/C, and a guardrail is Z. Let me fill the gaps."* Then move to whichever phase has the biggest hole. Order can flex; the gates below must still be met.

## P — Purpose & Principles

Get two things:
- **Purpose** — *why* this exists. "If this succeeds, what problem is solved / opportunity captured?" Probe: what triggered it, why now, who benefits, cost of not doing it.
- **Principles** — the guardrails. "What's non-negotiable? What would make this a failure even if delivered? Budget/timeline/relationship constraints?"

Redirect *what* → *why* ("that's a deliverable — why does it matter?"). Offer common principles if they're stuck.

**Gate:** purpose in 1–2 sentences; ≥2–3 principles; operator confirms. Read it back before moving on.

## O — Outcome Visioning

Get a vivid, **observable** end state — a scene, not a task list. "This went perfectly — describe what you see. Who benefits first, what's different for them? What would you show to prove it worked? How would you know in 30 days?"

Push vague → concrete ("'aligned' how? what artifact exists? what are they *doing* differently?"). Make sure every stakeholder's success shows up.

**Gate:** outcome is specific and observable, distinct from purpose, covers stakeholders, operator confirms "yes, that's done." Capture any **measurable signals** they name.

## B — Brainstorm

Unfiltered dump of everything that might need to happen — no sequencing, no judgment, volume first. Then probe gaps: prerequisites, dependencies, who else is needed, what could go wrong, what they're avoiding ("the conversation nobody wants to have" is usually load-bearing). **Add items they're missing** from your read of the domain. Keep them out of organizing mode until it's all out.

**Gate:** enough items to cover prerequisites → core → handoff → follow-up; operator agrees "that's everything"; no obvious gaps.

## O — Organize (where the plan is born)

This is where most plans go wrong by getting heavy. Hold the philosophy from `SKILL.md`. Steps:

1. **Run the two-projects test first.** Do the items split into *decide-what-it-is* vs *execute-across-channels*? If yes → this is **two projects**. Plan the first now; its last phase spawns the second. Tell the operator plainly; don't cram both into one plan.
2. **Cluster the brainstorm into phases — one deliverable per phase = one session.** A phase is a single thing produced start-to-finish. Sequence by dependency. Merge trivial steps; split anything that needs two sittings.
3. **Look for a ship-value-early phase** — an early deliverable that gives a usable provisional output off whatever's already decided. Place it right after the decision it depends on (not before — never ship wording you'll reverse).
4. **Name owners and the human-only phases** (decisions, voice). For those, the phase preps options so the decision is fast.
5. **Propose the structure and let the operator react.** Present the phase list; adjust. Then write each as a simple phase card.

Resist: parallel tracks, status cursors, completion rituals, per-phase "watch-outs / read-first / hands-to-next" as standard fields. If you're adding those, you're building a runner, not a plan. A phase card is Goal · Steps · Done-when · Owner · Kickoff · Next. That's all.

**Gate:** phases are dependency-ordered, each one session/one deliverable; a clear first next action; a stranger could read the plan and know what to do next.

## Execution bridge (lightweight)

Before scaffolding, nail three things in conversation — they go into `_status.md`, not a heavy section:
- **The constraint** — the single bottleneck most likely to stall everything. Name it.
- **Where the next action lives** — it has a real home (the plan + status), not the operator's head.
- **Review cadence** — when they'll look at this again (a date or a recurring review).

## Scaffold the project

1. Ask once: **"Does this involve code or a repo?"** → 9-item structure (adds `repo/`) vs 8-item.
2. Derive `{slug}` (kebab-case) and **confirm it** before creating.
3. Create under `gtd/projects/{slug}/`: `_brief.md`, `_status.md`, `plan.md`, `notes/` (drop the brainstorm in `notes/brainstorm.md`), `reference/`, `specs/`, `deliverables/`, `_archive/` (+ `repo/` if code). Empty dirs get `.gitkeep`.
4. **Never clobber** — if the folder exists, stop and ask.
5. Populate `_brief.md`, `_status.md`, `plan.md`, `notes/brainstorm.md`. Verify wikilinks (`config/scripts/check-wikilinks.sh`) before declaring done.
6. Confirm before creating: *"Ready to scaffold at `gtd/projects/{slug}/`? I'll create the structure and populate the brief, status, plan, and brainstorm."*

## Templates

### `_brief.md`
```markdown
---
type: project
slug: {slug}
status: active
created: {date}
last_updated: {date}
---
# {Project Name}

{One-sentence what-this-is.}

## Purpose
{1–2 sentences — why this exists.}

## Principles
- {guardrail}

## Outcome
{The observable end state. Include measurable signals if named.}

## Vision
{2–4 sentences — what success feels like.}
```

### `_status.md`
```markdown
---
type: project-status
slug: {slug}
last_updated: {date}
current_phase: 0
---
# Status — {Project Name}

**Next action:** Phase 0 — {first phase} ({owner}).

> [!info] How to work this
> Do the first unchecked phase below. Its card (goal, steps, done-when, kickoff) is in [[plan]].
> When done: check it off, add the output link, update **Next action**. That's the loop.

### Resume prompt
```
Resume {slug}. Read gtd/projects/{slug}/_status.md, find the first unchecked phase, open its
card in plan.md, do it. When done, check it off and update the Next action line.
```

## Phase ledger
- [ ] **0** — {phase} — *{owner}*
- [ ] **1** — {phase} — *{owner}*

## Constraint
{The one bottleneck.}

## Review
{Cadence / next review date.}
```

### `plan.md`
Header (purpose/principles/outcome pointers to `_brief`) + a short "how this runs" note + the phase cards in the **simple phase-card format** from `SKILL.md`. One card per phase. End with a **Next action** line. Nothing heavier than the card format.

## Edge cases

- **Tiny (1–2 actions):** not a project — suggest capturing it as an action in `gtd/actions/next/` instead.
- **Already has a clear plan:** don't force every phase; fill the gaps, then organize + scaffold.
- **Multiple projects surface:** flag it (two-projects test) — plan one, sequence the other.
- **Standing responsibility (no bounded outcome):** not a POBO target — say so and stop.
- **Gets heavy:** if the plan is sprawling or you're reaching for tracks/cursors, stop and run the two-projects test — it's usually the cause.

---

## Lite mode (`/pobo --lite`)

Three questions only: (1) **Outcome** — one sentence; (2) **First next action** — one physical line; (3) **End-state signal** — how you'll know it's done. Scaffold the 8-item structure; populate `_brief.md` (those three) and `_status.md` (`current_phase: lite`, next action). Leave `plan.md` minimal. Note that it can graduate to full POBO if it grows past ~3 actions or 2 weeks.
