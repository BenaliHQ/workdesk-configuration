---
name: weekly-review
description: Mandatory weekly signal. Generates the weekly-review briefing with proposed closures, promotions, and cleanup. Active from week 1 — the bridge skill between onboarding and steady state. Run at start or end of week, or whenever it's been more than 6 days since the last one.
---

# /weekly-review

The most important signal in the first 30 days. Active from week 1. Stable everyday loop ships before vault-improvements ever runs.

## Invocation

- `/weekly-review` — full cycle
- `/weekly-review --preview` — show proposed closures/promotions without writing inbox items

## Scope

The full cycle below produces a weekly briefing. If the operator requests only a project review or another bounded portion, honor that scope, label the output as partial, and verify its links with `check-wikilinks.sh --require-links`. Do not add unrelated scans merely to fill the full briefing, apply the full-week format gate, or advance `weekly-review.last-fired` for that partial task. `--preview` retains the requested review scope while suppressing inbox writes.

## Phases

### 1. Anchor scan

Per `config/signals/weekly-review.md`:

- `gtd/actions/next/` and `gtd/actions/waiting/` (status, last-touched)
- Projects across `gtd/projects/*`, `atlas/clients/*/projects/*`, and `atlas/businesses/*/projects/*`: read each `_brief.md` and `_status.md`. Respect explicit status; use declared cadence and dates, including `last_updated` / `last-updated` when `last-touched` is absent. A missing or invalid date means freshness is unknown: report the date gap without classifying the project as stale or current, or proposing closure on that basis.
- `gtd/recurring/schedules/` filter `status: active` AND `next_due <= today + 7d`
- `gtd/inbox/` (full backlog + age + prefix mix)
- Stale projects (all three locations above) and stale recurring items (`gtd/recurring/*`): `today - last-touched > 1.5 × expected-cadence` (skip `expected-cadence: none`)
- Last 7 days of `personal/daily/` (read only)
- Processed transcripts since `weekly-review.last-fired`

### 2. Synthesize

For the full cycle, build all four sections as level-two headings. A project inventory belongs within this synthesis; it does not replace it. For a section with no supported items, state the searched scope and result; if an anchor was unavailable, state that coverage gap instead of claiming there was no activity.

Build sections:

1. **What you shipped** — completed actions in `gtd/archive/actions/{current-month}/`, archived projects, decisions logged, content published
2. **What's stalled** — stale contexts, blocked actions (`waiting:` >7 days), inbox backlog
3. **What's coming** — recurring items due in 7 days, calendar deadlines, time-sensitive projects
4. **Proposed closures + promotions** — list each candidate with reasoning

### 3. Write

`intel/briefings/weekly/{YYYY-MM-DD}-weekly-review.md`:

```yaml
---
type: signal
shape: briefing
date: 2026-04-26
sources: [...]
schedule: weekly
week-of: 2026-04-20
---
```

### 4. Drop `[REVIEW]` items

For each proposed closure/promotion, drop a `[REVIEW]` item in `gtd/inbox/`:
- "Project X has had no activity for 18 days (expected biweekly) — close, archive, or update?"
- "Action Y has been in `waiting/` for 9 days — chase, close, or move to `someday/`?"
- "Recurring `weekly-payroll` due tomorrow — promote to next?"

Subject to flood guard (≤7 per session — additional candidates batched).

### 5. Verify and update state

Resolve the host-local Python with `bash config/scripts/migrate.sh source-runtime`. Use its returned path for the read-only briefing gate:

```bash
"<runtime-python>" config/scripts/complete-transcript.py --vault "$PWD" \
  --verify-outputs --weekly-review --output "<briefing-path>"
```

The existing output verifier checks the required weekly properties, real date values, all four nonempty sections, and source/context wikilinks. It does not establish factual accuracy or complete anchor coverage: review those separately before marking the run complete. Derive `week-of` from the actual reviewed week and the operator's week-start convention; do not copy the example dates.

After writing, verify source/context wikilinks with this gate. Plain-text paths and zero outgoing links do not satisfy the connection rule. Verify any newly created knowledge/inbox notes too. If required context is genuinely absent, report the gap and leave the run incomplete rather than fabricate a link.

Only after successful write and verification:
- `config/state/signals.json` → `weekly-review.last-fired` = today

### 6. Graduation check

If all three are true:
- onboarding `phases.graduation: complete`
- this is at least the first weekly-review
- at least one of: project, recurring item, processed transcript exists

Then update `config/operator-profile.md` `first-30-days-mode: graduated` and tell the operator: *"You've graduated from first-30-days. Vault-improvements activates in {X} days."*

## What NOT to do

- Don't skip --preview when operator asks. Some weeks they want to see candidates without committing them to inbox.
- Don't write more than 7 `[REVIEW]` items in one session. Batch the rest.
- Don't update state if the write failed.
- Don't graduate without all three conditions met.
