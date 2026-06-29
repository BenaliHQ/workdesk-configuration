---
name: unpack
description: >-
  Progressively disclose complex work or topics ONE idea at a time so the operator genuinely
  comprehends it — never a wall of text. Use when the operator says "unpack this", "catch me up",
  "walk me through what you did", "explain this one thing at a time", "break this down", "I don't
  understand this", or "progressively disclose". Also PROACTIVELY OFFER it (don't auto-run) right
  before delivering a long recap of multi-step work, a dense plan, a hairy bug, an architecture, or
  any topic where a single message would overwhelm. The goal is comprehension, not awareness — the
  operator must do the thinking; their understanding cannot be outsourced.
argument-hint: "[optional: the topic or work to unpack]"
---

# Unpack — progressive disclosure for comprehension

The operator wants to **fully understand** something complex — work you just did, a long-running
effort, a dense plan, a concept. Not a summary they nod along to. Real, durable comprehension they
could explain back to someone else.

The failure mode this skill exists to kill: **the wall of text.** Dumping everything at once produces
the *feeling* of being informed and none of the understanding. You cannot transfer understanding by
volume. You transfer it one idea at a time, building on what already landed.

## The one principle everything serves

**The operator must do the cognitive work. You cannot do it for them.** Your job is to feed exactly
one idea, in the right order, at the right altitude, then *stop and let them process it* — and to
confirm it landed before adding the next. A check they breeze past is fine; a check that exposes a gap
is the whole point. Never trade their comprehension for your speed of delivery.

## Step 1 — Build the ladder (privately, before you say anything)

Decompose the topic into a **dependency-ordered sequence of single ideas**, each one resting on the
ones before it. Order by understanding, not by chronology or by how you built it. A reliable default
ladder (adapt freely — it's a skeleton, not a cage):

1. **Why it exists** — the purpose / the problem, as a plain mental model. (Start here almost always.)
2. **The core tension** — the one hard thing that makes this non-trivial.
3. **The mechanism** — how it actually works, at a high level.
4. **The constraints** — the rules/guardrails that must hold.
5. **The evidence** — what was actually done / proof it works.
6. **The scrutiny** — how it was stress-tested, or where it's genuinely uncertain.
7. **The honest gaps + recap** — what's *not* done, then a compact recap of the whole arc.

Keep the ladder to ~5–8 rungs. If you have more, you're mixing altitudes — collapse detail upward.

## Step 2 — Set the frame, then calibrate the starting altitude

Open with how this will go: *layer by layer, one idea at a time, I'll stop and check, you set the
pace, tell me to slow down or skip ahead.* Then **find where they already are** — either ask ("how
are you currently thinking about this?") or deliver rung 1 and explicitly invite "skip ahead if you
already know this." Never assume their starting point; never start above it.

## Step 3 — The per-turn loop (the heart of the skill)

For each rung, in one message:

- **One idea. Only one.** If you're tempted to add "and also…", that's the next rung. Hold it.
- **Plain language.** No jargon without defining it once, in line. If a teammate-facing term exists,
  use it; otherwise translate. Name the technical term in parentheses only after the plain version.
- **Anchor to what they already know.** Reach for an analogy from *their* world (their business, a
  process they run, something established earlier in the conversation), not a generic one.
- **Then STOP.** End with a check that makes *them* do a little work:
  - sometimes a genuine question — *"in your own words, why X?"*
  - sometimes a reaction gate — *"does this land, or is anything fuzzy?"*
  - occasionally a predict — *"given that, what would you expect to happen if…?"*
- **Wait.** Do not reveal the next rung in the same message.

## Step 4 — Calibrate to their response, every turn

- **"got it" / "next" / "skip"** → they're moving fast. **Seal the prior point in one short line**
  (so the comprehension isn't lost to speed), then advance one rung. Don't pad, don't re-teach.
- **A wrong or partial answer to a check** → don't just correct and barrel on. **Re-explain that rung
  a different way** (new analogy, smaller piece) — never the same explanation louder. Stay on the rung
  until it lands.
- **A question** → answer it at their altitude, then resume the ladder where you were.
- **"this is too much" / overwhelmed** → you went too wide or too deep. Drop to a smaller idea.

## Step 5 — Land it

After the last rung, give a **compact recap of the full arc** — the whole ladder in one tight list —
so the separate layers consolidate into a single structure they can hold. Then ask if any layer is
still fuzzy before you consider it done.

## Honesty is part of comprehension

Surface caveats, limits, and "what's *not* actually done" as their own rung — usually near the end.
Real understanding includes knowing the edges and the gaps. Glossing them produces false confidence,
which is worse than a known unknown. (Vault rule: [[no-fabrication]].)

## Proactive offer (don't auto-run)

When you're about to dump a wall of detail — a recap of multi-step work, a complex plan, a dense
debugging trail, an architecture, anything where one message would overwhelm — **offer first**:
*"This is a lot — want me to walk you through it one layer at a time so it actually lands?"* If they'd
rather have the full thing at once, give it. Offer, don't impose.

## What NOT to do

- Don't reveal two ideas in one turn "to save time." Speed is not the goal; comprehension is.
- Don't skip the check because they seem to be following. The check is what *makes* them follow.
- Don't answer your own comprehension question for them, or treat a "got it" as proof — seal and move,
  but if a real check surfaces a gap, stay until it closes.
- Don't start at the implementation. Start at *why it exists* unless they tell you they're past that.
- Don't use undefined jargon, then "explain" with more jargon.
- Don't omit the honest gaps to make the work sound more finished than it is.
- Don't turn the recap into a fresh info-dump — it's a consolidation of rungs already understood.

## Source

Operator instruction 2026-06-29: after a long autonomous build (Demandcast Shelf Phase 5), the
operator asked to be brought up to speed progressively — "one thing at a time… I can't outsource my
understanding to you" — then to capture the method as a reusable skill. The 7-rung walk-through used
in that session (purpose → hard problem → mechanism → guardrails → evidence → adversarial review →
honest gap → recap) is the validated template encoded above.
