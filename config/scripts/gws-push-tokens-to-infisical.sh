#!/usr/bin/env bash
# gws-push-tokens-to-infisical.sh — push current gws per-user state (encrypted
# refresh tokens, encryption key, accounts.json) to Infisical so the next
# restore renders the fresh values. Idempotent: mtime markers prevent no-op
# pushes when called from a daemon or shell wrapper after every auth.
#
# Multi-account (2026-07-24): every credentials.<b64-email>.enc file in the
# gws state dir is pushed. The Infisical key suffix is the uppercase first
# label of the account's email domain:
#   alex@example.com           → PERSONAL_GWS_CREDENTIALS_EXAMPLE_ENC_B64
#   alex@client-co.example     → PERSONAL_GWS_CREDENTIALS_CLIENTCO_ENC_B64

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/operator-config.sh"

ENV="prod"
GWS_DIR="${HOME}/Library/Application Support/gws"
KEY_FILE="${GWS_DIR}/.encryption_key"
ACCTS_FILE="${GWS_DIR}/accounts.json"
LOG="${WORKDESK_ROOT}/system/log/gws-push.log"

mkdir -p "$(dirname "${LOG}")"

# Shared state files must exist (script can be called proactively, so bail quietly).
for f in "${KEY_FILE}" "${ACCTS_FILE}"; do
  if [[ ! -f "${f}" ]]; then
    echo "$(date -u +%FT%TZ) skip: missing ${f}" >> "${LOG}"
    exit 0
  fi
done

# Derive the Infisical key suffix from an account email: uppercase first
# label of the domain, non-alphanumerics stripped.
suffix_for_email() {
  local dom="${1#*@}"
  printf '%s' "${dom%%.*}" | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z0-9_'
}

# Decode the b64-email component of a credentials filename (padding stripped
# by gws; restore it before decoding).
email_from_b64() {
  local b64="$1"
  case $(( ${#b64} % 4 )) in
    2) b64="${b64}==" ;;
    3) b64="${b64}=" ;;
  esac
  printf '%s' "${b64}" | /usr/bin/base64 -D 2>/dev/null
}

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

# Push every registered account's encrypted credential.
for enc in "${GWS_DIR}"/credentials.*.enc; do
  [[ -f "${enc}" ]] || continue
  b64part="${enc##*/credentials.}"
  b64part="${b64part%.enc}"
  email="$(email_from_b64 "${b64part}")"
  if [[ "${email}" != *@*.* ]]; then
    echo "$(date -u +%FT%TZ) skip: cannot decode account email from ${enc}" >> "${LOG}"
    continue
  fi
  push_if_stale "${enc}" "PERSONAL_GWS_CREDENTIALS_$(suffix_for_email "${email}")_ENC_B64" base64
done

push_if_stale "${KEY_FILE}"   "PERSONAL_GWS_ENCRYPTION_KEY" raw
push_if_stale "${ACCTS_FILE}" "PERSONAL_GWS_ACCOUNTS_JSON"  raw
