# gws-env.sh — wraps the gws CLI so `gws auth login` can read its OAuth-app
# client_id/client_secret from Infisical at the moment of login, without the
# operator ever copy-pasting them.
#
# Source from ~/.zshrc:
#   source /path/to/Workdesk-OS/config/shell/gws-env.sh
#
# This defines a `gws` shell function that wraps the real binary. For normal
# API calls (`gws gmail ...`, `gws calendar ...`), gws reads its OAuth state
# from ~/Library/Application Support/gws/ (real directory on the SSD as of
# 2026-07-06; the ramdisk/agent pattern is retired), so no env vars are
# needed. The wrapper still exists for one case: `gws auth login` uses
# GOOGLE_WORKSPACE_CLI_CLIENT_ID / _CLIENT_SECRET env vars to mint a new
# refresh token. The wrapper pulls those from Infisical only when `auth login`
# is invoked, never for routine calls (requires an active `infisical login`
# user session).
#
# Multi-org (2026-07-24): each Google Workspace org has its own OAuth app in
# Infisical, keyed by the uppercase first label of the account's email domain:
#   alex@example.com           → PERSONAL_GOOGLE_WORKSPACE_EXAMPLE_CLIENT_ID / _CLIENT_SECRET
#   alex@client-co.example     → PERSONAL_GOOGLE_WORKSPACE_CLIENTCO_CLIENT_ID / _CLIENT_SECRET
# The wrapper derives the suffix from the `--account` argument to `gws auth
# login` (falling back to the operator-profile `email:` when --account is
# omitted) and injects that org's client credentials.
#
# After every `gws auth login`, also re-run:
#   bash /path/to/Workdesk-OS/config/scripts/gws-push-tokens-to-infisical.sh
# so Infisical's stored copy stays current.
#
# IMPORTANT: the function must be fully self-contained — no references to
# variables set at source time. Some environments (e.g. Claude Code shell
# snapshots) capture shell FUNCTIONS but not shell VARIABLES, so any state
# the function needs is baked in as literals at definition time (the vault
# root path) or resolved lazily at call time (the Infisical project ID).

# Find WORKDESK_ROOT from this file's location.
__wd_self="${BASH_SOURCE[0]:-${(%):-%x}}"
__wd_root="$(cd "$(dirname "${__wd_self}")/../.." && pwd)"
unset __wd_self

# Function template. Quoted heredoc → no expansion here; @@WD_ROOT@@ is
# substituted with the resolved vault root just before eval, so the defined
# function carries the path as a literal.
__wd_gws_def="$(cat <<'WD_GWS_EOF'
gws() {
  local __real="/opt/homebrew/bin/gws"
  local __root="@@WD_ROOT@@"
  if [[ "${1:-}" = "auth" && "${2:-}" = "login" ]]; then
    # Read the operator's Infisical project ID from operator-profile.md
    # frontmatter, lazily — auth login is rare, and call-time reads never
    # go stale or rely on source-time state.
    local __pid
    __pid="$(
      awk '
        /^---[[:space:]]*$/ { c++; if (c==1) {fm=1; next}; if (c==2) exit }
        fm && /^infisical-project-id:/ {
          sub(/^infisical-project-id:[[:space:]]*/, "")
          gsub(/^"|"$/, "")
          print; exit
        }
      ' "${__root}/config/operator-profile.md" 2>/dev/null
    )"
    if [[ -z "${__pid}" ]]; then
      echo "ERROR: infisical-project-id missing from operator-profile.md frontmatter." >&2
      echo "Run config/scripts/bootstrap-infisical.sh first." >&2
      return 1
    fi
    # Which org's OAuth app? Take the email from --account, falling back to
    # the operator-profile `email:`. Suffix = uppercase first label of the
    # email domain (alex@example.com → EXAMPLE).
    local __acct="" __prev="" __arg
    for __arg in "$@"; do
      if [[ "${__prev}" = "--account" ]]; then __acct="${__arg}"; break; fi
      __prev="${__arg}"
    done
    if [[ -z "${__acct}" ]]; then
      __acct="$(
        awk '
          /^---[[:space:]]*$/ { c++; if (c==1) {fm=1; next}; if (c==2) exit }
          fm && /^email:/ {
            sub(/^email:[[:space:]]*/, "")
            gsub(/^"|"$/, "")
            print; exit
          }
        ' "${__root}/config/operator-profile.md" 2>/dev/null
      )"
    fi
    if [[ "${__acct}" != *@*.* ]]; then
      echo "ERROR: cannot determine account email for gws auth login (pass --account EMAIL)." >&2
      return 1
    fi
    local __dom="${__acct#*@}"
    local __sfx
    __sfx="$(printf '%s' "${__dom%%.*}" | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z0-9_')"
    /opt/homebrew/bin/infisical run \
      --projectId="${__pid}" \
      --env=prod \
      --command="GOOGLE_WORKSPACE_CLI_CLIENT_ID=\$PERSONAL_GOOGLE_WORKSPACE_${__sfx}_CLIENT_ID GOOGLE_WORKSPACE_CLI_CLIENT_SECRET=\$PERSONAL_GOOGLE_WORKSPACE_${__sfx}_CLIENT_SECRET ${__real} $(printf '%q ' "$@")"
    return $?
  fi
  "${__real}" "$@"
}
WD_GWS_EOF
)"

eval "${__wd_gws_def//@@WD_ROOT@@/${__wd_root}}"
unset __wd_gws_def __wd_root
