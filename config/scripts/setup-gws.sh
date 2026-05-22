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

# gws install — Google Workspace CLI at https://github.com/googleworkspace/cli.
# Two install methods documented in the official README; we try brew first
# (cleaner upgrade path, no node runtime needed), then npm as a fallback.
# (Specifically AVOID `brew install gws` — that's an unrelated git-workspaces
# tool by streakycobra. The Google CLI's brew formula is `googleworkspace-cli`.)
if command -v gws >/dev/null 2>&1 && gws --help 2>&1 | grep -qi 'google workspace'; then
  ok "gws CLI present ($(gws --version 2>&1 | head -1 || echo 'version unknown'))"
elif command -v gws >/dev/null 2>&1; then
  err "A different tool named 'gws' is on PATH at $(command -v gws)."
  say "    The setup needs the Google Workspace CLI from github.com/googleworkspace/cli."
  say "    Remove or shadow the conflicting tool, then re-run."
  exit 1
else
  warn "gws CLI not found — installing the Google Workspace CLI"
  if command -v brew >/dev/null 2>&1; then
    say "    trying: brew install googleworkspace-cli"
    if brew install googleworkspace-cli; then
      ok "gws installed via Homebrew: $(gws --version 2>&1 | head -1 || echo 'version unknown')"
    else
      warn "brew install failed; falling back to npm"
      if command -v npm >/dev/null 2>&1; then
        npm install -g @googleworkspace/cli
        ok "gws installed via npm: $(gws --version 2>&1 | head -1 || echo 'version unknown')"
      else
        err "Neither brew formula nor npm worked. Install manually:"
        say "    https://github.com/googleworkspace/cli/releases"
        exit 1
      fi
    fi
  elif command -v npm >/dev/null 2>&1; then
    say "    Homebrew not present; using npm install -g @googleworkspace/cli"
    npm install -g @googleworkspace/cli
    ok "gws installed via npm: $(gws --version 2>&1 | head -1 || echo 'version unknown')"
  else
    err "Neither Homebrew nor npm available. Install gws manually:"
    say "    https://github.com/googleworkspace/cli/releases"
    exit 1
  fi
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

# ─── Step 4: Migrate gws state to ramdisk ───────────────────────────────────
# Migration BEFORE agent reload: if the operator was already authenticated
# locally, this moves the real state onto the ramdisk so it survives the
# reload-and-render cycle. If they were NOT yet authenticated, the ramdisk
# starts empty and we leave agent reload for later (see step 6).
step "4. Migrate gws to RAM disk"

bash "${SCRIPT_DIR}/gws-migrate-to-ramdisk.sh"

# Detect whether the operator was already authenticated by checking for the
# minimum set of state files on the ramdisk after migration. If yes, we can
# push to Infisical and reload the agent safely. If no, we defer the reload
# until after the operator runs `gws auth login` and re-runs this script.
RAMDISK_GWS="/Volumes/wd-ramdisk/gws"
ENC_GWS_FILE="${RAMDISK_GWS}/credentials.${OPERATOR_EMAIL_B64}.enc"

if [[ -f "${ENC_GWS_FILE}" && -f "${RAMDISK_GWS}/.encryption_key" && -f "${RAMDISK_GWS}/accounts.json" ]]; then
  HAVE_LOCAL_AUTH=1
  ok "existing gws auth state detected on ramdisk"
else
  HAVE_LOCAL_AUTH=0
  warn "no existing gws auth state — agent reload deferred until after \`gws auth login\`"
fi

# ─── Step 5: Push existing state to Infisical (if any) ──────────────────────
# CRITICAL ordering: this push MUST happen before the agent reload, otherwise
# the next agent poll renders empty templates (no values in Infisical yet) and
# the post-render hook decodes empty-into-empty, clobbering the just-migrated
# auth state on the ramdisk.
step "5. Push gws state to Infisical (race-safety, before agent reload)"

if [[ "${HAVE_LOCAL_AUTH}" = "1" ]]; then
  if bash "${SCRIPT_DIR}/gws-push-tokens-to-infisical.sh"; then
    ok "gws state pushed to Infisical"
  else
    err "push failed — refusing to reload the agent (would risk clobbering ramdisk state)"
    say "    Check ${WORKDESK_ROOT}/system/log/gws-push.log and re-run."
    exit 1
  fi
else
  say "  Skipped — no local state to push yet."
fi

# ─── Step 6: Reload Infisical Agent (only if state was pushed) ──────────────
step "6. Reload Infisical Agent"

if [[ "${HAVE_LOCAL_AUTH}" = "1" ]]; then
  if [[ -f "${LAUNCHAGENT_DIR}/${AGENT_PLIST_NAME}" ]]; then
    launchctl unload "${LAUNCHAGENT_DIR}/${AGENT_PLIST_NAME}" 2>/dev/null || true
    launchctl load   "${LAUNCHAGENT_DIR}/${AGENT_PLIST_NAME}"
    ok "agent reloaded — give it a moment to re-render"
    sleep 4
  else
    err "${LAUNCHAGENT_DIR}/${AGENT_PLIST_NAME} not found — foundation incomplete"
    exit 1
  fi
else
  warn "deferred — reload happens automatically when you re-run setup-gws.sh after \`gws auth login\`"
fi

# ─── Step 7: Operator next steps ────────────────────────────────────────────
step "7. Next steps"

if [[ "${HAVE_LOCAL_AUTH}" = "1" ]]; then
  cat <<EOF

${bold}${grn}gws layer wired up + state pushed to Infisical.${rst}

${bold}Verify (right now):${rst}
    gws auth status
    gws calendar events list --params '{"calendarId":"primary","maxResults":3}'

${bold}Reboot test:${rst}
    Reboot once. After login, run \`gws auth status\` again — it should
    show authenticated without any browser prompt. That confirms the
    Infisical Agent re-rendered your state from the ramdisk.

${bold}Optional — for future re-auths via the shell wrapper:${rst}
    Append to ~/.zshrc:
        source ${WORKDESK_ROOT}/config/shell/gws-env.sh
    Then a fresh shell's \`gws auth login\` will pull OAuth-app creds
    from Infisical for you, instead of you copy-pasting them.

${bold}After \`gws auth login\` (any time you re-auth):${rst}
    Always re-run:
        bash ${WORKDESK_ROOT}/config/scripts/gws-push-tokens-to-infisical.sh
    A re-auth rotates the refresh token; without the push, the next
    reboot reverts to the stale token and gws prompts for browser OAuth.

${bold}Cleanup (after the reboot test passes):${rst}
    ls ~/Library/Application\ Support/gws.bak.*
    rm -rf ~/Library/Application\ Support/gws.bak.<timestamp>
EOF
else
  cat <<EOF

${bold}${ylw}gws agent.yaml wired up, but the agent is NOT yet reloaded.${rst}

Reason: no existing gws auth state was found on this machine. Reloading
the agent now would have it poll Infisical (which has no values yet) and
write empty files to the ramdisk on the next poll.

${bold}Next steps:${rst}
  1. Append to ~/.zshrc, then open a fresh shell:
         source ${WORKDESK_ROOT}/config/shell/gws-env.sh

  2. Authenticate gws (opens a browser):
         gws auth login --account ${OPERATOR_EMAIL}

  3. Re-run this script — it will detect the new auth state, push it to
     Infisical, and reload the agent in the correct order:
         bash ${WORKDESK_ROOT}/config/scripts/setup-gws.sh
EOF
fi
