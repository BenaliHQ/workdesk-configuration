#!/usr/bin/env bash
# gws-push-tokens-to-infisical.sh — push current gws per-user state (encrypted
# refresh token, encryption key, accounts.json) to Infisical so the next reboot
# renders the fresh value. Idempotent: mtime markers prevent no-op pushes when
# called from a daemon or shell wrapper after every auth.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/operator-config.sh"

ENV="prod"
GWS_DIR="${HOME}/Library/Application Support/gws"
ENC_FILE="${GWS_DIR}/credentials.${OPERATOR_EMAIL_B64}.enc"
KEY_FILE="${GWS_DIR}/.encryption_key"
ACCTS_FILE="${GWS_DIR}/accounts.json"
LOG="${WORKDESK_ROOT}/system/log/gws-push.log"

mkdir -p "$(dirname "${LOG}")"

# Source files must exist (script can be called proactively, so bail quietly).
for f in "${ENC_FILE}" "${KEY_FILE}" "${ACCTS_FILE}"; do
  if [[ ! -f "${f}" ]]; then
    echo "$(date -u +%FT%TZ) skip: missing ${f}" >> "${LOG}"
    exit 0
  fi
done

# Auth: relies on the operator's `infisical login` user session (machine
# identities retired 2026-07-06). If the session has expired, pushes fail and
# are logged — re-run `infisical login`, then this script.

push_if_stale() {
  local src="$1" name="$2" transform="$3"
  local marker="${src}.last-push"
  if [[ -f "${marker}" && "${marker}" -nt "${src}" ]]; then
    return 0   # marker newer than source — no push needed
  fi
  local val
  case "${transform}" in
    base64) val=$(/usr/bin/base64 -i "${src}" | /usr/bin/tr -d '\n') ;;
    raw)    val=$(cat "${src}") ;;
    *)      echo "$(date -u +%FT%TZ) ERROR: unknown transform ${transform}" >> "${LOG}"; return 1 ;;
  esac
  if /opt/homebrew/bin/infisical secrets set "${name}=${val}" \
       --projectId="${INFISICAL_PERSONAL_PROJECT_ID}" --env="${ENV}" --path=/ >/dev/null 2>&1; then
    touch "${marker}"
    echo "$(date -u +%FT%TZ) pushed ${name}" >> "${LOG}"
  else
    echo "$(date -u +%FT%TZ) FAILED to push ${name}" >> "${LOG}"
  fi
  unset val
}

push_if_stale "${ENC_FILE}"   "PERSONAL_GWS_CREDENTIALS_${OPERATOR_KEY_SUFFIX}_ENC_B64" base64
push_if_stale "${KEY_FILE}"   "PERSONAL_GWS_ENCRYPTION_KEY"                              raw
push_if_stale "${ACCTS_FILE}" "PERSONAL_GWS_ACCOUNTS_JSON"                               raw
