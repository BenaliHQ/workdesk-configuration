#!/usr/bin/env bash
# gws-post-render.sh — fired by the Infisical Agent after any gws template
# renders (and once at first-render by the launcher's sweep). Decodes the
# base64-encoded credentials file into its binary form, and enforces 600 perms
# on every rendered secret. Idempotent.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/operator-config.sh"

GWS_DIR="/Volumes/wd-ramdisk/gws"
B64="${GWS_DIR}/credentials.${OPERATOR_EMAIL_B64}.enc.b64"
ENC="${GWS_DIR}/credentials.${OPERATOR_EMAIL_B64}.enc"

if [[ -f "${B64}" ]]; then
  /usr/bin/base64 -D -i "${B64}" -o "${ENC}.tmp"
  /bin/mv -f "${ENC}.tmp" "${ENC}"
fi

# Lock down everything sensitive that the agent might have written at default
# (644) perms. Defense in depth — the ramdisk is already user-only (700), but
# any escalation would meet 600 file perms on top.
for f in \
  "${GWS_DIR}/.encryption_key" \
  "${GWS_DIR}/accounts.json" \
  "${GWS_DIR}/client_secret.json" \
  "${ENC}" \
  "${B64}"
do
  [[ -f "${f}" ]] && /bin/chmod 600 "${f}"
done

exit 0
