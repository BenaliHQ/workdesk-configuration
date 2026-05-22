#!/usr/bin/env bash
# bootstrap-infisical.sh — interactive first-time setup for the Infisical
# secrets-management layer on this machine.
#
# Idempotent. Re-running is safe — each phase checks state and skips work that's
# already done.
#
# Walks through:
#   1. Preflight  — verify required binaries exist
#   2. Profile    — fill in operator-profile.md frontmatter (email, project id,
#                   key suffix) if missing
#   3. Keychain   — stash Universal Auth client-id + client-secret if missing
#   4. Ramdisk    — mount /Volumes/wd-ramdisk if not mounted
#   5. Configs    — render agent.yaml + LaunchAgent plists from templates
#   6. LaunchAgents — install + load the two .plists in ~/Library/LaunchAgents
#   7. Verify     — confirm agent is running and can read from Infisical

set -euo pipefail

# Lenient so step 2 can populate the missing fields before they're enforced.
OPERATOR_CONFIG_LENIENT=1
source "$(dirname "${BASH_SOURCE[0]}")/lib/operator-config.sh"

PROFILE="${WORKDESK_ROOT}/config/operator-profile.md"
LAUNCHAGENT_DIR="${HOME}/Library/LaunchAgents"
RAMDISK_PLIST_NAME="com.benali.workdesk.ramdisk.plist"
AGENT_PLIST_NAME="com.benali.workdesk.infisical-agent.plist"
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
require_bin hdiutil   "macOS built-in; if missing your system is broken" || exit 1
require_bin diskutil  "macOS built-in; if missing your system is broken" || exit 1
require_bin security  "macOS built-in; if missing your system is broken" || exit 1
require_bin launchctl "macOS built-in; if missing your system is broken" || exit 1
require_bin base64    "macOS built-in; if missing your system is broken" || exit 1
require_bin awk       "macOS built-in; if missing your system is broken" || exit 1

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
  read -rp "  Operator email (used as Keychain account + tool-account label): " new_email
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

# ─── Step 3: Keychain ───────────────────────────────────────────────────────
step "3. Universal Auth creds in Keychain"

have_cid=$(security  find-generic-password -a "${OPERATOR_EMAIL}" -s "infisical-ua-client-id"     -w 2>/dev/null || true)
have_csec=$(security find-generic-password -a "${OPERATOR_EMAIL}" -s "infisical-ua-client-secret" -w 2>/dev/null || true)

if [[ -n "${have_cid}" && -n "${have_csec}" ]]; then
  ok "UA creds already stored for ${OPERATOR_EMAIL}"
else
  warn "UA creds not found in Keychain for ${OPERATOR_EMAIL}"
  say  ""
  say  "  ${bold}You need a Universal Auth machine identity in your personal Infisical project.${rst}"
  say  "  1. https://app.infisical.com → personal project → Access Control → Machine Identities → Create"
  say  "  2. Authentication method: Universal Auth"
  say  "  3. Role: Viewer (read-only — critical; never grant write)"
  say  "  4. After creation, Add Auth Method → Universal Auth → Create Client Secret"
  say  "     The Client Secret is shown ${bold}ONCE${rst} — copy it now."
  say  ""
  bash "${SCRIPT_DIR}/infisical-keychain-store.sh"
  ok "UA creds stored"
fi
unset have_cid have_csec

# ─── Step 4: Ramdisk ────────────────────────────────────────────────────────
step "4. RAM disk"

if mount | grep -q "on /Volumes/wd-ramdisk "; then
  ok "/Volumes/wd-ramdisk already mounted"
else
  bash "${SCRIPT_DIR}/ramdisk-mount.sh"
  ok "/Volumes/wd-ramdisk mounted"
fi

# ─── Step 5: Render templates ───────────────────────────────────────────────
step "5. Generate concrete configs from templates"

render_template() {
  local src="$1" dst="$2"
  if [[ ! -f "${src}" ]]; then err "template missing: ${src}" ; return 1 ; fi
  mkdir -p "$(dirname "${dst}")"
  sed "s|{{WORKDESK_ROOT}}|${WORKDESK_ROOT}|g" "${src}" > "${dst}"
  ok "rendered ${dst#${WORKDESK_ROOT}/}"
}

render_template \
  "${WORKDESK_ROOT}/config/infisical/agent.yaml.tmpl" \
  "${WORKDESK_ROOT}/config/infisical/agent.yaml"

render_template \
  "${WORKDESK_ROOT}/config/launchagents/${RAMDISK_PLIST_NAME}.tmpl" \
  "${LAUNCHAGENT_DIR}/${RAMDISK_PLIST_NAME}"

render_template \
  "${WORKDESK_ROOT}/config/launchagents/${AGENT_PLIST_NAME}.tmpl" \
  "${LAUNCHAGENT_DIR}/${AGENT_PLIST_NAME}"

