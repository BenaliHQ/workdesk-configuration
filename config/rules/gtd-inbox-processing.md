# GTD Inbox Processing & Ownership Routing

The inbox is an **in-tray, not a to-do list.** Processing it means routing every item to a home until it's empty (or near it) — not skimming it and deleting only the items that happen to be done. And the operator **does not track other people's work**: a delegated action never enters the operator's GTD unless it is a hard blocker on the operator's own forward progress.

These two principles travel together. Without the first, the inbox never empties (un-routed items pile up). Without the second, the inbox fills with the team's task lists and stops being the operator's surface.

## When this applies

- Processing `gtd/inbox/` (operator-invoked or during review)
- Any workflow or skill that creates inbox items from a source — transcript processing, bookmark processing, signals, future kinds
- Routing captured actions from any interaction
- Reviewing whether something belongs in `actions/next/`, `actions/waiting/`, a project's `_status.md`, or nowhere in the operator's system

## What to do

### The inbox is a capture in-tray

The goal of every processing pass is to **empty it**. Each item gets one clarify decision and moves to a home. What remains should be only decisions that genuinely need the operator.

Clarify decision tree, per item:

- **Not actionable** → `gtd/archive/` (done/dead), `gtd/someday/` (maybe later), or `gtd/reference/` (just good to know).
- **Operator's own action, < 2 min** → do it now, then archive.
- **Operator's own action, deferred** → `gtd/actions/next/`, or fold into the relevant project's `_status.md` open items if it's multi-step.
- **Delegated to someone else** → apply ownership routing below.
- **Needs the operator's decision before it can even be clarified** (`[REVIEW]` / `[QUESTION]`) → stays in the inbox as the **review queue**. This is the only category that legitimately waits in the inbox. Keep the queue short — the operator blasts through it, it doesn't sit ten deep.

### Ownership routing — the core rule

- **The operator does not track their team's task lists.** Delegating something does not put it on the operator's plate.
- A delegated action enters the operator's GTD **only if it is a hard blocker** on the operator's own forward progress (the operator cannot proceed until it's done). When it qualifies, it goes to `gtd/actions/waiting/` — **not** the inbox.
- **Non-blocking delegated work stays only as an inline record on its source note** (the meeting note, the call note). It never gets an inbox item and never enters `actions/`. The source note is the record; that's enough.
- `actions/waiting/` is **sparse by design** — hard blockers only. If `waiting/` is filling with routine delegated items, this rule is being violated.

When in genuine doubt about whether a delegated item blocks the operator, default to inline-only (not a blocker). A missed blocker resurfaces naturally; an over-eager inbox does not self-clean.

## What NOT to do

- Do not treat the inbox as a master to-do list and merely delete completed items. That's the failure mode that makes it grow without bound — un-routed items have nowhere to go, so they sit. Route every item to a home.
- Do not create inbox items (or `waiting/` items) for delegated work that doesn't block the operator. The source note is the record.
- Do not let `actions/waiting/` accumulate non-blocking delegated work. Blockers only.
- Do not leave the operator's own deferred actions sitting in the inbox. Move them to `actions/next/` or the relevant project.
- Do not infer that a delegated item is a blocker just because it's important or the operator cares about it. "Blocker" means the operator's own next action is gated on it.

## Source

- Operator instruction, 2026-06-10: "I don't want a bunch of delegated work inside of my waiting. I don't really want to track other people's stuff. Unless it is a major blocker for me from making progress and moving forward. Waiting should be fairly sparse." Followed by a full inbox clarify pass (95 → 14) and the corresponding `/process-transcripts` owner-routing change (released v1.18.0). This rule is the general constraint; the transcript processor's `owner_category` routing is one enforcement point of it.

Related: [[matching]] § Inbox notifications (when to fire an inbox item at all); [[inbox-item-format]] (the shape of an inbox item); [[source-processing-pattern]] (the source → primary → secondaries → notification flow); the `action` object ownership filter.
