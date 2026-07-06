#!/usr/bin/env bash
# bootstrap-infisical.sh — interactive first-time setup for the Infisical
# secrets-management layer on this machine.
#
# Idempotent. Re-running is safe — each phase checks state and skips work that's
# already done.
#
# Auth model: your own Infisical account via `infisical login` (browser flow).
# No machine identities, no agents, no daemons. The CLI stores a user session
# locally; when it expires (every few weeks), re-run `infisical login` — any
# failing fetch or push will tell you.
#
# Walks through:
#   1. Preflight — verify required binaries exist
#   2. Profile   — fill in operator-profile.md frontmatter (email, project id,
#                  key suffix) if missing
#   3. Login     — establish an `infisical login` user session if none works
#   4. Verify    — confirm the personal project is reachable

set -euo pipefail

# Lenient so step 2 can populate the missing fields before they're enforced.
OPERATOR_CONFIG_LENIENT=1
source "$(dirname "${BASH_SOURCE[0]}")/lib/operator-config.sh"

PROFILE="${WORKDESK_ROOT}/config/operator-profile.md"
SCRIPT_DIR="${WORKDESK_ROOT}/config/scripts"

# Color helpers (skip if not a TTY).
if [[ -t 1 ]]; then
  bold=$(tput bold) ; dim=$(tput dim) ; red=$(tput setaf 1) ; grn=$(tput setaf 2)
  ylw=$(tput setaf 3) ; cyn=$(tput setaf 6) ; rst=$(tput sgr0)
else
  bold='' ; dim='' ; red='' ; grn='' ; ylw='' ; cyn='' ; rst=''
fi

say()  { printf '%s\n' "$*"; }
step() { printf '\n%s\n' "${bold}${cyn}== $* ==${rst}"; }
ok()   { printf '  %s%s%s %s\n' "${grn}" "✓" "${rst}" "$*"; }
warn() { printf '  %s%s%s %s\n' "${ylw}" "!" "${rst}" "$*"; }
err()  { printf '  %s%s%s %s\n' "${red}" "✗" "${rst}" "$*" >&2; }

# Replace a single frontmatter field in operator-profile.md.
#   set_field <key> <value>
# Handles both `key: ""` (empty default) and `key: "existing"` forms.
set_field() {
  local key="$1" value="$2" tmp
  tmp="$(mktemp)"
  awk -v key="${key}" -v val="${value}" '
    BEGIN { in_fm = 0; count = 0; updated = 0 }
    /^---[[:space:]]*$/ {
      count++
      print
      if (count == 1) in_fm = 1
      else if (count == 2) in_fm = 0
      next
    }
    in_fm && $0 ~ "^" key ":" {
      printf "%s: \"%s\"\n", key, val
      updated = 1
      next
    }
    { print }
    END {
      if (!updated && in_fm) {
        # Frontmatter never closed — bail rather than corrupt the file.
        exit 2
      }
    }
  ' "${PROFILE}" > "${tmp}"
  mv "${tmp}" "${PROFILE}"
}

# ─── Step 1: Preflight ──────────────────────────────────────────────────────
step "1. Preflight"

case "$(uname -s)" in
  Darwin) ok "macOS detected" ;;
  *)      err "This bootstrap supports macOS only (uname=$(uname -s))." ; exit 1 ;;
esac

require_bin() {
  if command -v "$1" >/dev/null 2>&1; then
    ok "$1 present"
  else
    err "$1 not found — $2"
    return 1
  fi
}
require_bin base64 "macOS built-in; if missing your system is broken" || exit 1
require_bin awk    "macOS built-in; if missing your system is broken" || exit 1

if command -v /opt/homebrew/bin/infisical >/dev/null 2>&1; then
  ok "infisical CLI present ($(/opt/homebrew/bin/infisical --version 2>&1 | head -1))"
else
  err "infisical CLI not found at /opt/homebrew/bin/infisical"
  say "    Install with: npm install -g @infisical/cli"
  exit 1
