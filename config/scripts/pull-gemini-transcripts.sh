#!/usr/bin/env bash
# pull-gemini-transcripts.sh — Daily ETL pull of Google Meet "Notes by Gemini"
# verbatim transcripts (Tab 2) into system/intake/.
#
# Pure ETL. No AI tokens. Idempotent (skips docs already pulled, by
# gemini-doc-id across system/intake/ and system/transcripts/).
#
# Why a separate script from pull-google-transcripts.sh:
#
#   Meet generates TWO kinds of artifacts in Drive per recorded meeting:
#     1. A standalone Doc literally named "<Title> - YYYY/MM/DD HH:MM TZ - Transcript"
#        — full verbatim, single-tab.  pull-google-transcripts.sh handles these.
#     2. A "Notes by Gemini" Doc with TWO tabs: Notes (AI summary) + Transcript
#        (full verbatim).  Drive's text/plain export only returns the first tab,
#        so it misses the verbatim entirely.  This script reaches it via the
#        Docs API with `includeTabsContent: true` and extracts only the
#        Transcript tab.
#
#   Meetings vary: some get only (1), some only (2), some both, some neither.
#   Running both scripts catches every transcribed meeting Workspace produced.
#
# Source enumeration goes through Calendar (not Drive search) because the
# Gemini Docs don't have a stable name pattern — they're titled after the
# meeting and look identical to user-authored docs.  The calendar attachment
# `title: "Notes by Gemini"` is the only reliable signal.
#
# Usage:
#   bash config/scripts/pull-gemini-transcripts.sh                         # default: --days 1
#   bash config/scripts/pull-gemini-transcripts.sh --days 7
#   bash config/scripts/pull-gemini-transcripts.sh --days 30 --backfill    # >7 requires --backfill
#   bash config/scripts/pull-gemini-transcripts.sh --dry-run
#   bash config/scripts/pull-gemini-transcripts.sh --doc-id <id> --force
#   bash config/scripts/pull-gemini-transcripts.sh --status
#   bash config/scripts/pull-gemini-transcripts.sh --help
#
# Exit codes:
#   0  success (may include zero new pulls)
#   1  partial — some docs failed to pull
#   2  hard failure (auth, bad args, API unreachable)

set -uo pipefail

# ── Constants ────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
INTAKE_DIR="$VAULT_ROOT/system/intake"
TRANSCRIPTS_DIR="$VAULT_ROOT/system/transcripts"
STATE_FILE="$VAULT_ROOT/config/state/pull-gemini.json"
LOG_FILE="$VAULT_ROOT/system/cron-pull-gemini-transcripts.log"
SOURCE_FORMAT="gemini-meet-transcript"

# Skip Gemini Docs whose Transcript tab is below this character count — those
# are the stub messages Gemini writes when transcription failed (multilingual,
# silent meeting, etc.).  500 chars is well below any real meeting (a 1-minute
# back-and-forth runs ~1500 chars) and well above the stub template (~200).
MIN_TRANSCRIPT_CHARS=500

# ── Defaults ─────────────────────────────────────────────────────────────────
DAYS=1
BACKFILL=0
DRY_RUN=0
FORCE_DOC_ID=""
FORCE=0
SHOW_STATUS=0

# ── Helpers ──────────────────────────────────────────────────────────────────
log() {
  local ts
  ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  printf '%s %s\n' "$ts" "$*" | tee -a "$LOG_FILE" >&2
}

slug_from_title() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' \
    | cut -c1-80
}

# Convert ISO timestamp (with optional offset) to operator-local YYYY-MM-DD
iso_to_local_date() {
  local ts="$1"
  # Strip fractional seconds and any timezone offset/Z; treat as UTC.
  local clean="${ts%%.*}"
  clean="${clean%Z}"
  # If the timestamp carries an offset like "2026-05-19T10:30:00-05:00",
  # GNU/BSD `date -j -f` can't parse it directly — keep just YYYY-MM-DD as a
  # cheap and reliable approximation; the operator-local date matches the
  # offset already in the calendar timestamp.
  if [[ "$ts" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[+-][0-9]{2}:[0-9]{2}$ ]]; then
    printf '%s' "${ts:0:10}"
    return
  fi
  TZ=UTC date -j -f "%Y-%m-%dT%H:%M:%S" "$clean" "+%s" 2>/dev/null \
    | xargs -I {} date -r {} "+%Y-%m-%d" 2>/dev/null
}

write_state() {
  local content="$1"
  mkdir -p "$(dirname "$STATE_FILE")"
  local tmp="$STATE_FILE.tmp.$$"
  printf '%s\n' "$content" > "$tmp"
  mv "$tmp" "$STATE_FILE"
}

