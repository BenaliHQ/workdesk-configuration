---
name: daily-ops
description: Generate today's daily plan via the daily-plan signal, then surface session-entry items (unprocessed transcripts, intake, due signals). Run first thing in a session, or when context shifts mid-day. Updates state/signals.json after writing.
---

# /daily-ops

Daily operating cycle. Reads session-entry state, runs the daily-plan signal, surfaces what needs attention right now.

## Invocation

- `/daily-ops` — full cycle: read state, generate daily plan, surface inbox
- `/daily-ops --plan-only` — generate daily plan, skip surfacing
- `/daily-ops --refresh` — regenerate daily plan even if today's already exists

## Phases

### 1. Read session-entry state

Read `config/state/session-entry.md`. Note the counts:
- unprocessed transcripts
- intake items
- unsummarized session logs
- due signals

### 2. Run daily-plan signal

Follow `config/signals/daily-plan.md`:

0. **Read config** from `config/operator-profile.md` (`email` + `daily-plan:` block) — see the signal's `## Configuration` table. Defaults: scope `own`, lookahead `7`, lookback `7`, email-label empty (skip). All of the below substitute these values.
1. Resolve anchors:
   - Calendar — scoped per `calendar-scope` (default `own` = `{email}` only, shared calendars excluded), **today + next `{lookahead}` days**: `gws calendar +agenda --today --calendar {email}` and `gws calendar +agenda --days {lookahead} --calendar {email}`
   - Daily notes — **last `{lookback}` days** of `personal/daily/`, today weighted most (read-only)
   - Email — the **`{action-email-label}`** Gmail label *if set* (default empty → skip): `gws gmail users messages list --params '{"userId":"me","q":"label:{label}","maxResults":25}'` then fetch each id's metadata headers
   - Active project `_status.md` across **all three locations**: `gtd/projects/`, `atlas/clients/*/projects/`, `atlas/businesses/*/projects/`
   - Actions: `gtd/actions/next/` and `gtd/actions/waiting/`
   - Due recurring items, inbox
2. Traverse:
   - For each person on today's calendar, fetch their atlas/people note + last meeting
   - For each project referenced today, fetch `_status` + recent meetings
   - Surface stale work where `today - last-touched > 1.5 × expected-cadence`
   - For each `gtd/actions/waiting/` item, check whether it's unblocked or needs a nudge
3. **Reason — GTD triage.** Assign every candidate a disposition (do-now / prioritize / delegate / defer / delete) and lead the plan with the 1–3 items that truly require the operator. See the signal's `## Reasoning — focus & GTD triage`.
4. Apply sparse-data fallback chain (skip layers with no data)
5. Apply tonality from `operator-profile.role` and `operator-profile.work-mode`. If `first-30-days-mode: active`, lean toward setup-oriented framing; otherwise neutral. If either field is empty (early state), default to neutral.

Write to `intel/briefings/daily/{YYYY-MM-DD}-daily-plan.md` with the signal frontmatter:

```yaml
---
type: signal
shape: briefing
date: 2026-04-26
sources: ["..."]
schedule: daily
---
```

Body sections per the declaration:
1. Today's commitments + relevant context
2. Projects to advance + where you left off
3. Stalled items needing attention
4. Inbox items awaiting triage (with backlog warning if >20)

### 3. Surface

Print to chat (after the file is written):
- Top 3 commitments with one-line context each
- Top 3 advance-work items
- Inbox count + 1-line summary if backlog >20
- Unprocessed source counts and proposals (e.g., "3 transcripts unprocessed — run `/process-transcripts`?")

### 4. Update state

After successful write:
- `config/state/signals.json` → `daily-plan.last-fired` = today

If write fails, do NOT update state. `/workdesk-doctor` trusts output files over state.

## Auto-expiry side effect

Daily-plan also cleans up expired inbox items as a side effect:
- `[AWARENESS]` older than 7 days → archive to `gtd/inbox/_archive/{YYYY-MM}/`
- `[QUESTION]` older than 14 days → archive

`[REVIEW]` and `[ACTION]` never expire — operator clears.

## What NOT to do

- Don't generate a hollow plan. If all 7 fallback layers return empty, produce a setup-oriented plan, not a stub.
- Don't write past the cap (7 new `[REVIEW]` per session). Batch beyond that.
- Don't update state before the file is written.
- Don't write to `personal/`. Read today's daily note; never modify it.
