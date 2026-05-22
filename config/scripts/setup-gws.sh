#!/usr/bin/env bash
# setup-gws.sh — interactive setup for the gws layer on top of the Infisical
# foundation. Idempotent. Re-running is safe.
#
# Prerequisite: bootstrap-infisical.sh has been run on this machine (foundation
# is in place: operator-profile populated, UA creds in Keychain, agent + ramdisk
# LaunchAgents loaded).
#
# Walks through:
#   1. Preflight    — verify foundation is in place + gws is installed (or
#                     install via brew)
#   2. Render       — substitute the 4 gws .tmpl.in files into concrete .tmpl
#                     files the Infisical Agent reads
#   3. Wire agent   — append gws template entries into config/infisical/agent.yaml
#                     (skipped on re-run if already present)
#   4. Reload agent — restart the Infisical Agent LaunchAgent so it picks up
#                     the new templates
#   5. Migrate gws  — symlink ~/Library/Application Support/gws to the ramdisk
#   6. Operator     — print the two manual steps the operator runs next
#                     (`gws auth login` + `gws-push-tokens-to-infisical.sh`)

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/operator-config.sh"

SCRIPT_DIR="${WORKDESK_ROOT}/config/scripts"
TEMPLATE_DIR="${WORKDESK_ROOT}/config/infisical/templates"
AGENT_CONFIG="${WORKDESK_ROOT}/config/infisical/agent.yaml"
SNIPPET_TMPL="${WORKDESK_ROOT}/config/infisical/agent-gws.yaml.snippet.tmpl"
LAUNCHAGENT_DIR="${HOME}/Library/LaunchAgents"
AGENT_PLIST_NAME="com.benali.workdesk.infisical-agent.plist"

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

# ─── Step 1: Preflight ──────────────────────────────────────────────────────
step "1. Preflight"

if [[ ! -f "${AGENT_CONFIG}" ]]; then
  err "Infisical foundation not set up — ${AGENT_CONFIG} missing."
  say "    Run config/scripts/bootstrap-infisical.sh first."
  exit 1
fi
ok "Infisical foundation in place"

if ! mount | grep -q "on /Volumes/wd-ramdisk "; then
  err "ramdisk not mounted at /Volumes/wd-ramdisk — foundation appears broken"
  say "    Re-run config/scripts/bootstrap-infisical.sh"
  exit 1
fi
ok "ramdisk mounted"

if [[ ! -s "/Volumes/wd-ramdisk/infisical/access-token" ]]; then
  warn "Infisical Agent has no access-token sink yet — may still be starting"
  say  "    If this persists, check ${WORKDESK_ROOT}/system/log/infisical-agent.log"
fi

if command -v gws >/dev/null 2>&1; then
  ok "gws CLI present ($(gws --version 2>&1 | head -1 || echo 'version unknown'))"
else
  warn "gws CLI not found — installing via Homebrew"
  if ! command -v brew >/dev/null 2>&1; then
    err "Homebrew not installed. Install from https://brew.sh first."
    exit 1
  fi
  brew tap iyear/tap 2>/dev/null || true
  brew install gws
  ok "gws installed: $(gws --version 2>&1 | head -1 || echo 'version unknown')"
fi

# ─── Step 2: Render templates ───────────────────────────────────────────────
step "2. Render gws agent templates"

render_in() {
  local src="$1"
  local dst="${src%.in}"
  if [[ ! -f "${src}" ]]; then err "template missing: ${src}" ; return 1 ; fi
  sed \
    -e "s|\[\[INFISICAL_PROJECT_ID\]\]|${INFISICAL_PERSONAL_PROJECT_ID}|g" \
    -e "s|\[\[OPERATOR_KEY_SUFFIX\]\]|${OPERATOR_KEY_SUFFIX}|g" \
    -e "s|\[\[OPERATOR_EMAIL_B64\]\]|${OPERATOR_EMAIL_B64}|g" \
    "${src}" > "${dst}"
  ok "rendered ${dst#${WORKDESK_ROOT}/}"
}

