#!/usr/bin/env bash
# setup-gws.sh — interactive setup for the gws layer on top of the Infisical
# foundation. Idempotent. Re-running is safe.
#
# Prerequisite: bootstrap-infisical.sh has been run on this machine (operator
# profile populated, `infisical login` user session working).
#
# gws keeps its OAuth state in ~/Library/Application Support/gws/ — a normal
# directory on disk (FileVault covers encryption at rest). Infisical holds a
# synced copy of that state so a new machine (or a wiped one) can restore it
# without redoing the browser OAuth flow.
#
# Walks through:
#   1. Preflight — Infisical session works + gws is installed (or install it)
#   2. State dir — ensure ~/Library/Application Support/gws is a real directory
#                  (repairs the legacy ramdisk symlink if present)
#   3. Restore   — if no local auth state, pull the synced copy from Infisical;
#                  if Infisical has none either, walk through `gws auth login`
#   4. Push      — sync current local state back to Infisical
#   5. Verify    — `gws auth status` + next steps

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/operator-config.sh"

SCRIPT_DIR="${WORKDESK_ROOT}/config/scripts"
GWS_DIR="${HOME}/Library/Application Support/gws"
ENC_FILE="${GWS_DIR}/credentials.${OPERATOR_EMAIL_B64}.enc"
KEY_FILE="${GWS_DIR}/.encryption_key"
ACCTS_FILE="${GWS_DIR}/accounts.json"
CLIENT_FILE="${GWS_DIR}/client_secret.json"

export INFISICAL_DISABLE_UPDATE_CHECK=true

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

# Fetch one secret value via the operator's user session. </dev/null keeps the
# CLI from dropping into its interactive wizard when the session has expired.
fetch_secret() {
  local key="$1"
  /opt/homebrew/bin/infisical secrets get "${key}" \
    --projectId="${INFISICAL_PERSONAL_PROJECT_ID}" --env=prod --plain \
    </dev/null 2>/dev/null
}

have_local_auth() {
  [[ -f "${ENC_FILE}" && -f "${KEY_FILE}" && -f "${ACCTS_FILE}" ]]
}

# ─── Step 1: Preflight ──────────────────────────────────────────────────────
step "1. Preflight"

if [[ -z "${INFISICAL_PERSONAL_PROJECT_ID}" ]]; then
  err "infisical-project-id missing from operator-profile.md."
  say "    Run config/scripts/bootstrap-infisical.sh first."
  exit 1
fi

if bash "${SCRIPT_DIR}/infisical-names.sh" </dev/null >/dev/null 2>&1; then
  ok "Infisical user session works"
else
  err "No working Infisical session — run \`infisical login\`, then re-run this script."
  exit 1
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

# ─── Step 2: State directory ────────────────────────────────────────────────
step "2. gws state directory"

if [[ -L "${GWS_DIR}" ]]; then
  # Legacy layout: symlink into the retired wd-ramdisk. Replace with a real
  # directory, carrying over any content still resolvable through the link.
  warn "legacy symlink detected at ${GWS_DIR} — converting to a real directory"
  tmp_dir="$(mktemp -d)"
  if [[ -d "${GWS_DIR}/" ]]; then
    cp -a "${GWS_DIR}/." "${tmp_dir}/" 2>/dev/null || true
  fi
  rm "${GWS_DIR}"
  mkdir -p "${GWS_DIR}"
  cp -a "${tmp_dir}/." "${GWS_DIR}/" 2>/dev/null || true
  rm -rf "${tmp_dir}"
  ok "converted to a real directory"
elif [[ -d "${GWS_DIR}" ]]; then
  ok "real directory in place"
else
  mkdir -p "${GWS_DIR}"
  ok "created ${GWS_DIR}"
fi
chmod 700 "${GWS_DIR}"

# ─── Step 3: Restore auth state ─────────────────────────────────────────────
step "3. Auth state"

if have_local_auth; then
  ok "existing local gws auth state found"
