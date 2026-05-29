#!/usr/bin/env bash
# check-for-updates.sh — checks GitHub for a newer WorkDesk OS release.
#
# Called from the SessionStart hook (session-entry-scan.sh) and from the
# /update skill's check phase. Caches the result so we don't hit GitHub more
# than once per 24 hours. Silent on network failure — never breaks a session.
#
# Subcommands:
#   check    Refresh cache if stale (>24h), output state as JSON to stdout.
#   notice   Output a one-line markdown notice if an update is available;
#            empty otherwise.
#   force    Bypass cache, always refresh.
#
# Cache file: config/state/update-check.json
#   {
#     "last-check":        "2026-04-30T12:00:00Z",
#     "latest-version":    "1.2.5",
#     "current-version":   "1.2.4",
#     "update-available":  true
#   }

set -euo pipefail
IFS=$'\n\t'

REPO="${WORKDESK_REPO:-BenaliHQ/workdesk-configuration}"
LATEST_URL="https://api.github.com/repos/$REPO/releases/latest"
TIMEOUT="${WORKDESK_UPDATE_TIMEOUT:-2}"

VAULT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
WD="$VAULT/config"
VERSION_FILE="$WD/VERSION"
CACHE="$WD/state/update-check.json"

current_version() {
  if [[ -f "$VERSION_FILE" ]]; then
    head -n 1 "$VERSION_FILE" | tr -d '[:space:]'
  else
    echo "unknown"
  fi
}

cache_age_hours() {
  [[ -f "$CACHE" ]] || { echo 999; return; }
  python3 - "$CACHE" <<'PYEOF' 2>/dev/null || echo 999
import json, sys
from datetime import datetime, timezone
try:
    d = json.load(open(sys.argv[1]))
    last = datetime.fromisoformat(d['last-check'].replace('Z','+00:00'))
    delta = (datetime.now(timezone.utc) - last).total_seconds()
    print(int(delta / 3600))
except Exception:
    print(999)
PYEOF
}

# Compare semver-ish strings. Returns 0 if a > b, 1 if a == b, 2 if a < b.
semver_cmp() {
  python3 - "$1" "$2" <<'PYEOF'
import sys, re
def parse(v):
    return tuple(int(p) for p in re.findall(r'\d+', v) or [0])
a, b = parse(sys.argv[1]), parse(sys.argv[2])
if a > b: sys.exit(0)
if a == b: sys.exit(1)
sys.exit(2)
PYEOF
}

refresh_cache() {
  local cur="$1"
  local body
  body=$(curl -fsSL --max-time "$TIMEOUT" "$LATEST_URL" 2>/dev/null) || return 1

  local tag
  tag=$(printf '%s' "$body" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('tag_name', '').lstrip('v'))
except Exception:
    pass
") || return 1
  [[ -n "$tag" ]] || return 1

  local update_available="false"
  if semver_cmp "$tag" "$cur"; then
    update_available="true"
  fi

  mkdir -p "$(dirname "$CACHE")"
  python3 - "$CACHE" "$tag" "$cur" "$update_available" <<'PYEOF'
import json, sys
from datetime import datetime, timezone
path, latest, current, available = sys.argv[1:5]
data = {
    'last-check':       datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
    'latest-version':   latest,
    'current-version':  current,
    'update-available': available == 'true',
}
json.dump(data, open(path, 'w'), indent=2)
PYEOF
  return 0
}

cmd_check() {
  local cur
  cur="$(current_version)"
  local age
  age=$(cache_age_hours)

  if (( age >= 24 )); then
    refresh_cache "$cur" || true
  fi

  if [[ -f "$CACHE" ]]; then
    cat "$CACHE"
  else
    cat <<EOF
{
  "last-check": null,
  "latest-version": null,
  "current-version": "$cur",
  "update-available": false
}
EOF
  fi
}

cmd_force() {
  local cur
  cur="$(current_version)"
  refresh_cache "$cur" || {
    cat <<EOF >&2
ERROR: Could not refresh update cache (network failure or GitHub unreachable).
EOF
    exit 1
  }
  cat "$CACHE"
}

cmd_notice() {
  # Pass the cache state to python as argv. Interpolating $state into
  # the heredoc would let a tampered cache file (or a hostile release
  # tag containing ''') inject Python code that runs on every
  # SessionStart. argv keeps it data-only — argv strings are never
  # evaluated as code.
  local state
  state=$(cmd_check)
  python3 - "$state" <<'PYEOF'
import json, sys
try:
    state = json.loads(sys.argv[1])
except (json.JSONDecodeError, ValueError, IndexError):
    sys.exit(0)
if not isinstance(state, dict):
    sys.exit(0)
if state.get('update-available'):
    cur = state.get('current-version', '?')
    new = state.get('latest-version', '?')
    print(f"**Update available:** WorkDesk OS v{new} — run `/update` to install. (You're on v{cur}.)")
PYEOF
}

case "${1:-}" in
  check)  shift; cmd_check  ;;
  force)  shift; cmd_force  ;;
  notice) shift; cmd_notice ;;
  ""|-h|--help)
    cat <<EOF
check-for-updates.sh — check GitHub for a newer WorkDesk OS release.

Usage:
  check-for-updates.sh check    Output cache state as JSON. Refreshes if stale.
  check-for-updates.sh force    Bypass cache and refresh now.
  check-for-updates.sh notice   Print a one-line notice if update available.

Cache: config/state/update-check.json (24h TTL).
Network: 2s timeout. Failures are silent — never breaks a session.
EOF
    ;;
  *) echo "Unknown subcommand: $1. Try --help." >&2; exit 1 ;;
esac