# Ensure log dir exists so launchd can write StdoutPath/StderrPath.
mkdir -p "${WORKDESK_ROOT}/system/log"

# ─── Step 6: Load LaunchAgents ──────────────────────────────────────────────
step "6. Load LaunchAgents"

load_plist() {
  local plist="$1"
  if launchctl list | grep -q "$(basename "${plist}" .plist)"; then
    launchctl unload "${plist}" 2>/dev/null || true
    ok "reloading $(basename "${plist}")"
  else
    ok "loading $(basename "${plist}") for the first time"
  fi
  launchctl load "${plist}"
}

load_plist "${LAUNCHAGENT_DIR}/${RAMDISK_PLIST_NAME}"
load_plist "${LAUNCHAGENT_DIR}/${AGENT_PLIST_NAME}"

# ─── Step 7: Verify ─────────────────────────────────────────────────────────
step "7. Verify"

# Poll for agent registration AND access-token sink. On macOS Sequoia first-
# load, background-item approval can delay registration past a one-shot check;
# poll for up to 30s.
poll_for() {
  local label="$1" check_cmd="$2" timeout="${3:-30}"
  local i
  for i in $(seq 1 "$((timeout * 2))"); do
    if eval "${check_cmd}" >/dev/null 2>&1; then
      ok "${label} (after ${i}× 0.5s)"
      return 0
    fi
    sleep 0.5
  done
  err "${label} — still failing after ${timeout}s"
  return 1
}

poll_for "infisical-agent LaunchAgent registered" \
  "launchctl list | grep -q 'com.benali.workdesk.infisical-agent'" 30 || {
  say "    Check ~/Library/LaunchAgents/${AGENT_PLIST_NAME}"
  say "    Inspect ${WORKDESK_ROOT}/system/log/infisical-agent.log"
  exit 1
}

poll_for "agent authenticated (access-token sink populated)" \
  "[[ -s /Volumes/wd-ramdisk/infisical/access-token ]]" 30 || {
  say "    The agent registered but never wrote an access token."
  say "    Check ${WORKDESK_ROOT}/system/log/infisical-agent.log for auth errors."
  exit 1
}

# Authenticate the `infisical` shell CLI using the same UA identity the agent
# uses. Without this, any shell-level `infisical secrets` call falls through
# to interactive browser-login on a fresh machine — wrong auth path and noisy.
say ""
say "  Logging the shell CLI in via Universal Auth"
if infisical login --method=universal-auth --plain --silent \
     --client-id="$(security find-generic-password -a "${OPERATOR_EMAIL}" -s infisical-ua-client-id     -w 2>/dev/null)" \
     --client-secret="$(security find-generic-password -a "${OPERATOR_EMAIL}" -s infisical-ua-client-secret -w 2>/dev/null)" \
     >/dev/null 2>&1; then
  ok "shell CLI authenticated via UA identity"
else
  warn "shell CLI UA login failed — \`infisical-names.sh\` may fall back to browser login"
fi

# Smoke test: fetch the names listing — proves the UA identity can read.
if names_count=$(bash "${SCRIPT_DIR}/infisical-names.sh" 2>/dev/null | wc -l | tr -d ' '); then
  if [[ "${names_count}" -gt 0 ]]; then
    ok "infisical project reachable — ${names_count} secret(s) listed"
  else
    warn "infisical-names returned 0 secrets — project is reachable but empty, or the UA identity lacks read on this project"
  fi
else
  warn "infisical-names smoke check failed — confirm UA identity has Viewer role on this project"
fi

cat <<EOF

${bold}${grn}Bootstrap complete.${rst}

  Operator:         ${OPERATOR_EMAIL}
  Key suffix:       ${OPERATOR_KEY_SUFFIX}
  Project ID:       ${INFISICAL_PERSONAL_PROJECT_ID}
  Agent config:     ${WORKDESK_ROOT}/config/infisical/agent.yaml
  LaunchAgents:     ${LAUNCHAGENT_DIR}/${RAMDISK_PLIST_NAME}
                    ${LAUNCHAGENT_DIR}/${AGENT_PLIST_NAME}
  Agent log:        ${WORKDESK_ROOT}/system/log/infisical-agent.log

${dim}Next steps:${rst}
  - To set up the Google Workspace CLI (gws) on this machine:
      bash ${WORKDESK_ROOT}/config/scripts/setup-gws.sh
  - To list secrets safely (without leaking values into a Claude session):
      bash ${WORKDESK_ROOT}/config/scripts/infisical-names.sh
  - To fetch a single secret value:
      infisical secrets get <KEY> --projectId=${INFISICAL_PERSONAL_PROJECT_ID} --env=prod --plain
EOF
