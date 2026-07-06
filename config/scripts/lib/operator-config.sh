#!/usr/bin/env bash
# operator-config.sh — single source of truth for per-operator runtime values.
#
# Sourced by every script in the Infisical / tool-auth stack.
# Reads operator-profile.md frontmatter and exports:
#
#   OPERATOR_NAME                   from `name:`
#   OPERATOR_EMAIL                  from `email:`
#   OPERATOR_KEY_SUFFIX             from `infisical-key-suffix:`, or uppercase
#                                     local part of OPERATOR_EMAIL if unset
#   OPERATOR_EMAIL_B64              base64(email) with padding stripped — used
#                                     as the gws credentials filename suffix
#   INFISICAL_PERSONAL_PROJECT_ID   from `infisical-project-id:`
#   WORKDESK_ROOT                   derived from this script's location
#
# Usage:
#   source "$(dirname "$0")/lib/operator-config.sh"     # from a sibling script
#   source "${WORKDESK_ROOT}/config/scripts/lib/operator-config.sh"
#
# Exits non-zero with a helpful message if any required field is missing,
# unless OPERATOR_CONFIG_LENIENT=1 is set (used by bootstrap-infisical.sh,
# which writes the missing values).

set -u

# Path resolution — find WORKDESK_ROOT from this script's location.
_lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDESK_ROOT="$(cd "${_lib_dir}/../../.." && pwd)"
export WORKDESK_ROOT

_profile="${WORKDESK_ROOT}/config/operator-profile.md"

if [[ ! -f "${_profile}" ]]; then
  echo "ERROR: operator-profile.md not found at ${_profile}" >&2
  return 1 2>/dev/null || exit 1
fi

# Parse a single frontmatter field. Matches `key: "value"` or `key: value`
# inside the leading `---` block. Empty values return empty strings.
_read_frontmatter_field() {
  local key="$1"
  awk -v key="${key}" '
    BEGIN { in_fm = 0; count = 0 }
    /^---[[:space:]]*$/ {
      count++
      if (count == 1) { in_fm = 1; next }
      if (count == 2) { exit }
    }
    in_fm && $0 ~ "^" key ":" {
      sub("^" key ":[[:space:]]*", "")
      gsub(/^"|"$/, "")
      gsub(/^'\''|'\''$/, "")
      print
      exit
    }
  ' "${_profile}"
}

OPERATOR_NAME="$(_read_frontmatter_field name)"
OPERATOR_EMAIL="$(_read_frontmatter_field email)"
OPERATOR_KEY_SUFFIX="$(_read_frontmatter_field infisical-key-suffix)"
INFISICAL_PERSONAL_PROJECT_ID="$(_read_frontmatter_field infisical-project-id)"

# Derive suffix from email local-part if not explicitly set.
if [[ -z "${OPERATOR_KEY_SUFFIX}" && -n "${OPERATOR_EMAIL}" ]]; then
  OPERATOR_KEY_SUFFIX="$(printf '%s' "${OPERATOR_EMAIL%@*}" | tr '[:lower:]' '[:upper:]')"
fi

# Derive base64-encoded email (used as a filename component).
if [[ -n "${OPERATOR_EMAIL}" ]]; then
  OPERATOR_EMAIL_B64="$(printf '%s' "${OPERATOR_EMAIL}" | base64 | tr -d '=\n')"
else
  OPERATOR_EMAIL_B64=""
fi

export OPERATOR_NAME OPERATOR_EMAIL OPERATOR_KEY_SUFFIX OPERATOR_EMAIL_B64 INFISICAL_PERSONAL_PROJECT_ID

# Required-field check. Bootstrap sets OPERATOR_CONFIG_LENIENT=1 to suppress
# this so it can fill in missing values.
if [[ "${OPERATOR_CONFIG_LENIENT:-0}" != "1" ]]; then
  _missing=()
  [[ -z "${OPERATOR_EMAIL}" ]] && _missing+=("email")
  [[ -z "${INFISICAL_PERSONAL_PROJECT_ID}" ]] && _missing+=("infisical-project-id")
  if (( ${#_missing[@]} > 0 )); then
    cat >&2 <<EOF
ERROR: operator-profile.md is missing required fields for the Infisical layer:
  ${_missing[*]}

Profile: ${_profile}

Run \`bash config/scripts/bootstrap-infisical.sh\` to populate them
interactively, or edit the frontmatter directly.
EOF
    return 1 2>/dev/null || exit 1
  fi
fi

unset _lib_dir _profile _missing
