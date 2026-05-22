#!/usr/bin/env bash
# infisical-keychain-store.sh — one-time setup: stash the Infisical Universal
# Auth client-id and client-secret in macOS Keychain.
#
# Manual prerequisite:
#   1. Go to https://app.infisical.com → your personal project → Access Control →
#      Machine Identities → Create.
#   2. Authentication method: Universal Auth.
#   3. Role: assign a read-only role (Viewer) scoped to the project.
#   4. After creation, generate a Client Secret. Copy the Client ID and the
#      Client Secret — the secret is shown ONCE.
#
# Run this script and paste each value when prompted. Values are stored in the
# default login keychain as generic passwords; the keychain is encrypted at
# rest by macOS and unlocked at login.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/operator-config.sh"

SERVICE_ID="infisical-ua-client-id"
SERVICE_SECRET="infisical-ua-client-secret"

read -rp "Infisical Universal Auth — Client ID: " CLIENT_ID
read -rsp "Infisical Universal Auth — Client Secret (input hidden): " CLIENT_SECRET
echo

if [[ -z "${CLIENT_ID}" || -z "${CLIENT_SECRET}" ]]; then
  echo "ERROR: both values are required." >&2
  exit 1
fi

# -U updates the entry if it already exists.
security add-generic-password -U -a "${OPERATOR_EMAIL}" -s "${SERVICE_ID}"     -w "${CLIENT_ID}"
security add-generic-password -U -a "${OPERATOR_EMAIL}" -s "${SERVICE_SECRET}" -w "${CLIENT_SECRET}"

echo "stored both values in Keychain under account=${OPERATOR_EMAIL}"
echo "verify with:"
echo "  security find-generic-password -a ${OPERATOR_EMAIL} -s ${SERVICE_ID}     -w"
echo "  security find-generic-password -a ${OPERATOR_EMAIL} -s ${SERVICE_SECRET} -w"