read_state_field() {
  local field="$1"
  local default="$2"
  if [[ -f "$STATE_FILE" ]]; then
    jq -r --arg field "$field" --arg default "$default" \
      '(.[$field] // $default)' "$STATE_FILE" 2>/dev/null \
      || printf '%s' "$default"
  else
    printf '%s' "$default"
  fi
}

# ── Parse args ──────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --days)     DAYS="$2"; shift 2 ;;
    --backfill) BACKFILL=1; shift ;;
    --dry-run)  DRY_RUN=1; shift ;;
    --doc-id)   FORCE_DOC_ID="$2"; FORCE=1; shift 2 ;;
    --force)    FORCE=1; shift ;;
    --status)   SHOW_STATUS=1; shift ;;
    --help|-h)
      sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown flag: $1" >&2
      echo "Try: $0 --help" >&2
      exit 2
      ;;
  esac
done

# ── --status ────────────────────────────────────────────────────────────────
if [[ $SHOW_STATUS -eq 1 ]]; then
  echo "Gemini Meet transcripts pull status:"
  if [[ -f "$STATE_FILE" ]]; then
    jq -r '
      "  last_success_at:    \(.last_success_at // "never")",
      "  last_failure_at:    \(.last_failure_at // "never")",
      "  consecutive_fails:  \(.consecutive_failures // 0)",
      "  files_last_run:     \(.last_run_pulled // 0)",
      "  last_run_at:        \(.last_run_at // "never")"
    ' "$STATE_FILE"
    last_success="$(jq -r '.last_success_at // empty' "$STATE_FILE")"
    if [[ -n "$last_success" ]]; then
      last_epoch="$(TZ=UTC date -j -f "%Y-%m-%dT%H:%M:%SZ" "${last_success%.*Z}Z" "+%s" 2>/dev/null || echo 0)"
      now_epoch="$(date -u "+%s")"
      delta_h=$(( (now_epoch - last_epoch) / 3600 ))
      echo "  hours_since_success: $delta_h"
      if [[ $delta_h -gt 36 ]]; then
        echo "  HEALTH: STALE (last success > 36h ago)"
      else
        echo "  HEALTH: ok"
      fi
    fi
  else
    echo "  (no state file — script has never run successfully)"
  fi
  exit 0
fi

# ── Validate args ───────────────────────────────────────────────────────────
if [[ -n "$FORCE_DOC_ID" && $FORCE -eq 0 ]]; then
  echo "Error: --doc-id requires --force" >&2
  exit 2
fi

if [[ "$DAYS" -gt 7 && $BACKFILL -eq 0 && -z "$FORCE_DOC_ID" ]]; then
  echo "Error: --days $DAYS > 7 requires --backfill" >&2
  exit 2
fi

# Auto-extend lookback if last success was older than --days
last_success_at="$(read_state_field "last_success_at" "")"
if [[ -n "$last_success_at" && -z "$FORCE_DOC_ID" && $BACKFILL -eq 0 ]]; then
  last_epoch="$(TZ=UTC date -j -f "%Y-%m-%dT%H:%M:%SZ" "$last_success_at" "+%s" 2>/dev/null || echo 0)"
  now_epoch="$(date -u "+%s")"
  delta_days=$(( (now_epoch - last_epoch + 86399) / 86400 ))
  if [[ $delta_days -gt $DAYS ]]; then
    log "INFO   last success was $delta_days days ago; extending lookback from $DAYS to $delta_days"
    DAYS=$delta_days
  fi
fi

mkdir -p "$INTAKE_DIR" "$(dirname "$STATE_FILE")"

# ── Pre-flight ──────────────────────────────────────────────────────────────
if ! command -v gws >/dev/null 2>&1; then
  log "ERROR  gws CLI not on PATH"
  exit 2
fi

# ── Ramdisk readiness gate ──────────────────────────────────────────────────
# gws reads OAuth state from ~/Library/Application Support/gws, a symlink to the
# Infisical-rendered ramdisk. At boot/login the Infisical Agent renders those
# files asynchronously; a cron firing before the render (e.g. the 06:10 daily
# run vs. a later login) sees a dangling symlink. That is infra-not-ready, NOT
# an auth failure — wait briefly for the render, then skip cleanly without
# bumping consecutive_failures, so STALE only ever reflects genuine auth death.
GWS_STATE_DIR="$HOME/Library/Application Support/gws"
gws_state_rendered() {
  local f
  for f in "$GWS_STATE_DIR"/credentials.*.enc; do
    [[ -e "$f" ]] || return 1   # unmatched glob stays literal → no creds rendered
    break
  done
  [[ -s "$GWS_STATE_DIR/client_secret.json" ]]
}
if ! gws_state_rendered; then
  for _ in 1 2 3 4 5 6; do
    sleep 10
    gws_state_rendered && break
  done
