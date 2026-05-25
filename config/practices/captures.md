---
type: practice-declaration
name: captures
zone: personal
location: personal/captures/
naming: "{YYYY.MM.DD} Capture - {first-sentence}"
cadence: on-demand
template: source-shaped
read-policy: "daily-plan reads today + yesterday; weekly-review reads last 7 days; vault-improvements scans for recurring patterns"
version: 1.0
---

# Practice: captures

Quick-capture surface for voice memos (and, in the future, typed notes). Pairs with the WorkDesk Operating System plugin's mic ribbon icon. Lives in `personal/captures/{YYYY.MM.DD} Capture - {first sentence}.md`.

## Identity

A capture is a fragment that needs to land *now* — a thought, an observation, a follow-up — without context-switching into the day's note. Operator-owned input, Claude reads, Claude never writes.

Distinct from `personal/daily/`: daily notes are the day's working surface (one per day); captures are individual fragments that happen whenever, each in their own file.

Input path: the **WorkDesk plugin's mic ribbon icon** (also reachable via command palette → "Capture voice memo", id `workdesk:capture:voice-memo`). One tap starts recording — the icon pulses red, a sticky toast shows recording status. Second tap stops, transcribes via the configured STT provider, and writes the file. Errors (missing STT key, mic permission, transcribe failure) surface as toasts.

Typed captures aren't a built-in path today. If they become a need later, they can route through the same `personal/captures/` folder with `source-kind: typed` — signals don't need to change.

## Read policy

- **`daily-plan`** reads captures from today and yesterday as input anchors for the morning plan.
- **`weekly-review`** reads the last 7 days of captures and surfaces themes across them.
- **`vault-improvements`** scans for recurring patterns that might want to graduate — a concept candidate (→ propose `intel/concepts/{name}.md`), a project candidate (→ `[REVIEW]` inbox notification), or a contradiction with existing vault content.

Claude never writes to `personal/captures/` — `personal/` is hard-locked. When a specific capture warrants vault-side action, the operator asks Claude directly ("process the capture about X"); Claude reads the file in place and produces atlas/intel/inbox artifacts elsewhere. The capture itself stays in `personal/captures/` as audit trail.

## File shape

One file per capture, named `{YYYY.MM.DD} Capture - {first sentence of body}.md` (dot-separated date, "Capture" keyword, dash-separated slug derived from the first sentence). This is what the WorkDesk plugin writes.

**Filename is not what signals key off.** Signals discover captures by glob (`personal/captures/*.md`) and filter by frontmatter. The filename is for human findability in the file tree.

**Frontmatter (canonical shape — written by the WorkDesk plugin):**

```yaml
---
type: capture
source-kind: voice-memo
transcribed-at: 2026-05-25T14:32:08Z
provider: groq
model: whisper-large-v3
---
```

- `type: capture` — discoverability flag for signals
- `source-kind` — `voice-memo` (only kind the plugin writes today; reserved for future `typed` etc.)
- `transcribed-at` — ISO timestamp with time-of-day, so signals can order captures within a day
- `provider` / `model` — STT pipeline that produced the transcript; useful when comparing transcription quality or auditing a bad capture

Signals filter by recency using either `transcribed-at` (most precise) or the filename's leading `{YYYY.MM.DD}` (cheap glob match).

**Body:** free-form. Voice memos land as the raw transcript. No required body structure.

Reference template at `config/templates/captures.md` for manual creation.

## Detection

- `daily-plan` may surface "{N} captures yesterday" as a low-priority hint when relevant to today's plan.
- `vault-improvements` may surface recurring themes as `[REVIEW]` inbox notifications when ≥3 captures within 14 days share a recognizable pattern (concept candidate, project candidate, or contradiction with `atlas/decisions/`).

No `[REVIEW]` for "you haven't captured today" — captures are on-demand. A missing capture is signal, not a gap.

## Cadence

On-demand. No promotion pipeline — patterns surface via `vault-improvements`; specific captures get processed when the operator asks Claude to read one. Captures don't graduate to other types on a schedule.
