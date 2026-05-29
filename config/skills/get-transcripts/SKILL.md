---
name: get-transcripts
description: Pull raw verbatim transcripts from Granola (meetings, notes, phone calls), Google Meet standalone Transcript Docs, AND the verbatim Transcript tab inside "Notes by Gemini" Docs — into system/intake/ via three ETL scripts. Pure script orchestration — no AI synthesis, no tokens spent on extraction. Idempotent (skips already-pulled). Default lookback 7 days; flags for 14d / backfill / dry-run / status / single-source. Use when the operator says "get transcripts", "pull transcripts", "grab the last N days of transcripts", or before /process-transcripts.
---

# /get-transcripts

Pull the last N days of verbatim transcripts into `system/intake/`. Wraps three pure-ETL scripts — no LLM tokens spent on extraction — so what lands in intake is the raw source, not a summary.

## Invocation

- `/get-transcripts` — default 7-day lookback, all three sources
- `/get-transcripts --days 14` — 2-week lookback (auto-applies `--backfill` since >7)
- `/get-transcripts --days 30 --backfill` — 30-day backfill (explicit)
- `/get-transcripts --source granola` — Granola only
- `/get-transcripts --source google` — Google Meet standalone Transcript Docs only
- `/get-transcripts --source gemini` — "Notes by Gemini" Docs only (Transcript tab)
- `/get-transcripts --dry-run` — list what would pull, no writes
- `/get-transcripts --status` — show state files only, no pull

## What it does

Runs three pure-ETL scripts in parallel when no `--source` filter is given (their state files are disjoint, so concurrent runs are safe):

| Source | Script | Captures | Source-id field |
|---|---|---|---|
| Granola (meetings, phone calls, in-person notes) | `config/scripts/pull-granola.sh` | Verbatim transcript via `/v1/notes/{id}?include=transcript`. Diarization labels (Speaker A, B, …) — speaker resolution happens at processing time. | `granola-note-id` |
| Google Meet standalone Transcript Docs (Drive Docs named `"…- Transcript"`) | `config/scripts/pull-google-transcripts.sh` | Single-tab Doc, exported as plain text via Drive export. Speakers are name-resolved by Google. | `google-drive-file-id` |
| "Notes by Gemini" Docs (Transcript tab only) | `config/scripts/pull-gemini-transcripts.sh` | Tab-2 verbatim transcript via Docs API with `includeTabsContent: true`. Speakers are name-resolved by Google. Source enumeration goes through Calendar (the `Notes by Gemini` attachment), not Drive search — the Docs don't have a stable name pattern. | `gemini-doc-id` |

**All three scripts write to `system/intake/`** with `source-kind: transcript` frontmatter and `processed: false`. All three are idempotent: re-running skips anything already on disk (in intake or in the `system/transcripts/` archive) by source id.

**Why three scripts instead of two?** Google Meet emits two different artifact shapes per recorded meeting: (1) a standalone Doc named "<Title> - DATE TIME TZ - Transcript", or (2) a "Notes by Gemini" Doc whose first tab is the AI summary and whose second tab is the verbatim. Drive's text/plain export only returns the first tab, so shape (2) was structurally invisible to `pull-google-transcripts.sh`. Many meetings emit ONLY shape (2) — they were silently missing until `pull-gemini-transcripts.sh` was added. Running all three catches every transcribed meeting Workspace produced.

## Phases

### 1. Show status first (always)

Run all selected scripts with `--status` and surface the result. The operator should see:

- Last successful pull (timestamp + hours ago)
- Consecutive failures (if any)
- HEALTH: ok / STALE

If any source shows `HEALTH: STALE` (>36h since last success) or `consecutive_fails ≥ 1`, call that out — auth or API issues need fixing before the pull will succeed.

### 2. Decide flags

- `--days N`:
  - No arg → 7
  - `N ≤ 7` → pass through as-is
  - `N > 7` → pass with `--backfill` (the scripts hard-fail on >7 without backfill, as a guard rail)
- `--source`:
  - No arg → run all three
  - `granola` → only `pull-granola.sh`
  - `google` → only `pull-google-transcripts.sh`
  - `gemini` → only `pull-gemini-transcripts.sh`
- `--dry-run` and `--status` pass through.

### 3. Run pulls

When all three sources are selected, run them in parallel (separate Bash tool calls in one message). They write to different state files (`config/state/pull-granola.json`, `config/state/pull-google.json`, `config/state/pull-gemini.json`) and the same intake dir, but the idempotency check happens per-file with id grep, so parallel writes are safe.

Capture the tail of each log:

```
INFO   done: pulled=N skipped=N failed=N
```

If `failed > 0`, surface the error lines (`grep ERROR` on the log) — don't bury them. The exit code distinguishes:
- `0` — success (may be zero pulls)
- `1` — partial (some files failed; state file updated with `consecutive_failures` increment)
- `2` — hard failure (auth, bad args, API unreachable)

### 4. Summarize

Report concisely to the operator:

```
Granola:      pulled=N skipped=N failed=N
Google Meet:  pulled=N skipped=N failed=N
Gemini Docs:  pulled=N skipped=N stub=N no_access=N failed=N
Now in system/intake/ (transcripts only): N

Next: /process-transcripts to extract into atlas/meetings, decisions, people.
```

Gemini-specific counts to expose:
- **stub** — Notes-by-Gemini Doc exists but its Transcript tab is below the 500-char threshold (transcription failed; usually multilingual or silent meeting). Skipped permanently.
- **no_access** — calendar event has a Notes-by-Gemini attachment but the Doc lives in another organizer's Drive and isn't shared. 403/404 — skipped permanently, not counted as failure.