fi
if ! gws_state_rendered; then
  log "INFO   gws state not rendered on ramdisk yet (Infisical Agent not ready) — skipping; will retry next run"
  exit 0
fi

if ! gws drive about get --params '{"fields": "user(emailAddress)"}' >/dev/null 2>&1; then
  log "ERROR  gws auth failed — run \`gws auth login --account you@example.com\`"
  prev_fails="$(read_state_field "consecutive_failures" "0")"
  new_fails=$(( prev_fails + 1 ))
  write_state "$(jq -n \
    --arg last_failure "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    --argjson fails "$new_fails" \
    --arg prev_success "$last_success_at" \
    '{
       last_success_at: ($prev_success | select(. != "")),
       last_failure_at: $last_failure,
       consecutive_failures: $fails,
       last_run_at: $last_failure,
       last_run_pulled: 0
     }')"
  exit 2
fi

# ── Cutoff ──────────────────────────────────────────────────────────────────
CUTOFF_EPOCH=$(( $(date -u "+%s") - DAYS * 86400 ))
CUTOFF_ISO="$(date -u -r "$CUTOFF_EPOCH" "+%Y-%m-%dT%H:%M:%SZ")"
NOW_ISO="$(date -u "+%Y-%m-%dT%H:%M:%SZ")"

log "INFO   starting Gemini Meet pull (days=$DAYS dry_run=$DRY_RUN force_doc=${FORCE_DOC_ID:-none} cutoff=$CUTOFF_ISO)"

