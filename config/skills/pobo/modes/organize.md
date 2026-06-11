# POBO — Organize mode

`/pobo organize [project]` — take material that's *already framed* (a brief + brainstorm, or a messy/overgrown plan) and (re)structure it into clean, runnable phases. Use this when the thinking exists but the structure is weak, or after a `/pobo review` that says "this is really two projects" or "this is over-built."

This is the **Organize** half of the planning flow, runnable on its own. Read the philosophy + phase-card format in `SKILL.md` first.

## When to reach for this

- A plan exists but it's sprawling, vague, or heavy (work-order fields, tracks, rituals) and needs to collapse to the simple format.
- A brief + brainstorm exist (from `/pobo` or elsewhere) and just need organizing into phases.
- A review found a structural problem (two-projects, wrong granularity) and you're applying the fix.

## What to do

1. **Read the source material.** The `_brief` (purpose/outcome/principles) and the brainstorm — or the existing `plan.md`/`_status.md` if restructuring. Don't re-interview; the framing is assumed. If purpose or outcome is actually missing, stop and send them to `/pobo` (plan) — you can't organize what isn't framed.

2. **Run the two-projects test.** Do the items split into *decide-what-it-is* vs *execute-it-across-channels*? If yes, it's two projects — propose the split, plan the first, let its last phase spawn the second. This is the single highest-leverage move; do it before anything else. **Smell:** skeleton phases, "detail-on-unlock," or a plan too big to hold in one model.

3. **Cluster into phases — one deliverable = one session.** Each phase is a single thing produced start-to-finish. Sequence by dependency. Merge trivial steps; split anything needing two sittings. Name the dependency order and what (if anything) can run in any order.

4. **Find a ship-value-early phase.** An early deliverable that gives a usable provisional output off what's already decided — placed right after the decision it rests on.

5. **Name owners + human-only phases.** Decisions and voice get prepped (options laid out) so they're fast; mark them "this one's yours."

6. **Write each phase in the simple card format** (Goal · Steps · Done-when · Owner · Kickoff · Next). Resist heavier structure — see the over-structuring warning in `SKILL.md`.

7. **Propose, then write.** Show the operator the phase list to react to before committing it to `plan.md` + `_status.md`.

## Strip, don't add

If you're restructuring an overgrown plan, the job is mostly **removal**: kill parallel tracks, status cursors, completion rituals, per-phase watch-out/read-first/hands-to-next fields. Collapse to Goal/Steps/Done-when/Owner/Kickoff/Next. A good organize pass usually *shrinks* the plan — measure it (e.g., wikilink/line count before vs after) and report the reduction.

## Output

Updated `plan.md` (simple phase cards) + `_status.md` (next-action line + phase checklist), per the templates in `modes/plan.md`. Verify wikilinks before declaring done. If you split into two projects, scaffold only the first now; note the second as spawned by the first's final phase.
