# gws-env.sh — wraps the gws CLI so `gws auth login` can read its OAuth-app
# client_id/client_secret from Infisical at the moment of login, without the
# operator ever copy-pasting them.
#
# Source from ~/.zshrc:
#   source /path/to/Workdesk-OS/config/shell/gws-env.sh
#
# This defines a `gws` shell function that wraps the real binary. For normal
# API calls (`gws gmail ...`, `gws calendar ...`), gws reads its OAuth state
# from /Volumes/wd-ramdisk/gws/ (rendered by the Infisical Agent), so no env
# vars are needed. The wrapper still exists for one case: `gws auth login`
# uses GOOGLE_WORKSPACE_CLI_CLIENT_ID / _CLIENT_SECRET env vars to mint a new
# refresh token. The wrapper pulls those from Infisical only when `auth login`
# is invoked, never for routine calls.
#
# After every `gws auth login`, also re-run:
#   bash /path/to/Workdesk-OS/config/scripts/gws-push-tokens-to-infisical.sh
# otherwise the next reboot reverts to the stale token.

__wd_gws_real="/opt/homebrew/bin/gws"

# Find WORKDESK_ROOT from this file's location.
__wd_self="${BASH_SOURCE[0]:-${(%):-%x}}"
__wd_root="$(cd "$(dirname "${__wd_self}")/../.." && pwd)"
unset __wd_self

# Read the operator's Infisical project ID from operator-profile.md frontmatter.
__wd_personal_pid="$(
  awk '
    /^---[[:space:]]*$/ { c++; if (c==1) {fm=1; next}; if (c==2) exit }
    fm && /^infisical-project-id:/ {
      sub(/^infisical-project-id:[[:space:]]*/, "")
      gsub(/^"|"$/, "")
      print; exit
    }
  ' "${__wd_root}/config/operator-profile.md" 2>/dev/null
)"

gws() {
  if [[ "${1:-}" = "auth" && "${2:-}" = "login" ]]; then
    if [[ -z "${__wd_personal_pid}" ]]; then
      echo "ERROR: infisical-project-id missing from operator-profile.md frontmatter." >&2
      echo "Run config/scripts/bootstrap-infisical.sh first." >&2
      return 1
    fi
    /opt/homebrew/bin/infisical run \
      --projectId="${__wd_personal_pid}" \
      --env=prod \
      --command="GOOGLE_WORKSPACE_CLI_CLIENT_ID=\$PERSONAL_GOOGLE_WORKSPACE_CLIENT_ID GOOGLE_WORKSPACE_CLI_CLIENT_SECRET=\$PERSONAL_GOOGLE_WORKSPACE_CLIENT_SECRET ${__wd_gws_real} $(printf '%q ' "$@")"
    return $?
  fi
  "${__wd_gws_real}" "$@"
}
