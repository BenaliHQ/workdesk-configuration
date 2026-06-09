---
type: object-type-definition
name: inbox-item
zone: gtd
location: gtd/inbox/
shape: atomic
naming: "[{PREFIX}] {short-slug}"
version: 1.0
---

# Object Type: inbox-item

Lightweight pointer to something that needs operator attention. Pointers, not content — the real note lives in atlas or intel. Inbox items are notification, not storage.

## Format

```yaml
---
type: inbox-item
prefix: REVIEW                                          # REVIEW | ACTION | QUESTION | AWARENESS
target: "[[atlas/decisions/2026-04-23-acme-corp-scope-change]]"
source: "[[atlas/meetings/2026-04-23-acme-corp-weekly]]"
created: 2026-04-26
---
One-line description of why this needs review.
```

## Prefix table

| Prefix | When to use | Auto-expiry |
|---|---|---|
| `REVIEW` | Claude proposes; operator approves | never (operator clears) |
| `ACTION` | Operator must act on something | never |
| `QUESTION` | Claude needs an answer | 14 days |
| `AWARENESS` | FYI; no action needed | 7 days |

## Inbox flood guard

Plan §"Inbox flood guard" — Claude enforces:

- **Per-session cap.** ≤7 new `[REVIEW]` items per session. Past the cap, batch into a single rolled-up `[REVIEW]` ("12 more potential person notes from this transcript — review batch?").
- **Confidence threshold.** Proposals require ≥0.7 self-rated confidence. Below the bar: ask inline or stay silent.
- **Backlog signal.** When `gtd/inbox/` has >20 unresolved items, daily-plan surfaces a triage prompt as its top item.
- **Auto-expiry.** Per the prefix table above. `daily-plan` cleans up expired `[AWARENESS]` items as a side effect.

## Rules

- Only Claude writes inbox items
- Only operator clears them (move to archive or delete)
- Pointers, not content — real note in atlas/intel; inbox just points

## Detection

Inbox items are emitted by other detection clauses (object proposals, decision proposals, signal output). This declaration governs the format and the flood guard, not when items are created.
