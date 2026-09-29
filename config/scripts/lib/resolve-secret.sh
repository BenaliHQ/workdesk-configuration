#!/usr/bin/env bash
# resolve-secret.sh — resolve one runtime secret without source-time side effects.
#
# wd_resolve_secret <SECRET_NAME>
# Prints the secret value. Resolution order:
#   1. env var of the same name
#   2. Infisical via the `infisical login` user session
#   3. Infisical via the Universal Auth machine identity in the macOS keychain
# Returns non-zero with an actionable message on stderr if none are available.
#
# Why step 3 exists: the user session from `infisical login` expires roughly
# every 60 days, and nothing renews it unattended. When it lapses, every
# unattended fetch (transcript pulls, gws token refresh) fails with "No <KEY>
# available" until the operator notices and re-runs the browser flow. The
# machine identity has no such expiry and needs no TTY, so it keeps scheduled
# and scripted work alive across a lapsed user session. The user session is
# still preferred — this is a fallback, not a replacement.
#
# Keychain items (created by the Jun 2026 UA setup):
#   infisical-ua-client-id      client id for universal auth
#   infisical-ua-client-secret  client secret for universal auth

# shellcheck disable=SC1091,SC2034

# Mint an Infisical access token from the Universal Auth machine identity and
# export it as INFISICAL_TOKEN, which the CLI picks up automatically.
#
# Cached per shell: once INFISICAL_TOKEN is set, later calls reuse it rather
# than re-exchanging credentials for every secret. A failed exchange is also
# remembered, so a machine with no UA creds pays the lookup cost once.
_wd_mint_ua_token() {
  [[ -n "${INFISICAL_TOKEN:-}" ]] && return 0
  [[ -n "${_WD_UA_ATTEMPTED:-}" ]] && return 1
  _WD_UA_ATTEMPTED=1

  command -v security >/dev/null 2>&1 || return 1
  command -v infisical >/dev/null 2>&1 || return 1

  local client_id client_secret token
  client_id="$(security find-generic-password -s 'infisical-ua-client-id' -w 2>/dev/null)" || return 1
  client_secret="$(security find-generic-password -s 'infisical-ua-client-secret' -w 2>/dev/null)" || return 1
  [[ -n "$client_id" && -n "$client_secret" ]] || return 1

  token="$(INFISICAL_DISABLE_UPDATE_CHECK=true infisical login \
    --method=universal-auth \
    --client-id="$client_id" \
    --client-secret="$client_secret" \
    --plain --silent </dev/null 2>/dev/null)" || return 1
  [[ -n "$token" ]] || return 1

  export INFISICAL_TOKEN="$token"
  return 0
}

# Fetch one secret from the personal project. Prints the value and returns 0 on
# success; returns non-zero and prints nothing on failure.
#
# </dev/null stops the CLI from blocking on its interactive login wizard when no
# session exists — but it does NOT stop it from writing that wizard to *stdout*
# first. A dead session therefore yields a non-empty capture full of ANSI cursor
# and colour codes, which is indistinguishable from a secret unless inspected.
# Treat any ESC byte or login-flow marker as failure rather than a value; real
# secret values never contain terminal control sequences.
_wd_infisical_get() {
  local secret_name="$1" out
  # A failed provider exit is a failed lookup even if it printed something:
  # partial or error output must never be returned as a credential.
  out="$(INFISICAL_DISABLE_UPDATE_CHECK=true infisical secrets get "$secret_name" \
    --projectId="$INFISICAL_PERSONAL_PROJECT_ID" --env=prod --plain \
    </dev/null 2>/dev/null)" || return 1

  [[ -n "$out" ]] || return 1
  case "$out" in
    *$'\x1b'*|*"valid login session"*|*"hosting option"*|*"Unable to parse domain"*)
      return 1 ;;
  esac

  printf '%s' "$out"
}

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
  local lib_dir OPERATOR_CONFIG_LENIENT=1
  lib_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  source "$lib_dir/operator-config.sh" 2>/dev/null || true

  if [[ -n "${INFISICAL_PERSONAL_PROJECT_ID:-}" ]] && command -v infisical >/dev/null 2>&1; then
    # Attempt 1 — whatever session already exists (user login, or a token the
    # caller exported).
    if value="$(_wd_infisical_get "$secret_name")"; then
      printf '%s' "$value"
      return 0
    fi

    # Attempt 2 — the user session is missing or expired; fall back to the
    # machine identity and retry once.
    if _wd_mint_ua_token && value="$(_wd_infisical_get "$secret_name")"; then
      printf '%s' "$value"
      return 0
    fi
  fi

  printf 'No %s available. Either export %s, or configure Infisical (bash config/scripts/bootstrap-infisical.sh) and store the key there.\n' \
    "$secret_name" "$secret_name" >&2
  return 1
}