render_in "${TEMPLATE_DIR}/gws-client-secret-json.tmpl.in"
render_in "${TEMPLATE_DIR}/gws-encryption-key.tmpl.in"
render_in "${TEMPLATE_DIR}/gws-credentials-b64.tmpl.in"
render_in "${TEMPLATE_DIR}/gws-accounts-json.tmpl.in"

# ─── Step 3: Wire gws templates into agent.yaml ─────────────────────────────
step "3. Wire gws templates into agent.yaml"

GWS_MARKER="# gws templates — appended to config/infisical/agent.yaml by setup-gws.sh."

if grep -qF "${GWS_MARKER}" "${AGENT_CONFIG}"; then
  ok "agent.yaml already contains gws templates — skipping append"
else
  # Render the snippet with WORKDESK_ROOT + OPERATOR_EMAIL_B64 substitutions.
  RENDERED_SNIPPET=$(
    sed \
      -e "s|{{WORKDESK_ROOT}}|${WORKDESK_ROOT}|g" \
      -e "s|\[\[OPERATOR_EMAIL_B64\]\]|${OPERATOR_EMAIL_B64}|g" \
      "${SNIPPET_TMPL}"
  )

  # If agent.yaml ends with `templates: []`, replace that line with
  # `templates:` (open list) before appending. Otherwise append directly.
  if grep -q "^templates: \[\]$" "${AGENT_CONFIG}"; then
    # macOS sed needs -i ''.
    /usr/bin/sed -i '' 's|^templates: \[\]$|templates:|' "${AGENT_CONFIG}"
    ok "opened empty templates list in agent.yaml"
  fi

  printf '\n%s\n' "${RENDERED_SNIPPET}" >> "${AGENT_CONFIG}"
  ok "appended gws template block to agent.yaml"
fi

# ─── Step 4: Reload Infisical Agent ─────────────────────────────────────────
step "4. Reload Infisical Agent"

if [[ -f "${LAUNCHAGENT_DIR}/${AGENT_PLIST_NAME}" ]]; then
  launchctl unload "${LAUNCHAGENT_DIR}/${AGENT_PLIST_NAME}" 2>/dev/null || true
  launchctl load   "${LAUNCHAGENT_DIR}/${AGENT_PLIST_NAME}"
  ok "agent reloaded — give it a moment to re-render"
  sleep 4
else
  err "${LAUNCHAGENT_DIR}/${AGENT_PLIST_NAME} not found — foundation incomplete"
  exit 1
fi

# ─── Step 5: Migrate gws state to ramdisk ───────────────────────────────────
step "5. Migrate gws to RAM disk"

bash "${SCRIPT_DIR}/gws-migrate-to-ramdisk.sh"

# ─── Step 6: Operator next steps ────────────────────────────────────────────
step "6. Next steps (operator-driven)"

cat <<EOF

${bold}${grn}gws layer wired up.${rst} Two manual steps remain — both run by you:

  ${bold}A. Source the gws shell wrapper${rst}
     Append to ~/.zshrc (if not already there):
       source ${WORKDESK_ROOT}/config/shell/gws-env.sh

     Then open a fresh shell so the wrapper picks up.

  ${bold}B. Authenticate gws against your Google account${rst}
       gws auth login --account ${OPERATOR_EMAIL}

     This opens a browser for OAuth consent. The wrapper injects the OAuth
     app's client_id/client_secret from Infisical — you only consent.

  ${bold}C. Push the resulting auth state to Infisical${rst}
       bash ${WORKDESK_ROOT}/config/scripts/gws-push-tokens-to-infisical.sh

     This is critical — without it, your auth state lives only on the
     ramdisk and will vanish on next reboot. Re-run this script after
     every \`gws auth login\` (re-auths rotate the refresh token).

After C, verify with:
    gws auth status
    gws calendar events list --params '{"calendarId":"primary","maxResults":3}'

${dim}Then reboot once to confirm the agent re-renders your state from
Infisical without any browser prompt.${rst}
EOF