# ── Write intake file for one Gemini Doc ────────────────────────────────────
# Args: <doc_id> <event_title> <event_start_iso> <event_organizer> <attendees_json>
write_intake_for_doc() {
  local doc_id="$1"
  local event_title="$2"
  local event_start="$3"
  local event_organizer="$4"
  local attendees_json="$5"

  # Cheap idempotency check first — skip the Docs API call entirely if we
  # already have this doc on disk
  if [[ $FORCE -eq 0 || "$FORCE_DOC_ID" != "$doc_id" ]]; then
    if grep -rlq "^gemini-doc-id: ${doc_id}[[:space:]]*\$" "$INTAKE_DIR" "$TRANSCRIPTS_DIR" 2>/dev/null; then
      log "SKIP   $doc_id already-pulled (pre-fetch)"
      return 2
    fi
  fi

  # Fetch the Doc with all tab content.  Capture output unconditionally —
  # gws prints the API error JSON to stdout AND exits non-zero on 403/404,
  # so we need to inspect the body regardless of exit code.  403 (no
  # permission) and 404 (not found) happen when the meeting was organized
  # by someone else and they didn't share the Gemini Doc.  Those are
  # permanent: don't count as retryable failure or consecutive_failures
  # climbs every run.
  local doc_json; doc_json="$(mktemp)"
  gws docs documents get \
    --params "$(jq -n --arg id "$doc_id" '{documentId:$id, includeTabsContent:true}')" \
    --format json > "$doc_json" 2>/dev/null || true

  if [[ ! -s "$doc_json" ]]; then
    log "ERROR  $doc_id docs.get returned empty (gws or network failure)"
    rm -f "$doc_json"
    return 4
  fi

  local api_err_code
  api_err_code="$(jq -r '.error.code // empty' "$doc_json" 2>/dev/null)"
  if [[ -n "$api_err_code" ]]; then
    if [[ "$api_err_code" == "403" || "$api_err_code" == "404" ]]; then
      log "SKIP   $doc_id no-access (code=$api_err_code, owner has not shared) title=\"$event_title\""
      rm -f "$doc_json"
      return 5
    fi
    log "ERROR  $doc_id docs.get api error code=$api_err_code"
    rm -f "$doc_json"
    return 4
  fi

  # Extract only the Transcript tab text
  local transcript_text
  transcript_text="$(jq -r '
    .tabs[]?
    | select(.tabProperties.title == "Transcript")
    | .documentTab.body.content[]?
    | .paragraph?.elements[]?
    | .textRun?.content // empty
  ' "$doc_json" | awk 'BEGIN{ORS=""} {print}')"

  local size=${#transcript_text}

  if [[ $size -lt $MIN_TRANSCRIPT_CHARS ]]; then
    log "SKIP   $doc_id stub-transcript size=${size}b title=\"$event_title\""
    rm -f "$doc_json"
    return 1
  fi

  # Derive filename
  local local_date slug filename target_path
  local_date="$(iso_to_local_date "$event_start")"
  [[ -z "$local_date" ]] && local_date="$(date "+%Y-%m-%d")"
  slug="$(slug_from_title "$event_title")"
  [[ -z "$slug" ]] && slug="$(printf 'untitled-%s' "${doc_id:0:8}" | tr 'A-Z' 'a-z')"
  filename="${local_date}-${slug}.md"
  target_path="$INTAKE_DIR/$filename"

  # Filename collision handling — different doc landing on same filename
  if [[ -e "$target_path" ]]; then
    if grep -q "^gemini-doc-id: ${doc_id}[[:space:]]*\$" "$target_path" 2>/dev/null; then
      if [[ $FORCE -eq 1 && "$FORCE_DOC_ID" == "$doc_id" ]]; then
        : # fall through, overwrite
      else
        log "SKIP   $doc_id already-pulled (in intake) → $filename"
        rm -f "$doc_json"
        return 2
      fi
    else
      local short_suffix="${doc_id:0:6}"
      filename="${local_date}-${slug}-${short_suffix}.md"
      target_path="$INTAKE_DIR/$filename"
      log "INFO   filename collision avoided via suffix → $filename"
    fi
  fi

  if [[ $DRY_RUN -eq 1 ]]; then
    log "DRY    $doc_id WOULD pull → $filename (\"$event_title\" $local_date, ${size}b)"
    rm -f "$doc_json"
    return 3
  fi

  # Build attendee YAML from event attendee list (passed in by caller)
  local attendees_yaml
  attendees_yaml="$(printf '%s' "$attendees_json" | jq -r '
    (. // []) | .[] | "  - \"\(.displayName // (.email | split("@")[0])) <\(.email)>\""
  ' 2>/dev/null)"
  [[ -z "$attendees_yaml" ]] && attendees_yaml='  - "(none captured on event)"'

  local pulled_at drive_url
  pulled_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  drive_url="https://docs.google.com/document/d/$doc_id"

  local tmp="$target_path.tmp.$$"
  {
    printf -- '---\n'
    printf -- 'type: source\n'
    printf -- 'source-kind: transcript\n'
    printf -- 'date: %s\n' "$local_date"
    printf -- 'processed: false\n'
    printf -- 'processed-into: []\n'
    printf -- 'title: %s\n' "$(printf '%s' "$event_title" | jq -Rs '.')"
    printf -- 'gemini-doc-id: %s\n' "$doc_id"
    printf -- 'gemini-doc-url: %s\n' "$drive_url"
    printf -- 'event-start: %s\n' "$event_start"
    printf -- 'event-organizer: %s\n' "$event_organizer"
    printf -- 'attendees-from-source:\n'
    printf -- '%s\n' "$attendees_yaml"
    printf -- 'source-format: %s\n' "$SOURCE_FORMAT"
    printf -- 'pulled-at: %s\n' "$pulled_at"
    printf -- '---\n\n'
    printf -- '# %s — %s (raw transcript)\n\n' "$event_title" "$local_date"
    printf -- 'Verbatim transcript extracted from the "Notes by Gemini" Google Doc, **Transcript** tab. Speakers are name-resolved by Google (e.g., "Jane Doe: ..."). The Gemini-generated summary on the Notes tab is intentionally NOT pulled per [[../../config/rules/source-processing-pattern]] — synthesis happens at processing time from the verbatim, not from another system'"'"'s summary.\n\n'
    printf -- '## Transcript\n\n'
    printf -- '%s' "$transcript_text"
    printf -- '\n'
  } > "$tmp"

  mv "$tmp" "$target_path"
  rm -f "$doc_json"

  log "PULL   $doc_id → $filename (${size}b) \"$event_title\""
  return 0
}

# ── Forced single-doc path ──────────────────────────────────────────────────
if [[ -n "$FORCE_DOC_ID" ]]; then
  # No calendar context — pull minimal info from the Doc itself
  meta="$(gws docs documents get --params \
    "$(jq -n --arg id "$FORCE_DOC_ID" '{documentId:$id, includeTabsContent:false}')" \
    --format json 2>/dev/null)"
  if [[ -z "$meta" ]]; then
    log "ERROR  $FORCE_DOC_ID metadata fetch failed"
    exit 2
  fi
  title="$(printf '%s' "$meta" | jq -r '.title // "Untitled"')"
  write_intake_for_doc "$FORCE_DOC_ID" "$title" "$NOW_ISO" "(forced)" "[]"
  rc=$?
  pulled=0
  [[ $rc -eq 0 || $rc -eq 3 ]] && pulled=1
  write_state "$(jq -n \
    --arg now "$NOW_ISO" \
    --argjson pulled "$pulled" \
    '{
       last_success_at: $now,
       last_failure_at: null,
       consecutive_failures: 0,
       last_run_at: $now,
       last_run_pulled: $pulled
     }')"
  exit 0
fi

# ── List calendar events with Notes-by-Gemini attachments ───────────────────
TIME_MAX_ISO="$NOW_ISO"
PARAMS_JSON="$(jq -n --arg tmin "$CUTOFF_ISO" --arg tmax "$TIME_MAX_ISO" \
  '{calendarId:"primary", timeMin:$tmin, timeMax:$tmax, singleEvents:true, orderBy:"startTime", maxResults:250}')"

events_json="$(mktemp)"
trap 'rm -f "$events_json"' EXIT

if ! gws calendar events list --params "$PARAMS_JSON" --format json > "$events_json" 2>/dev/null; then
  log "ERROR  gws calendar events list failed"
  prev_fails="$(read_state_field "consecutive_failures" "0")"
  new_fails=$(( prev_fails + 1 ))
  write_state "$(jq -n \
    --arg now "$NOW_ISO" \
    --argjson fails "$new_fails" \
    --arg prev_success "$last_success_at" \
    '{
       last_success_at: ($prev_success | select(. != "")),
       last_failure_at: $now,
       consecutive_failures: $fails,
       last_run_at: $now,
       last_run_pulled: 0
     }')"
  exit 2
