#!/usr/bin/env bash
# pull-granola.sh — Daily ETL pull of Granola transcripts into system/intake/.
#
# Pure ETL. No AI tokens. Idempotent (skips notes already pulled, by
# granola-note-id across system/intake/ and system/transcripts/).
#
# Reads the Granola public API key from Infisical (PERSONAL_GRANOLA_API_KEY
# in the operator's personal Infisical project). For each note in the lookback window, fetches
# the verbatim transcript via /v1/notes/{id}?include=transcript and writes a
# markdown file conforming to the transcript source seed.
#
# Usage:
#   bash config/scripts/pull-granola.sh                         # default: --days 1
#   bash config/scripts/pull-granola.sh --days 7
#   bash config/scripts/pull-granola.sh --days 30 --backfill    # >7 days requires --backfill
#   bash config/scripts/pull-granola.sh --dry-run
#   bash config/scripts/pull-granola.sh --note-id not_xxx --force
#   bash config/scripts/pull-granola.sh --status
#   bash config/scripts/pull-granola.sh --help
#
# Exit codes:
#   0  success (may include zero new pulls)
#   1  partial — some notes failed to pull
#   2  hard failure (auth, bad args, API unreachable)

set -uo pipefail

# ── Constants ────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
INTAKE_DIR="$VAULT_ROOT/system/intake"
TRANSCRIPTS_DIR="$VAULT_ROOT/system/transcripts"
STATE_FILE="$VAULT_ROOT/config/state/pull-granola.json"
LOG_FILE="$VAULT_ROOT/system/cron-pull-granola.log"
PERSONAL_PROJ_ID="df755029-00a8-4374-b195-43eeb3268430"
INFISICAL_ENV="prod"
GRANOLA_API="https://public-api.granola.ai/v1"
SOURCE_FORMAT="granola-public-api"

# ── Defaults ─────────────────────────────────────────────────────────────────
DAYS=1
BACKFILL=0
DRY_RUN=0
FORCE_NOTE_ID=""
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

# Convert an ISO-8601 UTC timestamp ("2026-05-14T15:10:46.934Z") to operator-
# local-time YYYY-MM-DD. Uses BSD date on macOS.
iso_utc_to_local_date() {
  local utc="$1"
  # Strip fractional seconds + Z
  utc="${utc%%.*}"
  utc="${utc%Z}"
  TZ=UTC date -j -f "%Y-%m-%dT%H:%M:%S" "$utc" "+%s" 2>/dev/null \
    | xargs -I {} date -r {} "+%Y-%m-%d" 2>/dev/null
}

# Write state file atomically with the given json content
write_state() {
  local content="$1"
  mkdir -p "$(dirname "$STATE_FILE")"
  local tmp="$STATE_FILE.tmp.$$"
  printf '%s\n' "$content" > "$tmp"
  mv "$tmp" "$STATE_FILE"
}

# Read state-file field with default
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
    --days)      DAYS="$2"; shift 2 ;;
    --backfill)  BACKFILL=1; shift ;;
    --dry-run)   DRY_RUN=1; shift ;;
    --note-id)   FORCE_NOTE_ID="$2"; FORCE=1; shift 2 ;;
    --force)     FORCE=1; shift ;;
    --status)    SHOW_STATUS=1; shift ;;
    --help|-h)
      sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'
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
  echo "Granola pull status:"
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
      # Hours since last success
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
if [[ -n "$FORCE_NOTE_ID" && $FORCE -eq 0 ]]; then
  echo "Error: --note-id requires --force" >&2
  exit 2
fi

if [[ "$DAYS" -gt 7 && $BACKFILL -eq 0 && -z "$FORCE_NOTE_ID" ]]; then
  echo "Error: --days $DAYS > 7 requires --backfill (guard rail against accidental flood)" >&2
  exit 2
fi

# Extend lookback if last successful pull is older than --days
last_success_at="$(read_state_field "last_success_at" "")"
if [[ -n "$last_success_at" && -z "$FORCE_NOTE_ID" && $BACKFILL -eq 0 ]]; then
  last_epoch="$(TZ=UTC date -j -f "%Y-%m-%dT%H:%M:%SZ" "$last_success_at" "+%s" 2>/dev/null || echo 0)"
  now_epoch="$(date -u "+%s")"
  delta_days=$(( (now_epoch - last_epoch + 86399) / 86400 ))  # ceil
  if [[ $delta_days -gt $DAYS ]]; then
    log "INFO   last success was $delta_days days ago; extending lookback from $DAYS to $delta_days"
    DAYS=$delta_days
  fi
