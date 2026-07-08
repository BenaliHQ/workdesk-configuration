#!/usr/bin/env bash
# pull-google-transcripts.sh — Daily ETL pull of Google Meet transcripts into
# system/intake/.
#
# Pure ETL. No AI tokens. Idempotent (skips docs already pulled, by
# google-drive-file-id across system/intake/ and system/transcripts/).
#
# Uses the `gws` CLI (Google Workspace) which handles OAuth via local cache.
# Lists Google Docs owned by the operator with names matching the Meet
# transcript convention "<Title> - YYYY/MM/DD HH:MM TZ - Transcript", exports
# each as plain text, and writes a markdown file conforming to the transcript
# source seed.
#
# Cross-source dedupe (against Granola pulls) is intentionally deferred to the
# processing pass — both sources land in intake and `/process-transcripts`
# merges or chooses per operator-confirmed rules.
#
# Usage:
#   bash config/scripts/pull-google-transcripts.sh                         # default: --days 1
#   bash config/scripts/pull-google-transcripts.sh --days 7
#   bash config/scripts/pull-google-transcripts.sh --days 30 --backfill    # >7 requires --backfill
#   bash config/scripts/pull-google-transcripts.sh --dry-run
#   bash config/scripts/pull-google-transcripts.sh --file-id <id> --force
#   bash config/scripts/pull-google-transcripts.sh --status
#   bash config/scripts/pull-google-transcripts.sh --help
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
STATE_FILE="$VAULT_ROOT/config/state/pull-google.json"
LOG_FILE="$VAULT_ROOT/system/cron-pull-google-transcripts.log"
SOURCE_FORMAT="google-meet-transcript"

# ── Defaults ─────────────────────────────────────────────────────────────────
DAYS=1
BACKFILL=0
DRY_RUN=0
FORCE_FILE_ID=""
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

# Convert ISO UTC timestamp to operator-local YYYY-MM-DD
iso_utc_to_local_date() {
  local utc="$1"
  utc="${utc%%.*}"
  utc="${utc%Z}"
  TZ=UTC date -j -f "%Y-%m-%dT%H:%M:%S" "$utc" "+%s" 2>/dev/null \
    | xargs -I {} date -r {} "+%Y-%m-%d" 2>/dev/null
}

# Meet transcript filename pattern: "<Title> - YYYY/MM/DD HH:MM TZ - Transcript"
# Returns: title|date-iso-ymd  (pipe-separated; date is YYYY-MM-DD)
parse_meet_filename() {
  local fname="$1"
  # Strip trailing " - Transcript"
  local stripped="${fname% - Transcript}"
  # Match " - YYYY/MM/DD HH:MM TZ" at end
  if [[ "$stripped" =~ (.*)\ -\ ([0-9]{4})/([0-9]{1,2})/([0-9]{1,2})\ [0-9]{1,2}:[0-9]{2}\ [A-Z]+$ ]]; then
    local title="${BASH_REMATCH[1]}"
    local y="${BASH_REMATCH[2]}"
    local m="${BASH_REMATCH[3]}"
    local d="${BASH_REMATCH[4]}"
    # Force base-10: bash printf reads leading-zero values (08, 09) as octal and errors.
    printf '%s|%04d-%02d-%02d' "$title" "$((10#$y))" "$((10#$m))" "$((10#$d))"
  else
    # Fallback: no date in filename, use whole stripped as title, today as date
    printf '%s|%s' "$stripped" "$(date "+%Y-%m-%d")"
  fi
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
    --file-id)  FORCE_FILE_ID="$2"; FORCE=1; shift 2 ;;
    --force)    FORCE=1; shift ;;
    --status)   SHOW_STATUS=1; shift ;;
    --help|-h)
      sed -n '2,29p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown flag: $1" >&2
      echo "Try: $0 --help" >&2
      exit 2
      ;;
  esac
done

# ── --status mode ───────────────────────────────────────────────────────────
if [[ $SHOW_STATUS -eq 1 ]]; then
  echo "Google Meet transcripts pull status:"
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
if [[ -n "$FORCE_FILE_ID" && $FORCE -eq 0 ]]; then
  echo "Error: --file-id requires --force" >&2
  exit 2
fi

if [[ "$DAYS" -gt 7 && $BACKFILL -eq 0 && -z "$FORCE_FILE_ID" ]]; then
  echo "Error: --days $DAYS > 7 requires --backfill" >&2
  exit 2
fi

# Auto-extend lookback if last success was older than --days
last_success_at="$(read_state_field "last_success_at" "")"
if [[ -n "$last_success_at" && -z "$FORCE_FILE_ID" && $BACKFILL -eq 0 ]]; then
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

