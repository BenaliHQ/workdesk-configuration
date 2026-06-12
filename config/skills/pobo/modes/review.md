# POBO — Review mode

`/pobo review [project]` — adversarially pressure-test a plan before it's executed. The goal is to catch what makes a plan fail *in the world*, not to praise it. Be honest and specific; a flattering review is a useless review.

Read the planning philosophy in `SKILL.md` — the review scores the plan against it.

## What to do

1. **Read the whole plan** — `_brief`, `plan.md`, `_status.md` (and the source brainstorm if present).
2. **Score it against the quality bar** (below). For each dimension, state pass / weak / fail and *why*, with the specific evidence from the plan.
3. **Surface the findings ordered by severity** — the ones that change *outcomes* first, taste/polish last.
4. **Separate correctness bugs from taste.** A correctness bug is a logical flaw (a phase depends on output that doesn't exist yet; a metric that can't be measured when it's scheduled). Taste is "I'd phrase this differently." Label which is which — the operator should fix bugs and is free to ignore taste.
5. **Offer to apply the high-leverage fixes**, but don't rewrite unasked. Review surfaces; the operator (or `/pobo organize`) revises.

## The quality bar — score each

1. **Starts from why.** Is purpose stated before tasks, and does it actually filter decisions? Or is it tasks in search of a reason?
2. **Observable outcome.** Can you stand in front of "done" and verify it? Are there measurable signals — and can they actually be measured *when the plan schedules them* (no measuring something before it exists)?
3. **One deliverable per phase = one session.** Any phase that's really three? Any three that are really one? Anything that won't fit a single sitting?
4. **Objective acceptance.** Could two people disagree about whether a phase is done? If yes, it's underspecified. Look for countable conditions, not "comprehensive."
5. **Right-sized — not over-built.** *(The most common failure.)* Are there parallel tracks, status cursors, completion rituals, or fat per-phase fields that add ceremony without changing what someone does? If the plan is impressive-looking but hard to run, that's a fail. Recommend stripping.
6. **The two-projects test.** Do the phases secretly split into *decide-it* vs *execute-it-across-channels*? Skeleton phases / "detail-on-unlock" / a plan too big to hold = it's two projects. This is usually the root cause when a plan feels unwieldy — check it early.
7. **Honest about gaps.** Are unknowns flagged, or fabricated into false confidence? Future-dependent detail should be marked, not guessed.
8. **Ownership + human-only parts.** Does every phase have an owner? Are decision/voice phases named as such, with prep that makes the decision fast (not a prompt pretending to decide for the operator)?
9. **Sequencing soundness.** Does each phase's inputs exist by the time it runs? Trace the dependency chain for a phase that consumes a not-yet-produced artifact.
10. **Ship-value-early.** If the trigger was an urgent live need, does anything deliver usable value before the whole plan finishes — without committing to something a later phase reverses?
11. **Execution bridge.** Is the constraint named? Does the next action have a real home? Is there a review cadence and (for human-gated work) is that bandwidth actually booked, not just named?
12. **Cold-pickup test.** Could a competent stranger open `_status.md`, know exactly what to do next, do it, prove it's done, and hand off — without you in the room? If not, what's missing?

## How to deliver the review

- Lead with an honest one-line verdict ("strong on structure, but it's secretly two projects and over-built in the middle"). Don't bury it.
- Group findings: **correctness bugs** (fix these) → **risk/scope gaps** → **minor/taste**.
- For each, name the dimension, the evidence, and the fix.
- End by naming the 2–3 highest-leverage changes (the ones that change outcomes) and offer to apply them (often via `/pobo organize`).

## Watch your own bias

The failure mode of an AI reviewer is *adding* structure to look rigorous — each pass bolting on more fields, tracks, gates. Resist it. More often the right call is **remove**, **split into two projects**, or **merge over-granular phases**. If your review only ever makes plans bigger, you're doing it wrong.