fi

mkdir -p "$INTAKE_DIR" "$(dirname "$STATE_FILE")"

# ── Resolve API key (minimum-privilege — fetch just this one) ───────────────
if ! command -v infisical >/dev/null 2>&1; then
  log "ERROR  infisical CLI not on PATH"
  exit 2
fi

# Auth: the operator's `infisical login` user session (or an INFISICAL_TOKEN
# already exported by the caller). </dev/null on the fetch below keeps the CLI
# from dropping into its interactive wizard in non-interactive contexts
# (cron, agents) — it fails fast instead, and the error path says to re-login.

GRANOLA_API_KEY="$(infisical secrets get PERSONAL_GRANOLA_API_KEY \
  --projectId="$PERSONAL_PROJ_ID" --env="$INFISICAL_ENV" --plain </dev/null 2>/dev/null)" || true

if [[ -z "$GRANOLA_API_KEY" || "${GRANOLA_API_KEY:0:4}" != "grn_" ]]; then
  log "ERROR  could not read PERSONAL_GRANOLA_API_KEY from Infisical (or wrong shape) — run \`infisical login\` (user sessions expire every few weeks)"
  # Update state with failure
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

# ── Cutoff computation ──────────────────────────────────────────────────────
# Notes with created_at >= CUTOFF are candidates.
CUTOFF_EPOCH=$(( $(date -u "+%s") - DAYS * 86400 ))
CUTOFF_ISO="$(date -u -r "$CUTOFF_EPOCH" "+%Y-%m-%dT%H:%M:%SZ")"

log "INFO   starting Granola pull (days=$DAYS dry_run=$DRY_RUN force_note_id=${FORCE_NOTE_ID:-none} cutoff=$CUTOFF_ISO)"

# ── Forced re-pull of a specific note ───────────────────────────────────────
fetch_one() {
  local note_id="$1"
  local body_file="$2"
  curl -sS -w '\n%{http_code}' \
    "$GRANOLA_API/notes/$note_id?include=transcript" \
    -H "Authorization: Bearer $GRANOLA_API_KEY" \
    -o "$body_file"
}

