---
name: process-transcripts
description: Process unprocessed transcripts in system/intake/ into atlas/meetings, atlas/decisions, atlas/people updates, and gtd/inbox proposals. Uses Gemini 3.1 Flash Lite as the structured extractor (~$0.002/transcript, 4s latency) and Claude for vault integration (wikilink resolution, matching cross-updates, file ops, verification). Operator-confirmed per transcript. Honors matching, action-item ownership, source-documentation, and the source-processing-pattern intake → process → archive flow.
---

# /process-transcripts

Move raw transcripts through the extraction pipeline into structured vault notes. Operator confirms each transcript before processing. Never auto-process in the background.

## Architecture

Two-model pipeline. Gemini does cheap structured extraction; Claude does the vault discipline work that Gemini can't.

```
intake/{slug}.md (verbatim)
        │
        ▼  config/scripts/extract-transcript-gemini.sh
Gemini 3.1 Flash Lite (~$0.002, ~4s)
        │  strict JSON schema (.claude/skills/process-transcripts/schema.json)
        │
        ▼  Claude (Opus or Sonnet via subagent)
   • Validate JSON
   • Resolve names → wikilinks (Glob over atlas/people/)
   • Network-scope filter for person notes
   • Write atlas/meetings/{slug}.md
   • Apply matching cross-updates
   • Route action items by owner_category
   • Move intake → transcripts/
   • check-wikilinks.sh on every touched file
```

The Gemini prompt + JSON schema live next to this file:
- [`prompt.txt`](prompt.txt)
- [`schema.json`](schema.json)

Both are versioned with the skill so changes are auditable.

## Invocation

- `/process-transcripts` — interactive, one transcript at a time
- `/process-transcripts {path}` — process a specific transcript
- `/process-transcripts --all` — process every unprocessed transcript without per-file confirmation (use sparingly)

## Source location

Per [[../../rules/source-processing-pattern]], unprocessed transcripts live in `system/intake/`. Processed transcripts get moved to `system/transcripts/` (the archive) only after every downstream artifact is produced AND verified. **Never process a transcript that's still in `system/transcripts/`** — that's the post-processing archive; if it's there it's already done.

## Phases (per transcript)

### 1. Pre-flight

Read the transcript's frontmatter. Verify:
- `processed: false`
- `source-kind: transcript`
- `source-format` is one of: `granola-public-api`, `google-meet-transcript`, `gemini-meet-transcript`

If `processed: true`, skip.

Pre-load vault context that downstream phases need (do this BEFORE the Gemini call so the wikilink resolution work in Phase 3 is fast):
- Glob `atlas/people/*.md` — list of person notes for wikilink resolution
- If meeting title or attendees match a known client, read `atlas/clients/{slug}/_brief.md` and `_status.md`
- If the meeting title matches a project, read its `_brief.md` and `_status.md`
- Recent `atlas/decisions/` (last 30 days) — for contradiction detection

### 2. Gemini extraction

Run the extraction script:

```bash
bash config/scripts/extract-transcript-gemini.sh {transcript-path} > /tmp/extraction.json
```

The script:
- Reads the prompt from `.claude/skills/process-transcripts/prompt.txt`
- Reads the schema from `.claude/skills/process-transcripts/schema.json`
- Calls Gemini 3.1 Flash Lite with `responseMimeType: application/json` + `responseSchema`
- Validates JSON parse
- Emits token usage to stderr, JSON to stdout

**On failure** (exit non-zero), see § Failure fallback below.

### 3. Mid-ingest checkpoint (high-stakes only)

If ANY of these apply, pause and present the Gemini-extracted summary + action item routing to the operator for confirmation BEFORE writing anything:

- Transcript title contains `[HIGH STAKES]` or `[CONFIDENTIAL]`
- Operator flagged it ahead of time
- Gemini returned `"sensitive": true`
- Gemini returned `"speaker_resolution_confidence": "low"`

For routine transcripts (Google Meet + Gemini high-confidence, work topics, sensitive=false), skip the checkpoint.

### 4. Wikilink resolution + vault-fit

Take the extracted JSON and convert names → wikilinks:

- For each name in `attendees_present`, `decisions[].made_by`, `action_items[].owner`, `people_observations[].person`: check if `atlas/people/{slug}.md` exists.
  - Exists → use `[[slug]]`
  - Doesn't exist → use plain text first-name (per [[../../rules/no-fabrication]] — never guess a last name). Note in step 5 for person-note proposal evaluation.

- For project mentions or client mentions: same pattern. Use existing wikilinks where they resolve; plain text otherwise.

**Confidence-driven attribution:**

