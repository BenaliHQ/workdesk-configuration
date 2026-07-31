#!/usr/bin/env bash
# gws-push-tokens-to-infisical.sh — push current gws per-user state to Infisical
# so a new or wiped machine can restore without redoing the browser OAuth flow.
# Idempotent: mtime markers prevent no-op pushes when called repeatedly.
#
# LAYOUT-AWARE. Two on-disk layouts exist across gws versions:
#
#   xdg     (gws ~0.22+): ~/.config/gws/
#             - credentials.enc            (single file; the encrypted refresh token)
#             - account_timezone           (small metadata; replaces accounts.json)
#             - encryption key             → macOS Keychain, service "gws-cli"
#   legacy  (older gws):  ~/Library/Application Support/gws/
#             - credentials.<b64-email>.enc
#             - .encryption_key            (file)
#             - accounts.json
#
# This script detects which is present and pushes accordingly.
#
# The routine push (fired after every `gws auth login`) syncs the FILE state
# that ROTATES — credentials.enc (+ account_timezone) — headlessly, no prompt.
# On the xdg layout the encryption key lives in the Keychain; reading it
# triggers a one-time GUI approval, so it is pushed ONLY when called with
# --include-keychain-key (setup-gws.sh passes this during interactive setup,
# where you can click Allow). The key is stable per install, so once it's in
# Infisical the routine credentials-only pushes are enough for a restore.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/operator-config.sh"

ENV="prod"
LOG="${WORKDESK_ROOT}/system/log/gws-push.log"
mkdir -p "$(dirname "${LOG}")"

INCLUDE_KEYCHAIN_KEY=0
for arg in "$@"; do
  case "${arg}" in
    --include-keychain-key) INCLUDE_KEYCHAIN_KEY=1 ;;
  esac
done

log() { echo "$(date -u +%FT%TZ) $*" >> "${LOG}"; }

# ── Detect layout ────────────────────────────────────────────────────────────
XDG_DIR="${HOME}/.config/gws"
LEGACY_DIR="${HOME}/Library/Application Support/gws"

if [[ -f "${XDG_DIR}/credentials.enc" ]]; then
  LAYOUT="xdg"
  ENC_FILE="${XDG_DIR}/credentials.enc"
  TZ_FILE="${XDG_DIR}/account_timezone"
elif [[ -f "${LEGACY_DIR}/credentials.${OPERATOR_EMAIL_B64}.enc" ]]; then
  LAYOUT="legacy"
  ENC_FILE="${LEGACY_DIR}/credentials.${OPERATOR_EMAIL_B64}.enc"
  KEY_FILE="${LEGACY_DIR}/.encryption_key"
  ACCTS_FILE="${LEGACY_DIR}/accounts.json"
else
  log "skip: no gws credentials found in ${XDG_DIR} or ${LEGACY_DIR}"
  exit 0
fi

# Auth: relies on the operator's `infisical login` user session. If it has
# expired, pushes fail and are logged — re-run `infisical login`, then this.

set_secret() {  # name value
  local name="$1" val="$2"
  if /opt/homebrew/bin/infisical secrets set "${name}=${val}" \
       --projectId="${INFISICAL_PERSONAL_PROJECT_ID}" --env="${ENV}" --path=/ >/dev/null 2>&1; then
    log "pushed ${name}"
    return 0
  fi
  log "FAILED to push ${name}"
  return 1
}

push_file_if_stale() {  # src name transform
  local src="$1" name="$2" transform="$3"
  if [[ ! -f "${src}" ]]; then
    log "skip: missing ${src}"
    return 0
  fi
  local marker="${src}.last-push"
  if [[ -f "${marker}" && "${marker}" -nt "${src}" ]]; then
    return 0   # marker newer than source — no push needed
  fi
  local val
  case "${transform}" in
    base64) val=$(/usr/bin/base64 -i "${src}" | /usr/bin/tr -d '\n') ;;
    raw)    val=$(cat "${src}") ;;
    *)      log "ERROR: unknown transform ${transform}"; return 1 ;;
  esac
  if set_secret "${name}" "${val}"; then touch "${marker}"; fi
  unset val
}

CRED_NAME="PERSONAL_GWS_CREDENTIALS_${OPERATOR_KEY_SUFFIX}_ENC_B64"

if [[ "${LAYOUT}" == "xdg" ]]; then
  # Rotating file state — headless, no prompt.
  push_file_if_stale "${ENC_FILE}" "${CRED_NAME}"                 base64
  push_file_if_stale "${TZ_FILE}"  "PERSONAL_GWS_ACCOUNT_TIMEZONE" raw

  # Stable Keychain key — reading it prompts for approval, so gate it.
  if [[ "${INCLUDE_KEYCHAIN_KEY}" == "1" ]]; then
    # base64 the value so binary or newline-bearing keys round-trip cleanly.
    key_b64="$(/usr/bin/security find-generic-password -s gws-cli -w 2>/dev/null \
                 | /usr/bin/base64 | /usr/bin/tr -d '\n' || true)"
    if [[ -n "${key_b64}" ]]; then
      set_secret "PERSONAL_GWS_ENCRYPTION_KEY_B64" "${key_b64}" || true
    else
      log "skip: could not read gws-cli Keychain key (approval declined or item absent)"
    fi
    unset key_b64
  fi
else
  push_file_if_stale "${ENC_FILE}"   "${CRED_NAME}"                base64
  push_file_if_stale "${KEY_FILE}"   "PERSONAL_GWS_ENCRYPTION_KEY" raw
  push_file_if_stale "${ACCTS_FILE}" "PERSONAL_GWS_ACCOUNTS_JSON"  raw
fi