# Convert a single note's JSON into a markdown intake file at the target path
# (atomic write via temp + rename).
write_intake_for_note() {
  local note_json="$1"
  local note_id="$2"

  local title created_at uuid web_url utterance_count
  title="$(jq -r '.title' "$note_json")"
  created_at="$(jq -r '.created_at' "$note_json")"
  uuid="$(jq -r '.web_url' "$note_json" | sed -E 's|.*/d/||')"
  web_url="$(jq -r '.web_url' "$note_json")"
  utterance_count="$(jq '.transcript | length' "$note_json")"

  if [[ "$utterance_count" -eq 0 ]]; then
    log "SKIP   $note_id empty-transcript title=\"$title\""
    return 1
  fi

  local local_date slug filename target_path
  local_date="$(iso_utc_to_local_date "$created_at")"
  [[ -z "$local_date" ]] && local_date="$(date "+%Y-%m-%d")"
  slug="$(slug_from_title "$title")"
  [[ -z "$slug" ]] && slug="$(printf 'untitled-%s' "${note_id##not_}" | tr 'A-Z' 'a-z')"
  filename="${local_date}-${slug}.md"
  target_path="$INTAKE_DIR/$filename"

  # Collision: same filename but not from us (no matching granola-note-id)
  if [[ -e "$target_path" ]]; then
    if grep -q "^granola-note-id: $note_id[[:space:]]*\$" "$target_path" 2>/dev/null; then
      if [[ $FORCE -eq 1 && "$FORCE_NOTE_ID" == "$note_id" ]]; then
        : # fall through and overwrite
      else
        log "SKIP   $note_id already-pulled (in intake) → $filename"
        return 2
      fi
    else
      # Filename collision with a different note — disambiguate
      local short_suffix="${note_id##not_}"
      short_suffix="${short_suffix:0:6}"
      filename="${local_date}-${slug}-${short_suffix}.md"
      target_path="$INTAKE_DIR/$filename"
      log "INFO   filename collision avoided via suffix → $filename"
    fi
  fi

  # Idempotency check against transcripts/ archive
  if [[ $FORCE -eq 0 || "$FORCE_NOTE_ID" != "$note_id" ]]; then
    if grep -rlq "^granola-note-id: $note_id[[:space:]]*\$" "$TRANSCRIPTS_DIR" 2>/dev/null; then
      log "SKIP   $note_id already-processed (in transcripts/) → $filename"
      return 2
    fi
  fi

  if [[ $DRY_RUN -eq 1 ]]; then
    log "DRY    $note_id WOULD pull → $filename ($utterance_count utterances)"
    return 3
  fi

  # ── Write the file ────────────────────────────────────────────────────────
  local pulled_at attendees_yaml body
  pulled_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  attendees_yaml="$(jq -r '.attendees // [] | .[] | "  - \"\(.name // "Unknown") <\(.email // "no-email")>\""' "$note_json")"

  local tmp="$target_path.tmp.$$"
  {
    printf -- '---\n'
    printf -- 'type: source\n'
    printf -- 'source-kind: transcript\n'
    printf -- 'date: %s\n' "$local_date"
    printf -- 'processed: false\n'
    printf -- 'processed-into: []\n'
    printf -- 'title: %s\n' "$(printf '%s' "$title" | jq -Rs '.')"
    printf -- 'granola-note-id: %s\n' "$note_id"
    printf -- 'granola-uuid: %s\n' "$uuid"
    printf -- 'granola-url: %s\n' "$web_url"
    printf -- 'granola-created-at: %s\n' "$created_at"
    printf -- 'attendees-from-source:\n'
    printf -- '%s\n' "$attendees_yaml"
    printf -- 'source-format: %s\n' "$SOURCE_FORMAT"
    printf -- 'pulled-at: %s\n' "$pulled_at"
    printf -- '---\n\n'
    printf -- '# %s — %s (raw transcript)\n\n' "$title" "$local_date"
    printf -- 'Verbatim transcript from Granola public API. Speakers are diarization labels (A, B, C…), not resolved identities — operator/processing pass maps them to attendees. The `attendees-from-source` field above is calendar invitees from Granola; actual presence is determined during processing per [[../../config/objects/meeting]] step 2.\n\n'
    printf -- '## Transcript\n\n'
    jq -r '.transcript[] | "[\(.start_time[11:19])] \(.speaker.diarization_label // "Speaker ?"): \(.text)"' "$note_json"
  } > "$tmp"

  mv "$tmp" "$target_path"

  local size; size="$(wc -c < "$target_path" | tr -d ' ')"
  log "PULL   $note_id → $filename ($utterance_count utt, ${size}b) \"$title\""
  return 0
}

# ── Force-pull single note path ─────────────────────────────────────────────
if [[ -n "$FORCE_NOTE_ID" ]]; then
  body_file="$(mktemp)"
  trap 'rm -f "$body_file"' EXIT
  http=$(curl -sS -w '%{http_code}' \
    "$GRANOLA_API/notes/$FORCE_NOTE_ID?include=transcript" \
    -H "Authorization: Bearer $GRANOLA_API_KEY" \
    -o "$body_file")
  if [[ "$http" != "200" ]]; then
    log "ERROR  $FORCE_NOTE_ID http=$http (force fetch failed)"
    exit 2
  fi
  write_intake_for_note "$body_file" "$FORCE_NOTE_ID"
  rc=$?
  # 0 = pulled, 1 = empty, 2 = skipped (idempotent), 3 = dry-run
  if [[ $rc -eq 0 || $rc -eq 3 ]]; then
    pulled=1
  else
    pulled=0
  fi
  write_state "$(jq -n \
    --arg now "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" \
    --argjson pulled "$pulled" \
    --arg prev_success "$last_success_at" \
    '{
       last_success_at: $now,
       last_failure_at: null,
       consecutive_failures: 0,
       last_run_at: $now,
       last_run_pulled: $pulled
     }')"
  exit 0
fi

