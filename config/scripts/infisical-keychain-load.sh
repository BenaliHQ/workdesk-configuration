#!/usr/bin/env bash
# infisical-keychain-load.sh — read the Universal Auth creds from Keychain and
# print export statements. Intended to be `eval $(...)`-ed by other scripts.
#
# Usage:
#   eval "$(bash config/scripts/infisical-keychain-load.sh)"
#
# After eval, the following env vars are set in the calling shell:
#   INFISICAL_UA_CLIENT_ID
#   INFISICAL_UA_CLIENT_SECRET

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/operator-config.sh"

CID=$(security find-generic-password -a "${OPERATOR_EMAIL}" -s "infisical-ua-client-id"     -w 2>/dev/null || true)
CSEC=$(security find-generic-password -a "${OPERATOR_EMAIL}" -s "infisical-ua-client-secret" -w 2>/dev/null || true)

if [[ -z "${CID}" || -z "${CSEC}" ]]; then
  echo "echo 'ERROR: Infisical UA creds not found in Keychain. Run infisical-keychain-store.sh first.' >&2; return 1 2>/dev/null || exit 1"
  exit 1
fi

# Single-quoted so values containing special chars survive eval intact.
printf "export INFISICAL_UA_CLIENT_ID=%q\n"     "${CID}"
printf "export INFISICAL_UA_CLIENT_SECRET=%q\n" "${CSEC}"
