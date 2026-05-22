#!/usr/bin/env bash
# infisical-names.sh — list secret NAMES from an Infisical project without
# leaking values into stdout. Use this in any Claude Code / agent session
# where you need to verify presence of secrets but don't want to absorb
# their values into context.
#
# Usage:
#   bash config/scripts/infisical-names.sh [project-id] [env]
#
# If project-id is omitted, defaults to INFISICAL_PERSONAL_PROJECT_ID from
# operator-profile.md frontmatter. Env defaults to "prod".
#
# Exit codes:
#   0 — listing succeeded (may be empty)
#   2 — bad usage
#   non-zero from infisical — surfaced as-is

set -euo pipefail

# Lenient so omitted project-id falls back to the personal default.
OPERATOR_CONFIG_LENIENT=1 \
  source "$(dirname "${BASH_SOURCE[0]}")/lib/operator-config.sh"

PROJ="${1:-${INFISICAL_PERSONAL_PROJECT_ID:-}}"
ENV="${2:-prod}"

if [[ -z "${PROJ}" ]]; then
  cat >&2 <<EOF
Usage: $0 [project-id] [env]

Lists secret names in an Infisical project without printing values.
Intended for agent/session use where the default 'infisical secrets'
command leaks every value into the context.

No project-id provided and infisical-project-id is not set in
operator-profile.md. Either pass a project-id explicitly or run
bootstrap-infisical.sh.
EOF
  exit 2
fi

# Use the agent's already-minted UA access token if the ramdisk sink is
# populated. Without this, a fresh-install shell CLI has no cached auth
# and the `infisical secrets` command falls through to interactive browser-
# login — wrong auth path (human user instead of UA identity) and noisy.
TOKEN_FILE="/Volumes/wd-ramdisk/infisical/access-token"
if [[ -s "${TOKEN_FILE}" ]]; then
  INFISICAL_TOKEN="$(cat "${TOKEN_FILE}")"
  export INFISICAL_TOKEN
fi

infisical secrets --projectId="${PROJ}" --env="${ENV}" 2>&1 \
  | awk -F'│' '
      {
        name = $2
        gsub(/^ +| +$/, "", name)
        if (name != "" && name != "SECRET NAME") print name
      }
    ' \
  | sort