# ── Paginate /v1/notes and process ──────────────────────────────────────────
cursor=""
page=0
pulled=0
skipped=0
failed=0
seen_pre_cutoff=0
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

while :; do
  page=$((page + 1))
  list_url="$GRANOLA_API/notes?limit=100"
  [[ -n "$cursor" ]] && list_url="$list_url&cursor=$cursor"

  list_body="$tmp_dir/list-$page.json"
  http=$(curl -sS -w '%{http_code}' "$list_url" \
    -H "Authorization: Bearer $GRANOLA_API_KEY" \
    -o "$list_body")

  if [[ "$http" != "200" ]]; then
    log "ERROR  list page=$page http=$http"
    failed=$((failed + 1))
    break
  fi

  has_more="$(jq -r '.hasMore' "$list_body")"
  next_cursor="$(jq -r '.cursor // empty' "$list_body")"

  # API returns newest-first. Track per-page how many notes were below the
  # cutoff so we can early-exit when an entire page is past the lookback.
  page_total=0
  page_pre_cutoff=0
  while IFS=$'\t' read -r note_id note_created; do
    [[ -z "$note_id" ]] && continue
    page_total=$((page_total + 1))

    # Cutoff check
    note_epoch="$(TZ=UTC date -j -f "%Y-%m-%dT%H:%M:%S" "${note_created%%.*}" "+%s" 2>/dev/null || echo 0)"
    if [[ "$note_epoch" -lt "$CUTOFF_EPOCH" ]]; then
      page_pre_cutoff=$((page_pre_cutoff + 1))
      seen_pre_cutoff=$((seen_pre_cutoff + 1))
      continue
    fi

    # Pre-fetch idempotency (cheap): if already in intake or transcripts, skip
    # without hitting the per-note endpoint.
    if grep -rlq "^granola-note-id: $note_id[[:space:]]*\$" "$INTAKE_DIR" "$TRANSCRIPTS_DIR" 2>/dev/null; then
      skipped=$((skipped + 1))
      continue
    fi

    # Fetch transcript
    note_body="$tmp_dir/$note_id.json"
    note_http=$(curl -sS -w '%{http_code}' \
      "$GRANOLA_API/notes/$note_id?include=transcript" \
      -H "Authorization: Bearer $GRANOLA_API_KEY" \
      -o "$note_body")
    if [[ "$note_http" != "200" ]]; then
      log "ERROR  $note_id fetch http=$note_http"
      failed=$((failed + 1))
      continue
    fi

    write_intake_for_note "$note_body" "$note_id"
    case $? in
      0) pulled=$((pulled + 1)) ;;
      1) skipped=$((skipped + 1)) ;;  # empty transcript
      2) skipped=$((skipped + 1)) ;;  # already-pulled
      3) pulled=$((pulled + 1)) ;;    # dry-run "would pull"
      *) failed=$((failed + 1)) ;;
    esac

    # Polite rate limit
    sleep 0.2
  done < <(jq -r '.notes[] | "\(.id)\t\(.created_at)"' "$list_body")

  # Early-exit: if every note on this page was already past the cutoff (and
  # the page wasn't empty), the API's newest-first ordering means subsequent
  # pages are also past the cutoff — stop paginating.
  if [[ $page_total -gt 0 && $page_pre_cutoff -eq $page_total ]]; then
    break
  fi

  # If the API says no more pages, stop
  if [[ "$has_more" != "true" || -z "$next_cursor" ]]; then
    break
  fi
  cursor="$next_cursor"

  # Safety stop
  if [[ $page -gt 50 ]]; then
    log "WARN   safety-stop at page=50; further notes not pulled this run"
    break
  fi
done

# ── State + summary ─────────────────────────────────────────────────────────
now="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
if [[ $failed -eq 0 ]]; then
  if [[ $DRY_RUN -eq 1 ]]; then
    log "INFO   done (dry-run): pulled=$pulled skipped=$skipped failed=0 pages=$page (state file NOT updated)"
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
    log "INFO   done: pulled=$pulled skipped=$skipped failed=0 pages=$page"
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
  log "WARN   partial: pulled=$pulled skipped=$skipped failed=$failed pages=$page consec_fails=$new_fails"
  exit 1
fi