fi

# ─── Step 2: Profile fields ─────────────────────────────────────────────────
step "2. Operator profile frontmatter"

# Re-read profile to pick up any prior edits.
OPERATOR_CONFIG_LENIENT=1 source "${SCRIPT_DIR}/lib/operator-config.sh"

if [[ -z "${OPERATOR_EMAIL}" ]]; then
  read -rp "  Operator email (used as tool-account label): " new_email
  if [[ -z "${new_email}" ]]; then err "email is required" ; exit 1 ; fi
  set_field email "${new_email}"
  ok "wrote email to operator-profile.md"
else
  ok "email already set: ${OPERATOR_EMAIL}"
fi

if [[ -z "${INFISICAL_PERSONAL_PROJECT_ID}" ]]; then
  say "  Find this at https://app.infisical.com → your personal project → Settings → General → Project ID"
  read -rp "  Infisical personal project ID (UUID): " new_pid
  if [[ -z "${new_pid}" ]]; then err "project ID is required" ; exit 1 ; fi
  set_field infisical-project-id "${new_pid}"
  ok "wrote infisical-project-id to operator-profile.md"
else
  ok "infisical-project-id already set: ${INFISICAL_PERSONAL_PROJECT_ID}"
fi

# Re-read with strict enforcement now that fields should be populated.
unset OPERATOR_CONFIG_LENIENT
source "${SCRIPT_DIR}/lib/operator-config.sh"

if [[ -z "${OPERATOR_KEY_SUFFIX}" ]]; then
  err "OPERATOR_KEY_SUFFIX is empty — should have been derived from email"
  exit 1
fi
ok "key suffix: ${OPERATOR_KEY_SUFFIX}"
ok "email b64:  ${OPERATOR_EMAIL_B64}"

# ─── Step 3: User login ─────────────────────────────────────────────────────
step "3. Infisical user session"

# Probe with a value-safe listing. </dev/null keeps the CLI from dropping
# into its interactive wizard when the session is absent or expired.
session_ok() {
  local n
  n=$(bash "${SCRIPT_DIR}/infisical-names.sh" </dev/null 2>/dev/null | wc -l | tr -d ' ') || return 1
  [[ "${n}" -gt 0 ]]
}

if session_ok; then
  ok "existing user session works"
else
  say "  No working session — opening the browser login flow."
  say "  (Sessions expire every few weeks; re-run \`infisical login\` when fetches start failing.)"
  /opt/homebrew/bin/infisical login
  if session_ok; then
    ok "logged in and project reachable"
  else
    err "login completed but the personal project is not readable"
    say "    Confirm the project ID above and that your account has access to it."
    exit 1
  fi
fi

# ─── Step 4: Verify ─────────────────────────────────────────────────────────
step "4. Verify"

names_count=$(bash "${SCRIPT_DIR}/infisical-names.sh" </dev/null 2>/dev/null | wc -l | tr -d ' ')
if [[ "${names_count}" -gt 0 ]]; then
  ok "infisical project reachable — ${names_count} secret(s) listed"
else
  warn "infisical-names returned 0 secrets — project is reachable but empty"
fi

cat <<EOF

${bold}${grn}Bootstrap complete.${rst}

  Operator:   ${OPERATOR_EMAIL}
  Key suffix: ${OPERATOR_KEY_SUFFIX}
  Project ID: ${INFISICAL_PERSONAL_PROJECT_ID}
  Auth:       infisical login user session (re-run \`infisical login\` when it expires)

${dim}Next steps:${rst}
  - To set up the Google Workspace CLI (gws) on this machine:
      bash ${WORKDESK_ROOT}/config/scripts/setup-gws.sh
  - To list secrets safely (without leaking values into a Claude session):
      bash ${WORKDESK_ROOT}/config/scripts/infisical-names.sh
  - To fetch a single secret value:
      infisical secrets get <KEY> --projectId=${INFISICAL_PERSONAL_PROJECT_ID} --env=prod --plain
EOF
