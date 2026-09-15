#!/usr/bin/env bash
# post-tool-use-log.sh
#
# Categorizes a tool call against the 11 V1 semantic event classes and
# appends one line to system/events/{YYYY-MM}.md. Drops anything that
# doesn't match. The narrowing is intentional — see plan §"Event logging".
#
# Concurrency: full-section mkdir-based lock with trap-on-exit cleanup.
# Stale lock (mtime older than 5s) is treated as abandoned and reclaimed.
# Lock contention beyond retry budget drops the entry and warns to stderr
# (operations succeed; the log is observability).
#
# Latency budget: < 50ms p95.

set -euo pipefail
IFS=$'\n\t'

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT="${CLAUDE_PROJECT_DIR:-$(cd "$DIR/../.." && pwd)}"
# Nested projects inherit the containing vault. Preserve explicit standalone
# scratch roots used by the hook benchmark and isolated runtime probes.
VAULT_CANDIDATE="$VAULT"
while [[ "$VAULT_CANDIDATE" != / && ! -f "$VAULT_CANDIDATE/config/scripts/json-get.sh" ]]; do
  VAULT_CANDIDATE="$(dirname "$VAULT_CANDIDATE")"
done
if [[ -f "$VAULT_CANDIDATE/config/scripts/json-get.sh" ]]; then
  VAULT="$VAULT_CANDIDATE"
fi
EVENTS_DIR="$VAULT/system/events"
MONTH=$(date '+%Y-%m')
EVENTS_FILE="$EVENTS_DIR/$MONTH.md"
LOCK_DIR="$EVENTS_DIR/.events.lock.d"
STALE_LOCK_SECONDS=5

input="$(cat)"
[[ -z "$input" ]] && exit 0

# Parse the three flat fields we need with bash regex — no external
# interpreter, sub-millisecond cost. Falls back to empty on no match.
tool=""
path=""
cmd=""
re_tool='"tool_name"[[:space:]]*:[[:space:]]*"([^"]*)"'
re_path='"file_path"[[:space:]]*:[[:space:]]*"([^"]*)"'
re_npath='"notebook_path"[[:space:]]*:[[:space:]]*"([^"]*)"'
re_cmd='"command"[[:space:]]*:[[:space:]]*"((\\.|[^"\\])*)"'

[[ "$input" =~ $re_tool  ]] && tool="${BASH_REMATCH[1]}"
[[ "$input" =~ $re_path  ]] && path="${BASH_REMATCH[1]}"
[[ -z "$path" && "$input" =~ $re_npath ]] && path="${BASH_REMATCH[1]}"
[[ "$input" =~ $re_cmd   ]] && cmd="${BASH_REMATCH[1]}"

[[ -z "$tool" ]] && exit 0

# --- categorize ------------------------------------------------------------

event_class=""
target=""

