#!/usr/bin/env bash
# file-issue.sh — submit a GitHub issue to BenaliHQ/workdesk-configuration from a
# vault feedback session. Wrapped by /feedback SKILL.md.
#
# Subcommands:
#   check                       Verify gh installed + authenticated. Print
#                               status as JSON.
#   submit <title> <body-file>  Create the issue with given title and body
#                               (body read from file). Outputs the issue URL.
#   throttle-check              Reads config/state/feedback-throttle.json and
#                               prints {"count_24h": N, "limit": 20, "ok": bool}.
#   throttle-record             Append current ISO timestamp to throttle file
#                               (call after a successful submit).
#
# Env:
#   CLAUDE_PROJECT_DIR — vault root (defaults to detection from script path)
#   FEEDBACK_REPO      — override target repo (default: BenaliHQ/workdesk-configuration)
#   FEEDBACK_LIMIT     — daily issue cap (default: 20)

set -euo pipefail
IFS=$'\n\t'

REPO="${FEEDBACK_REPO:-BenaliHQ/workdesk-configuration}"
LIMIT="${FEEDBACK_LIMIT:-20}"

VAULT="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
THROTTLE="$VAULT/config/state/feedback-throttle.json"

log()  { printf '%s\n' "$*" >&2; }
fail() { log "ERROR: $*"; exit 1; }

cmd_check() {
  local gh_path gh_authed
  if command -v gh >/dev/null 2>&1; then
    gh_path="$(command -v gh)"
  else
    gh_path=""
  fi

  if [[ -n "$gh_path" ]] && gh auth status >/dev/null 2>&1; then
    gh_authed="True"
  else
    gh_authed="False"
  fi

  python3 -c "
import json
print(json.dumps({
  'gh_installed': bool('$gh_path'),
  'gh_path': '$gh_path',
  'gh_authenticated': $gh_authed,
}, indent=2))
"
}

cmd_throttle_check() {
  python3 - "$THROTTLE" "$LIMIT" <<'PYEOF'
import json, os, sys
from datetime import datetime, timedelta, timezone
path, limit = sys.argv[1], int(sys.argv[2])
now = datetime.now(timezone.utc)
cutoff = now - timedelta(hours=24)
subs = []
if os.path.isfile(path):
    try:
        data = json.load(open(path))
        subs = data.get('submissions', [])
    except (json.JSONDecodeError, KeyError):
        subs = []
recent = [s for s in subs if datetime.fromisoformat(s.replace('Z','+00:00')) >= cutoff]
print(json.dumps({
  'count_24h': len(recent),
  'limit': limit,
  'ok': len(recent) < limit,
}, indent=2))
PYEOF
}

cmd_throttle_record() {
  mkdir -p "$(dirname "$THROTTLE")"
  python3 - "$THROTTLE" <<'PYEOF'
import json, os, sys
from datetime import datetime, timezone
path = sys.argv[1]
now = datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
data = {'submissions': []}
if os.path.isfile(path):
    try:
        data = json.load(open(path))
    except json.JSONDecodeError:
        pass
data.setdefault('submissions', []).append(now)
# Trim to last 7 days for hygiene; throttle window is 24h.
from datetime import timedelta
cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat().replace('+00:00','Z')
data['submissions'] = [s for s in data['submissions'] if s >= cutoff]
json.dump(data, open(path, 'w'), indent=2)
print(now)
PYEOF
}

cmd_submit() {
  local title="${1:-}" body_file="${2:-}" type="${3:-enhancement}"
  [[ -n "$title"     ]] || fail "submit: title required as first arg"
  [[ -f "$body_file" ]] || fail "submit: body file not found at $body_file"

  command -v gh >/dev/null 2>&1 || fail "gh CLI not installed. Run: brew install gh"
  gh auth status >/dev/null 2>&1 || fail "gh not authenticated. Run: gh auth login"

  case "$type" in
    bug|enhancement|question) ;;
    *) fail "submit: type must be bug, enhancement, or question (got: $type)" ;;
  esac

  local url
  url=$(gh issue create \
    --repo "$REPO" \
    --title "$title" \
    --body-file "$body_file" \
    --label "from-vault" \
    --label "$type" 2>&1) || fail "gh issue create failed: $url"

  printf '%s\n' "$url"
}

case "${1:-}" in
  check)            shift; cmd_check ;;
  submit)           shift; cmd_submit "$@" ;;
  throttle-check)   shift; cmd_throttle_check ;;
  throttle-record)  shift; cmd_throttle_record ;;
  ""|-h|--help)
    cat <<EOF
file-issue.sh — submit feedback to GitHub from a vault session.

Usage:
  file-issue.sh check
      Verify gh CLI is installed and authenticated. Outputs JSON.

  file-issue.sh throttle-check
      Check whether the operator has filed fewer than \$FEEDBACK_LIMIT issues
      in the last 24h. Outputs JSON.

  file-issue.sh throttle-record
      Append the current timestamp to the throttle log. Call after a
      successful submit.

  file-issue.sh submit <title> <body-file> [bug|enhancement|question]
      Create the issue. Defaults to label \`enhancement\`. Always adds
      \`from-vault\` label. Outputs the issue URL on success.

Env: CLAUDE_PROJECT_DIR, FEEDBACK_REPO (default BenaliHQ/workdesk-configuration),
     FEEDBACK_LIMIT (default 20).
EOF
    ;;
  *) fail "Unknown subcommand: $1. Try --help." ;;
esac