# ── gws state gate ──────────────────────────────────────────────────────────
# gws reads OAuth state from ~/Library/Application Support/gws — a normal
# directory on disk. If the state files are missing, gws was never set up on
# this machine (or its state was wiped): that's a configuration error, not a
# transient condition — surface it instead of skipping silently.
GWS_STATE_DIR="$HOME/Library/Application Support/gws"
gws_state_present() {
  local f
  for f in "$GWS_STATE_DIR"/credentials.*.enc; do
    [[ -e "$f" ]] || return 1   # unmatched glob stays literal → no creds present
    break
  done
  [[ -s "$GWS_STATE_DIR/client_secret.json" ]]
}
if ! gws_state_present; then
  log "ERROR  gws auth state missing at $GWS_STATE_DIR — run config/scripts/setup-gws.sh"
  exit 2
fi

# Smoke-check that gws auth is alive
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

log "INFO   starting Google Meet pull (days=$DAYS dry_run=$DRY_RUN force_file=${FORCE_FILE_ID:-none} cutoff=$CUTOFF_ISO)"

# ── Write intake file for one Doc ───────────────────────────────────────────
# Args: <file_id> <name> <created_time>
write_intake_for_doc() {
  local file_id="$1"
  local fname="$2"
  local created_at="$3"

  # Parse filename → title, date
  local parsed title local_date
  parsed="$(parse_meet_filename "$fname")"
  title="${parsed%|*}"
  local_date="${parsed##*|}"

  local slug filename target_path
  slug="$(slug_from_title "$title")"
  [[ -z "$slug" ]] && slug="$(printf 'untitled-%s' "${file_id:0:8}" | tr 'A-Z' 'a-z')"
  filename="${local_date}-${slug}.md"
  target_path="$INTAKE_DIR/$filename"

  # Collision handling
  if [[ -e "$target_path" ]]; then
    if grep -q "^google-drive-file-id: $file_id[[:space:]]*\$" "$target_path" 2>/dev/null; then
      if [[ $FORCE -eq 1 && "$FORCE_FILE_ID" == "$file_id" ]]; then
        : # fall through, overwrite
      else
        log "SKIP   $file_id already-pulled (in intake) → $filename"
        return 2
      fi
    else
      local short_suffix="${file_id:0:6}"
      filename="${local_date}-${slug}-${short_suffix}.md"
      target_path="$INTAKE_DIR/$filename"
      log "INFO   filename collision avoided via suffix → $filename"
    fi
  fi

  # Idempotency vs archive
  if [[ $FORCE -eq 0 || "$FORCE_FILE_ID" != "$file_id" ]]; then
    if grep -rlq "^google-drive-file-id: $file_id[[:space:]]*\$" "$TRANSCRIPTS_DIR" 2>/dev/null; then
      log "SKIP   $file_id already-processed (in transcripts/) → $filename"
      return 2
    fi
  fi

  if [[ $DRY_RUN -eq 1 ]]; then
    log "DRY    $file_id WOULD pull → $filename (\"$title\" $local_date)"
    return 3
  fi

  # Export the doc as text to a temp file
  local body_tmp; body_tmp="$(mktemp)"
  if ! gws drive files export \
        --params "$(jq -n --arg id "$file_id" '{fileId: $id, mimeType: "text/plain"}')" \
        --output "$body_tmp" >/dev/null 2>&1; then
    log "ERROR  $file_id export failed"
    rm -f "$body_tmp"
    return 4
  fi

  # Strip BOM if present
  if head -c 3 "$body_tmp" | od -An -c | grep -q '357 273 277'; then
    tail -c +4 "$body_tmp" > "$body_tmp.unbomb"
    mv "$body_tmp.unbomb" "$body_tmp"
  fi

  # Normalize CRLF → LF. Drive text/plain exports use CRLF; leaving it in
  # produces mixed-ending files that editors later normalize to all-CRLF,
  # which breaks every $-anchored frontmatter grep (dedupe, scans).
  tr -d '\r' < "$body_tmp" > "$body_tmp.lf"
  mv "$body_tmp.lf" "$body_tmp"

  # Parse attendees: lines between "Attendees" and "Transcript" headers
  local attendees_yaml=""
  if grep -qE '^Attendees[[:space:]]*$' "$body_tmp"; then
    attendees_yaml="$(awk '/^Attendees[[:space:]]*$/{f=1; next} /^Transcript[[:space:]]*$/{f=0; exit} f && NF{ print }' "$body_tmp" \
      | tr ',' '\n' \
      | awk 'NF{gsub(/^[[:space:]]+|[[:space:]]+$/,""); print "  - \"" $0 "\""}')"
  fi
  [[ -z "$attendees_yaml" ]] && attendees_yaml='  - "(none captured in doc header)"'

  # Extract body — everything after the "Transcript" line
  local transcript_body
  transcript_body="$(awk 'f{print} /^Transcript[[:space:]]*$/{f=1}' "$body_tmp")"

  # Drive web URL
  local drive_url="https://docs.google.com/document/d/$file_id"

  local pulled_at
  pulled_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  local tmp="$target_path.tmp.$$"
  {
    printf -- '---\n'
    printf -- 'type: source\n'
    printf -- 'source-kind: transcript\n'
    printf -- 'date: %s\n' "$local_date"
    printf -- 'processed: false\n'
    printf -- 'processed-into: []\n'
    printf -- 'title: %s\n' "$(printf '%s' "$title" | jq -Rs '.')"
    printf -- 'google-drive-file-id: %s\n' "$file_id"
    printf -- 'google-drive-url: %s\n' "$drive_url"
    printf -- 'google-created-at: %s\n' "$created_at"
    printf -- 'attendees-from-source:\n'
    printf -- '%s\n' "$attendees_yaml"
    printf -- 'source-format: %s\n' "$SOURCE_FORMAT"
    printf -- 'pulled-at: %s\n' "$pulled_at"
    printf -- '---\n\n'
    printf -- '# %s — %s (raw transcript)\n\n' "$title" "$local_date"
    printf -- 'Verbatim Google Meet transcript. Speakers are name-resolved by Google (e.g., "Martin Holland: …") so the processing pass can map directly to `atlas/people/` per [[../../config/objects/meeting]] step 3 without diarization-label resolution. The `attendees-from-source` field above is the list embedded by Google in the doc header; cross-reference against speaker turns during processing.\n\n'
    printf -- '## Transcript\n\n'
    printf -- '%s\n' "$transcript_body"
  } > "$tmp"

  mv "$tmp" "$target_path"
  rm -f "$body_tmp"

  local size; size="$(wc -c < "$target_path" | tr -d ' ')"
  log "PULL   $file_id → $filename (${size}b) \"$title\""
  return 0
}