If anything failed (true `failed > 0`), point at the log files:
- `system/cron-pull-granola.log`
- `system/cron-pull-google-transcripts.log`
- `system/cron-pull-gemini-transcripts.log`

### 5. Verify (when ≥1 new file pulled)

Spot-check that frontmatter is well-formed on one new file from each source. Specifically:
- `source-kind: transcript`
- `processed: false`
- `source-format: granola-public-api`, `google-meet-transcript`, or `gemini-meet-transcript`
- A transcript body present under `## Transcript`

Do NOT process — that's `/process-transcripts`'s job.

### 6. Cross-source overlap

A single human meeting may produce intake files from multiple sources (e.g., Granola was recording AND a Google Meet transcript was generated AND Gemini Notes was on). This is **by design** — cross-source dedupe happens at `/process-transcripts` time, where the operator picks the strongest source per meeting (Granola for phone calls and diarized speakers; Google/Gemini for name-resolved speakers; whichever has the cleanest text). At pull time, all three land in intake with distinct source-ids.

If the operator asks "did I get duplicates", run:
```bash
grep -l '^date: <YYYY-MM-DD>$' system/intake/*.md | xargs grep -l '^source-kind: transcript$'
```
and look for same-day files with overlapping titles.

## Failure modes and recovery

| Symptom | Likely cause | Fix |
|---|---|---|
| `ERROR  could not read PERSONAL_GRANOLA_API_KEY from Infisical` | Infisical session expired | `infisical login`, then re-run |
| `ERROR  gws auth failed` | gws token expired or ramdisk unmounted | `gws auth login --account khalil@benali.com`, then `bash config/scripts/gws-push-tokens-to-infisical.sh` per [[../../config/rules/tools/gws]] |
| All scripts hard-fail (exit 2) at boot | Infisical Agent hasn't rendered the ramdisk yet | Wait ~30s after login, or check `/Volumes/wd-ramdisk/` |
| `consecutive_fails > 3` | Auth has been broken for multiple cron runs | Always check `--status` first; run remediation above |
| Gemini script reports `no_access > 0` | Meeting was organized by someone else and they didn't share the Notes-by-Gemini Doc | Expected and harmless — those transcripts live in the organizer's Drive. Ask them to share (View access is enough) and the next run picks them up. |
| Gemini script reports `stub > 0` | Gemini transcription failed for that meeting (multilingual, silent, or under the language threshold) | The recording still exists in Drive — would need self-hosted transcription (Whisper) to recover. Out of scope for this skill. |

## What NOT to do

- **Don't synthesize transcripts during this skill.** Synthesis is `/process-transcripts`'s job — see [[../../config/rules/source-processing-pattern]] ("Don't synthesize from an upstream summary when the verbatim source is available"). `/get-transcripts` ends when the raw transcript is on disk in `system/intake/`.
- **Don't pull from Granola's summary endpoint, Gemini's Notes tab (tab 1), or any AI-generated summary.** The scripts pull verbatim only — Granola via `?include=transcript`, Google standalone via the Doc named "<Title> - … - Transcript", Gemini via the Transcript tab (tab 2) of the Notes-by-Gemini Doc. The Notes tab is explicitly skipped per [[../../config/rules/source-processing-pattern]].
- **Don't change the scripts' default behavior without a corresponding rule update.** The scripts also run via cron (daily); divergence between the manual and cron paths breaks the audit log in `config/state/pull-*.json`.
- **Don't move pulled files out of `system/intake/`** in this skill. The intake → process → archive flow is enforced by [[../../config/rules/source-processing-pattern]]; only `/process-transcripts` moves files to `system/transcripts/`.
- **Don't run with `--days > 14` casually.** The cron runs daily; if state shows last success <2 days ago, `--days 7` (default) is plenty. Wider lookback is for catching up after auth outages.
- **Don't claim done if any pull reported `failed > 0`.** The `stub` and `no_access` counters are NOT failures — they're tracked permanent skips. Only `failed > 0` warrants investigation.
- **Don't dedupe across sources at pull time.** Same human meeting captured by multiple sources is by design — `/process-transcripts` is where the operator picks the strongest verbatim per meeting.

## Cron coexistence

The pull scripts may also run via daily cron. Running this skill manually does NOT conflict — the scripts use atomic writes (`mv tmp → final`) and per-file-id idempotency. Two simultaneous runs would each pull, the second would find the first's files via grep and skip. The only race is the state-file write, which is also atomic via `mv`.

Note: as of 2026-05-28, the Granola cron entry has been removed (cron environment lacks an Infisical session, causing repeated auth failures). Run Granola pulls manually via this skill, which inherits the interactive Infisical session. The Google and Keep.md crons remain — they auth through the Infisical Agent + RAM disk pattern that works in cron.

## Source

- Operator instruction 2026-05-28 — "make this a skill you can reliably run to get-transcripts" (session creating this skill).
- Operator correction 2026-05-28 (same session) — "Notes by Gemini docs have two tabs; tab 2 is the full raw transcript." Added the third script (`pull-gemini-transcripts.sh`) to capture this previously-missed source.
- Underlying scripts: `config/scripts/pull-granola.sh`, `config/scripts/pull-google-transcripts.sh`, `config/scripts/pull-gemini-transcripts.sh`.
- Source seed: `config/sources/transcript.md`.
- Related: [[process-transcripts]] (the next step after pulling).