fi

# Extract: doc_id <TAB> event_title <TAB> event_start <TAB> organizer_email <TAB> attendees_json
docs_tsv="$(mktemp)"
jq -r '
  .items[]?
  | select(.attachments != null)
  | . as $e
  | .attachments[]?
  | select(.title == "Notes by Gemini")
  | [
      .fileId,
      ($e.summary // "Untitled meeting"),
      ($e.start.dateTime // $e.start.date),
      ($e.organizer.email // "?"),
      ($e.attendees // [] | tostring)
    ]
  | @tsv
' "$events_json" > "$docs_tsv"

total_found=$(wc -l < "$docs_tsv" | tr -d ' ')
log "INFO   found $total_found Notes-by-Gemini attachments in calendar since $CUTOFF_ISO"

pulled=0
skipped=0
stub=0
no_access=0
failed=0

while IFS=$'\t' read -r doc_id event_title event_start event_organizer attendees_json; do
  [[ -z "$doc_id" ]] && continue
  write_intake_for_doc "$doc_id" "$event_title" "$event_start" "$event_organizer" "$attendees_json"
  case $? in
    0) pulled=$((pulled + 1)) ;;
    1) stub=$((stub + 1)) ;;
    2) skipped=$((skipped + 1)) ;;
    3) pulled=$((pulled + 1)) ;;
    5) no_access=$((no_access + 1)) ;;
    *) failed=$((failed + 1)) ;;
  esac
  sleep 0.2
done < "$docs_tsv"
rm -f "$docs_tsv"

# ── State + summary ─────────────────────────────────────────────────────────
now="$NOW_ISO"
if [[ $failed -eq 0 ]]; then
  if [[ $DRY_RUN -eq 1 ]]; then
    log "INFO   done (dry-run): pulled=$pulled skipped=$skipped stub=$stub no_access=$no_access failed=0 (state file NOT updated)"
  else
    write_state "$(jq -n \
      --arg now "$now" \
      --argjson pulled "$pulled" \
      '{
         last_success_at: $now,
         last_failure_at: null,
         consecutive_failures: 0,
         last_run_at: $now,
         last_run_pulled: $pulled
       }')"
    log "INFO   done: pulled=$pulled skipped=$skipped stub=$stub no_access=$no_access failed=0"
  fi
  exit 0
else
  prev_fails="$(read_state_field "consecutive_failures" "0")"
  new_fails=$(( prev_fails + 1 ))
  prev_success="$(read_state_field "last_success_at" "")"
  write_state "$(jq -n \
    --arg now "$now" \
    --argjson pulled "$pulled" \
    --argjson fails "$new_fails" \
    --arg prev_success "$prev_success" \
    '{
       last_success_at: ($prev_success | select(. != "")),
       last_failure_at: $now,
       consecutive_failures: $fails,
       last_run_at: $now,
       last_run_pulled: $pulled
     }')"
  log "WARN   partial: pulled=$pulled skipped=$skipped stub=$stub no_access=$no_access failed=$failed consec_fails=$new_fails"
  exit 1
fi