else
  say "  No local auth state — trying to restore the synced copy from Infisical."
  enc_b64="$(fetch_secret "PERSONAL_GWS_CREDENTIALS_${OPERATOR_KEY_SUFFIX}_ENC_B64" || true)"
  enc_key="$(fetch_secret "PERSONAL_GWS_ENCRYPTION_KEY" || true)"
  accounts="$(fetch_secret "PERSONAL_GWS_ACCOUNTS_JSON" || true)"

  if [[ -n "${enc_b64}" && -n "${enc_key}" && -n "${accounts}" ]]; then
    printf '%s' "${enc_b64}" | /usr/bin/base64 -D -o "${ENC_FILE}"
    printf '%s'  "${enc_key}"  > "${KEY_FILE}"
    printf '%s\n' "${accounts}" > "${ACCTS_FILE}"
    ok "restored encrypted credentials, encryption key, accounts.json"
  else
    warn "Infisical has no synced gws state yet — a browser login is needed."
    HAVE_NO_AUTH=1
  fi
fi

# client_secret.json — rebuilt from the three OAuth-app keys whenever missing.
if [[ ! -f "${CLIENT_FILE}" ]]; then
  g_cid="$(fetch_secret PERSONAL_GOOGLE_WORKSPACE_CLIENT_ID || true)"
  g_pid="$(fetch_secret PERSONAL_GOOGLE_WORKSPACE_PROJECT_ID || true)"
  g_sec="$(fetch_secret PERSONAL_GOOGLE_WORKSPACE_CLIENT_SECRET || true)"
  if [[ -n "${g_cid}" && -n "${g_pid}" && -n "${g_sec}" ]]; then
    cat > "${CLIENT_FILE}" <<JSON
{
  "installed": {
    "client_id": "${g_cid}",
    "project_id": "${g_pid}",
    "client_secret": "${g_sec}",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "redirect_uris": ["http://localhost"]
  }
}
JSON
    ok "rebuilt client_secret.json from Infisical OAuth-app keys"
  else
    warn "PERSONAL_GOOGLE_WORKSPACE_* keys not all present in Infisical — client_secret.json not built"
    say  "    Store CLIENT_ID / PROJECT_ID / CLIENT_SECRET in your personal project, then re-run."
  fi
  unset g_cid g_pid g_sec
fi

# Lock down perms on everything sensitive.
for f in "${KEY_FILE}" "${ACCTS_FILE}" "${CLIENT_FILE}" "${ENC_FILE}"; do
  [[ -f "${f}" ]] && chmod 600 "${f}"
done

# ─── Step 4: Push current state to Infisical ────────────────────────────────
step "4. Sync state to Infisical"

if have_local_auth; then
  if bash "${SCRIPT_DIR}/gws-push-tokens-to-infisical.sh"; then
    ok "gws state synced to Infisical"
  else
    warn "push failed — check ${WORKDESK_ROOT}/system/log/gws-push.log"
  fi
else
  say "  Skipped — no local state to push yet."
fi

# ─── Step 5: Verify / next steps ────────────────────────────────────────────
step "5. Next steps"

if have_local_auth; then
  cat <<EOF

${bold}${grn}gws layer set up.${rst}

${bold}Verify (right now):${rst}
    gws auth status
    gws calendar events list --params '{"calendarId":"primary","maxResults":3}'

${bold}Optional — for future re-auths via the shell wrapper:${rst}
    Append to ~/.zshrc:
        source ${WORKDESK_ROOT}/config/shell/gws-env.sh
    Then a fresh shell's \`gws auth login\` will pull OAuth-app creds
    from Infisical for you, instead of you copy-pasting them.

${bold}After \`gws auth login\` (any time you re-auth):${rst}
    Always re-run:
        bash ${WORKDESK_ROOT}/config/scripts/gws-push-tokens-to-infisical.sh
    A re-auth rotates the refresh token; without the push, Infisical's
    synced copy goes stale and a future restore gets a dead token.
EOF
else
  cat <<EOF

${bold}${ylw}gws installed, but not yet authenticated.${rst}

${bold}Next steps:${rst}
  1. Append to ~/.zshrc, then open a fresh shell:
         source ${WORKDESK_ROOT}/config/shell/gws-env.sh

  2. Authenticate gws (opens a browser):
         gws auth login --account ${OPERATOR_EMAIL}

  3. Re-run this script — it will detect the new auth state and sync it
     to Infisical:
         bash ${WORKDESK_ROOT}/config/scripts/setup-gws.sh
EOF
fi