# ── Forced single-file path ─────────────────────────────────────────────────
if [[ -n "$FORCE_FILE_ID" ]]; then
  meta="$(gws drive files get --params \
    "$(jq -n --arg id "$FORCE_FILE_ID" \
       '{fileId: $id, fields: "id,name,createdTime,mimeType"}')" \
    --format json 2>/dev/null)"
  if [[ -z "$meta" ]]; then
    log "ERROR  $FORCE_FILE_ID metadata fetch failed"
    exit 2
  fi
  fname="$(printf '%s' "$meta" | jq -r '.name')"
  created="$(printf '%s' "$meta" | jq -r '.createdTime')"
  write_intake_for_doc "$FORCE_FILE_ID" "$fname" "$created"
  rc=$?
  pulled=0
  [[ $rc -eq 0 || $rc -eq 3 ]] && pulled=1
  write_state "$(jq -n \
    --arg now "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
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

# ── List + iterate ──────────────────────────────────────────────────────────
QUERY="mimeType=\"application/vnd.google-apps.document\" and name contains \"- Transcript\" and \"me\" in owners and createdTime > \"$CUTOFF_ISO\""

PARAMS_JSON="$(jq -n --arg q "$QUERY" '{q: $q, fields: "files(id,name,createdTime)", orderBy: "createdTime desc", pageSize: 100}')"

list_json="$(mktemp)"
trap 'rm -f "$list_json"' EXIT

if ! gws drive files list --params "$PARAMS_JSON" --format json > "$list_json" 2>/dev/null; then
  log "ERROR  gws drive files list failed"
  prev_fails="$(read_state_field "consecutive_failures" "0")"
  new_fails=$(( prev_fails + 1 ))
  write_state "$(jq -n \
    --arg now "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
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

total_found="$(jq '.files | length' "$list_json")"
log "INFO   found $total_found owned-by-me Meet transcripts since $CUTOFF_ISO"

pulled=0
skipped=0
failed=0

while IFS=$'\t' read -r file_id fname created_at; do
  [[ -z "$file_id" ]] && continue

  # Pre-fetch idempotency: skip without exporting if file_id is already on disk
  # in intake/ or transcripts/. Handles suffix-renamed collisions that the
  # in-function check below would miss.
  if [[ $FORCE -eq 0 ]] && grep -rlq "^google-drive-file-id: $file_id[[:space:]]*\$" "$INTAKE_DIR" "$TRANSCRIPTS_DIR" 2>/dev/null; then
    log "SKIP   $file_id already-pulled (pre-fetch)"
    skipped=$((skipped + 1))
    continue
  fi

  write_intake_for_doc "$file_id" "$fname" "$created_at"
  case $? in
    0) pulled=$((pulled + 1)) ;;
    2) skipped=$((skipped + 1)) ;;
    3) pulled=$((pulled + 1)) ;;
    *) failed=$((failed + 1)) ;;
  esac
  sleep 0.2
done < <(jq -r '.files[] | "\(.id)\t\(.name)\t\(.createdTime)"' "$list_json")

# ── State + summary ─────────────────────────────────────────────────────────
now="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
if [[ $failed -eq 0 ]]; then
  if [[ $DRY_RUN -eq 1 ]]; then
    log "INFO   done (dry-run): pulled=$pulled skipped=$skipped failed=0 (state file NOT updated)"
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
    log "INFO   done: pulled=$pulled skipped=$skipped failed=0"
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
  log "WARN   partial: pulled=$pulled skipped=$skipped failed=$failed consec_fails=$new_fails"
  exit 1
fi