| `speaker_resolution_confidence` | What to write in the meeting note |
|---|---|
| `high` | Names directly as quoted, with wikilinks where available |
| `partial` | Names with `(inferred)` marker if name didn't appear literally in the transcript text. Create a `[REVIEW]` inbox item proposing the meeting note for operator double-check. |
| `low` | Keep diarization labels (`Speaker A`, `Speaker B`); create a `[REVIEW]` flagging the gap |

### 5. Write the meeting note

`atlas/meetings/{YYYY-MM-DD}-{topic-slug}.md` per [[../../objects/meeting]]. Build from the extracted JSON:

Required body sections (always present):
- **Summary** — Gemini's `summary` field
- **Key Topics** — Gemini's `key_topics[]`
- **Decisions** — Gemini's `decisions[]` (inline routine ones; durable ones get standalone notes per step 6)
- **Action Items** — Gemini's `action_items[]` (full record; owner-based routing happens in step 7)
- **Source** — wikilink back to the intake transcript file

Optional sections (only when Gemini's arrays are non-empty):
- **Key Quotes** — `key_quotes[]`
- **People Observations** — `people_observations[]`
- **Open Questions** — `open_questions[]`

Frontmatter:
- `sensitive: true` if Gemini flagged it (see [[../../objects/meeting]] § Confidentiality)
- `attendees:` from `attendees_present[]` (wikilinks where they resolve, plain text otherwise)
- `transcript:` wikilink to the intake source

### 6. Apply matching

Update each touched entity in the same pass per [[../../rules/matching]]:

- **Attendees with vault notes** — add substantive new context from `people_observations[]` with inline footnote citation to the meeting note. For attendees without a vault note, decide per the network-scope filter in [[../../objects/person]]:
  - Person is in Khalil's direct network and meets ≥3-mention threshold → propose `[REVIEW]` for person note creation
  - Person is a clients'-client / homeowner / tertiary mention → mention by name in the meeting body; do NOT propose a person note
- **Decisions** — durable decisions (`durability: "durable"` from Gemini) get standalone `atlas/decisions/{date}-{slug}.md` notes. Routine ones stay inline.
- **Client / business `_status.md`** — substantive new context warrants an update.

### 7. Route action items by ownership

Use Gemini's `owner_category` enum:

| `owner_category` | Where it goes |
|---|---|
| `khalil_or_benali_team` | `gtd/inbox/[ACTION] {slug}.md` — one file per commitment, no cap |
| `client_team` | Stays inline in the meeting note's `## Action Items` section. If material, also add to the client's `_status.md` under a "Byrd-side open items" / equivalent section. **Do NOT create inbox entries.** |
| `client_client` | Inline only; no inbox, no client status. |
| `unknown` | Inline + create a `[QUESTION]` inbox item asking the operator to clarify ownership |

The meeting note's `## Action Items` section captures the **full record** — every commitment made in the room, regardless of owner. The inbox is Khalil's GTD surface only.

The `[REVIEW]` flood-guard cap (≤7 per session) applies to `[REVIEW]` proposals (uncertain inferences). It does NOT apply to `[ACTION]` items.

### 8. Flip source state and archive

Update intake-file frontmatter:
- `processed: true`
- `processed-into:` — list with wikilinks to meeting note + any standalone decisions + any new person notes + any inbox items

Then move the file: `system/intake/{filename}` → `system/transcripts/{filename}` via `mv`. The transcript stays in `system/transcripts/` permanently as the audit trail.

### 9. Verify

Run `bash config/scripts/check-wikilinks.sh` on:
- The new meeting note
- Any decision notes created
- Any person notes created or updated
- Any client/business `_status.md` updated
- The moved transcript file
- Any inbox items created

Zero broken required before declaring done. The script catches both `[[wikilinks]]` and backtick-style inbox references (`` `[ACTION] foo` ``).

### 10. Log

Hook fires `source-processed` and `object-created` events automatically. No manual log entry needed.

## Failure fallback

If `extract-transcript-gemini.sh` exits non-zero:

| Exit code | Cause | Action |
|---|---|---|
| 1 | Gemini API error (rate limit, malformed request, transient) | Retry once with a 5s backoff. If still failing, fall back to step 2. |
| 2 | Hard failure (auth, prompt/schema missing, transcript unreadable) | Stop. Surface the error. No fallback — the operator needs to fix infra. |
| 3 | Gemini output didn't parse as JSON | Retry once. If still failing, fall back to step 2. |

**Step 2 (Sonnet fallback):** Delegate to the `knowledge-management` subagent with `model: sonnet`. Subagent prompt MUST be self-contained per the existing delegation pattern (see § Delegation pattern below). Sonnet does the full synthesis the way the pre-Gemini skill did — slower and more expensive, but reliable.

**If Sonnet also fails:** Stop, surface to the operator. Do not silently downgrade further.

## Delegation pattern (when Gemini fallback fires, or for batch processing)

For long transcripts (≥500 utterances), batches of multiple transcripts, or when the operator wants to keep the main session light, delegate to a `knowledge-management` subagent with `model: sonnet`. Sonnet handles the extraction craft well at meaningfully lower cost than the main session's model.

The subagent prompt MUST be fully self-contained — it sees zero of the main session's context. Required elements:

1. **The intake file paths.**
2. **Operator-confirmed attendee list** (if known) — the actual people in the room, not just the calendar invitees.
3. **Calendar invitees who should NOT be treated as present** (e.g., Rick on Byrd design-group meetings).
4. **Existing person-note paths** for attendees, so the agent knows which wikilinks resolve.
5. **Client folder and active-project folder paths** for matching cross-updates.
6. **Rule files to read** — `config/objects/meeting.md`, `config/rules/source-processing-pattern.md`, `config/rules/matching.md`, `config/rules/no-fabrication.md`, `config/rules/double-entry-knowledge.md`, `config/rules/writing-style.md`, plus this skill.
7. **Known sensitive content** the meeting touches — so the agent sets `sensitive: true` proactively.
8. **Required output schema** — what files to produce, what files to update, what to move, what to verify with check-wikilinks.
9. **Final-report shape** — speaker resolution summary, files produced/updated, anything unexpected, open items.

The main session's role after dispatch: read both meeting notes end-to-end, spot-check matching, verify check-wikilinks ran clean.

## Confidentiality

If the meeting note carries `sensitive: true` (set by Gemini or by operator flag), apply confidentiality conventions per [[../../objects/meeting]] § Confidentiality:
- Internal traceability stays — meeting note links to transcript and people as usual
- Any content draft proposed from this meeting must anonymize identifying details
- Add a `[QUESTION]` if any insight is unusually identifiable and you're unsure whether it can be shared externally

**Sensitive transcripts still go through the Gemini extraction path.** The data is already in WorkDesk OS (a third-party indexable surface). Sending the verbatim to Gemini's API doesn't materially change the trust posture, and the cost/latency savings are real. If you want a "Gemini-bypass for sensitive content" gate, add it explicitly via operator instruction — don't infer it from `sensitive: true`.

## Cost reference

| Path | Cost per transcript | Latency | Quality |
|---|---|---|---|
| Gemini 3.1 Flash Lite + Claude integration (default) | ~$0.05-$0.10 | ~10-30s | Validated on Google Meet + Granola test set; high on name-resolved, partial on diarization |
| Sonnet subagent (fallback) | ~$0.30-$0.50 | ~1-2 min | Reliable; less consistent on schema discipline |
| Opus in main session | ~$1-$2 | ~2-5 min | Highest quality; reserved for sensitive/high-stakes when manually invoked |

## What NOT to do

- **Don't fabricate attendees.** If Gemini returned a name not in the transcript, drop it. Per [[../../rules/no-fabrication]].
- **Don't treat the Granola/Google `attendees-from-source` field as ground truth.** That's the calendar invite list, not actual presence. Use Gemini's `attendees_present` (which is grounded in transcript speaker turns).
- **Don't fill timeline gaps.** If the transcript jumps topics, don't reconstruct what was missed.
- **Don't guess speaker names when Gemini returned `low` confidence.** Plain `Speaker X (unidentified)` + `[REVIEW]` beats fabrication.
- **Don't create person notes for clients' clients** (homeowners, prospects, tertiary mentions). Per [[../../objects/person]] network-scope filter.
- **Don't create inbox `[ACTION]` items for `client_team` commitments.** Per [[../../objects/action]] ownership filter and Gemini's owner_category enum.
- **Don't apply the `[REVIEW]` flood-guard cap to `[ACTION]` items** — every Khalil/Benali-team commitment becomes its own file.
- **Don't process a transcript without operator confirmation in interactive mode.**
- **Don't synthesize from Gemini's Tab-1 Notes summary or any pre-baked summary** — the pipeline runs against the verbatim only. Per [[../../rules/source-processing-pattern]].
- **Don't move the transcript out of `system/intake/`** until every downstream artifact is produced AND verified clean.
- **Don't tweak `prompt.txt` or `schema.json` without re-testing.** Both live next to this file and are easy to iterate, but every change should be smoke-tested on at least one Granola + one Google Meet transcript before being treated as production.
