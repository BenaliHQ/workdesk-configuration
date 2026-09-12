#!/usr/bin/env bash
# resolve-secret.sh — resolve one runtime secret without source-time side effects.
#
# wd_resolve_secret <SECRET_NAME>
# Prints the secret value. Resolution: env var of same name, then the macOS
# Keychain, then Infisical
# using the project from operator-config.sh. Returns non-zero with an actionable
# message on stderr if neither source is available.

# shellcheck disable=SC1091,SC2034
wd_resolve_secret() {
  local secret_name="${1:-}"
  local value
  if [[ -z "$secret_name" ]]; then
    printf 'wd_resolve_secret requires a secret name\n' >&2
    return 2
  fi
  value="${!secret_name:-}"
  if [[ -n "$value" ]]; then
    printf '%s' "$value"
    return 0
  fi
  # macOS Keychain. Checked before Infisical because Infisical user sessions
  # expire every few weeks, and a scheduled job that depends on one fails silently
  # when it does. A Keychain item does not expire and is readable from cron.
  # Service name is derived from the secret: PERSONAL_FOO_API_KEY -> "foo-api-key".
  if command -v security >/dev/null 2>&1; then
    local kc_service
    kc_service="$(printf '%s' "$secret_name" | sed 's/^PERSONAL_//' | tr 'A-Z_' 'a-z-')"
    local svc
    for svc in "$kc_service" "$secret_name"; do
      value="$(security find-generic-password -s "$svc" -w 2>/dev/null | tr -d '\r\n')"
      if [[ -n "$value" ]]; then
        printf '%s' "$value"
        return 0
      fi
    done
    value=""
  fi

  local lib_dir OPERATOR_CONFIG_LENIENT=1
  lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  source "$lib_dir/operator-config.sh" 2>/dev/null || true

  if [[ -n "${INFISICAL_PERSONAL_PROJECT_ID:-}" ]] && command -v infisical >/dev/null 2>&1; then
    if value="$(INFISICAL_DISABLE_UPDATE_CHECK=true infisical secrets get "$secret_name" \
      --projectId="$INFISICAL_PERSONAL_PROJECT_ID" --env=prod --plain \
      </dev/null 2>/dev/null)"; then
      if [[ -n "$value" ]]; then
        printf '%s' "$value"
        return 0
      fi
    fi
  fi

  printf 'No %s available. Either export %s, add it to the macOS Keychain, or configure Infisical (bash config/scripts/bootstrap-infisical.sh) and store the key there.\n' \
    "$secret_name" "$secret_name" >&2
  return 1
}