case "$tool" in
  Write)
    case "$path" in
      */gtd/projects/*/brief.md|*/atlas/clients/*/projects/*/brief.md|*/atlas/businesses/*/projects/*/brief.md)        event_class="project-created";    target="$path" ;;
      */atlas/areas/*/brief.md)         event_class="object-created";     target="$path" ;;
      */atlas/clients/*/brief.md|\
      */atlas/businesses/*/brief.md|\
      */atlas/teams/*/brief.md|\
      */atlas/labs/*/brief.md|\
      */atlas/disciplines/*/brief.md|\
      */atlas/collaborations/*/brief.md|\
      */atlas/departments/*/brief.md)
                                          event_class="object-created";     target="$path" ;;
      */atlas/meetings/*.md|\
      */atlas/decisions/*.md|\
      */atlas/people/*.md|\
      */atlas/companies/*.md|\
      */atlas/content/*.md)
                                          event_class="object-created";     target="$path" ;;
      */gtd/actions/*.md)            event_class="action-promoted";    target="$path" ;;
      */intel/briefings/*.md|\
      */intel/vault-improvements/*.md|\
      */intel/observations/*.md|\
      */intel/research/*.md)
                                          event_class="signal-generated";   target="$path" ;;
      */config/objects/*.md|\
      */config/signals/*.md|\
      */config/sources/*.md|\
      */config/practices/*.md|\
      */config/rules/*.md|\
      */config/tools/*.md|\
      */config/templates/*.md|\
      */config/skills/*/SKILL.md)
                                          event_class="declaration-changed"; target="$path" ;;
    esac
    ;;
  Edit|MultiEdit)
    case "$path" in
      */config/objects/*.md|\
      */config/signals/*.md|\
      */config/sources/*.md|\
      */config/practices/*.md|\
      */config/rules/*.md|\
      */config/tools/*.md|\
      */config/templates/*.md|\
      */config/skills/*/SKILL.md)
                                          event_class="declaration-changed"; target="$path" ;;
      */config/onboarding-state.md)    event_class="onboarding-phase-completed"; target="$path" ;;
      */system/transcripts/*.md|\
      */system/intake/*.md)               event_class="source-processed";   target="$path" ;;
    esac
    ;;
  Bash)
    # action-completed: move from gtd/actions/{next,waiting}/ to gtd/archive/actions/
    if printf '%s' "$cmd" | grep -Eq '\bmv\b.*gtd/actions/(next|waiting)/.*gtd/archive/actions'; then
      event_class="action-completed"
      target=$(printf '%s' "$cmd" | grep -oE 'gtd/actions/(next|waiting)/[^ ]+' | head -1 || true)
    # object-archived: container folder → its _archive/ counterpart, or projects → archive/projects
    elif printf '%s' "$cmd" | grep -Eq '\bmv\b.*gtd/projects/.*gtd/archive/projects'; then
      event_class="object-archived"
      target=$(printf '%s' "$cmd" | grep -oE 'gtd/projects/[^ ]+' | head -1 || true)
    elif printf '%s' "$cmd" | grep -Eq '\bmv\b.*atlas/(clients|businesses|areas|teams|labs|disciplines|collaborations|departments)/.*_archive'; then
      event_class="object-archived"
      target=$(printf '%s' "$cmd" | grep -oE 'atlas/[^ ]+' | head -1 || true)
    fi
    ;;
esac

[[ -z "$event_class" ]] && exit 0

# --- C4: sanitize target before it touches the log -------------------------
#
# `target` originates in tool_input and is attacker-influenceable. The log
# format uses ` | ` as a field delimiter and is read by humans (often via
# `cat`/Obsidian preview). Strip control characters (newlines + escape
# sequences) and replace the field delimiter so a hostile filename cannot
# forge log entries or inject terminal escapes.
sanitize_field() {
  # tr -d strips control chars (0x00-0x1f and 0x7f).
  # sed replaces literal "|" with "/" so the field separator stays unique.
  printf '%s' "$1" \
    | LC_ALL=C tr -d '\000-\037\177' \
    | LC_ALL=C sed 's/|/_/g'
}
target=$(sanitize_field "$target")
event_class=$(sanitize_field "$event_class")

# --- C3: full-section lock with trap + PID-aware stale reclaim ------------
#
# The lock must wrap the entire read-init-write critical section: header
# creation, last-line dedup, and append. Without that, two concurrent
# first-writers can both initialise the file and one truncates the
# other; or two writers can both pass dedup and double-log.
#
# Stale-lock reclamation is gated on process liveness (kill -0). Just
# checking mtime is unsafe — a long-running holder still owns the lock
# even at age > 5s, and reclaiming on time alone lets a third process
# remove the live holder's lock when its trap fires.
LOCK_HELD=0
release_lock() {
  if (( LOCK_HELD == 1 )); then
    # Only remove if we're still the recorded owner; protects against
    # reclaim races where another process took ownership.
    if [[ -f "$LOCK_DIR/owner.pid" ]] \
       && [[ "$(cat "$LOCK_DIR/owner.pid" 2>/dev/null || true)" == "$$" ]]; then
      rm -f "$LOCK_DIR/owner.pid" 2>/dev/null || true
      rmdir  "$LOCK_DIR" 2>/dev/null || true
    fi
    LOCK_HELD=0
  fi
}
trap release_lock EXIT INT TERM HUP

mkdir -p "$EVENTS_DIR" 2>/dev/null || exit 0

stale_reclaim_done=0
acquired=0
for _ in 1 2 3 4 5 6; do
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    printf '%s' "$$" > "$LOCK_DIR/owner.pid" 2>/dev/null || true
    LOCK_HELD=1
    acquired=1
    break
  fi
  # Existing lock — only reclaim if the owner is dead (or unrecorded)
  # AND the lock is older than STALE_LOCK_SECONDS. One reclaim per run.
  if (( stale_reclaim_done == 0 )) && [[ -d "$LOCK_DIR" ]]; then
    now=$(date '+%s')
    mtime=$(/usr/bin/stat -f '%m' "$LOCK_DIR" 2>/dev/null || echo "$now")
    if (( now - mtime > STALE_LOCK_SECONDS )); then
      owner=$(cat "$LOCK_DIR/owner.pid" 2>/dev/null || true)
      if [[ -z "$owner" ]] || ! kill -0 "$owner" 2>/dev/null; then
        rm -f "$LOCK_DIR/owner.pid" 2>/dev/null || true
        rmdir  "$LOCK_DIR" 2>/dev/null || true
        stale_reclaim_done=1
        continue
      fi
    fi
  fi
  sleep 0.05
done

if (( acquired == 0 )); then
  echo "post-tool-use-log: lock contention; dropped $event_class $target" >&2
  exit 0
fi

# --- critical section: header + dedup + append ----------------------------

[[ -f "$EVENTS_FILE" ]] || printf "# Events — %s\n\n" "$MONTH" > "$EVENTS_FILE"

# 5-second de-dup: if the last line in the file matches (event-class, target),
# skip. Cheap, single tail call. Now safely under the lock.
last=$(tail -n 1 "$EVENTS_FILE" 2>/dev/null || true)
if printf '%s' "$last" | grep -qF " | $event_class | $target | "; then
  last_ts=$(printf '%s' "$last" | awk '{print $1, $2}')
  last_epoch=$(date -j -f '%Y-%m-%d %H:%M' "$last_ts" '+%s' 2>/dev/null || echo 0)
  now_epoch=$(date '+%s')
  if (( now_epoch - last_epoch < 5 )); then
    exit 0
  fi
fi

ts=$(date '+%Y-%m-%d %H:%M')
printf '%s | %s | %s | ok\n' "$ts" "$event_class" "$target" >> "$EVENTS_FILE"

# Lock released by trap on exit.
exit 0
