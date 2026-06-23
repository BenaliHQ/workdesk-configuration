#!/usr/bin/env bash
# infisical-agent-run.sh — wait for the ramdisk, materialize the Universal Auth
# credential files on it (so they live in RAM, not on the SSD), spawn the
# Infisical Agent, then sweep every `*-post-render.sh` hook once after first
# renders settle. Subsequent renders (rotation) are handled by each template's
# own `execute.command` in the agent config.
#
# Why the sweep: the Infisical Agent's `execute.command` only fires when the
# rendered file content *changes* between successive renders. On a fresh boot
# (empty ramdisk → file appears), it does NOT fire. The sweep closes that gap
# exactly once per agent start across ALL tool families.

set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/operator-config.sh"

VOL_PATH="/Volumes/wd-ramdisk"
INF_DIR="${VOL_PATH}/infisical"
AGENT_CONFIG="${WORKDESK_ROOT}/config/infisical/agent.yaml"
HOOKS_DIR="${WORKDESK_ROOT}/config/scripts"
LOG="${WORKDESK_ROOT}/system/log/infisical-agent.log"

mkdir -p "$(dirname "${LOG}")"

# Wait for the ramdisk LaunchAgent to finish mounting (race at login).
for _ in $(seq 1 60); do
  if [[ -d "${VOL_PATH}" ]] && mount | grep -q "on ${VOL_PATH} "; then
    break
  fi
  sleep 0.5
done
if ! mount | grep -q "on ${VOL_PATH} "; then
  echo "$(date -u +%FT%TZ) ERROR: ramdisk never mounted at ${VOL_PATH}" >> "${LOG}"
  exit 1
fi

if [[ ! -f "${AGENT_CONFIG}" ]]; then
  echo "$(date -u +%FT%TZ) ERROR: agent config missing at ${AGENT_CONFIG}. Run bootstrap-infisical.sh." >> "${LOG}"
  exit 1
fi

mkdir -p "${INF_DIR}"
chmod 700 "${INF_DIR}"

# Pull UA creds from Keychain (encrypted at rest, OS-managed).
CID=$(security  find-generic-password -a "${OPERATOR_EMAIL}" -s "infisical-ua-client-id"     -w 2>/dev/null || true)
CSEC=$(security find-generic-password -a "${OPERATOR_EMAIL}" -s "infisical-ua-client-secret" -w 2>/dev/null || true)

if [[ -z "${CID}" || -z "${CSEC}" ]]; then
  echo "$(date -u +%FT%TZ) ERROR: UA creds missing from Keychain. Run config/scripts/infisical-keychain-store.sh." >> "${LOG}"
  exit 1
fi

# Write to ramdisk (RAM only), tight perms, no trailing newline.
printf '%s' "${CID}"  > "${INF_DIR}/client-id"
printf '%s' "${CSEC}" > "${INF_DIR}/client-secret"
chmod 600 "${INF_DIR}/client-id" "${INF_DIR}/client-secret"

# Scrub from this shell's memory.
unset CID CSEC

# Pre-create every render target's parent directory on the freshly-mounted
# ramdisk. The Infisical Agent's template engine does NOT mkdir parents — it
# opens the destination path directly. Because the ramdisk is recreated empty
# at each login, the first render of any tool layer (e.g. /Volumes/wd-ramdisk/
# gws/) fails with "no such file or directory" until something makes the dir.
# Derive the dirs from the agent config's destination-path entries so this stays
# tool-agnostic, and only ever mkdir under the ramdisk root (safety).
while IFS= read -r dest; do
  d=$(dirname "${dest}")
  case "${d}" in
    "${VOL_PATH}"/*)
      mkdir -p "${d}" && chmod 700 "${d}" || true
      ;;
  esac
done < <(grep -oE 'destination-path:[[:space:]]*"[^"]+"' "${AGENT_CONFIG}" | sed -E 's/.*"(.*)"/\1/')

echo "$(date -u +%FT%TZ) starting infisical agent with ${AGENT_CONFIG}" >> "${LOG}"

# Start agent in background so we can run the post-init sweep alongside it.
/opt/homebrew/bin/infisical agent --config "${AGENT_CONFIG}" >> "${LOG}" 2>&1 &
AGENT_PID=$!

# Forward launchd's SIGTERM/SIGINT to the agent and exit cleanly.
trap 'kill -TERM "${AGENT_PID}" 2>/dev/null; wait "${AGENT_PID}" 2>/dev/null; exit 0' TERM INT

# Post-init sweep — waits for the first burst of renders to land, then runs
# every *-post-render.sh hook once. Subsequent rotations are handled by the
# agent's per-template execute.command. Hooks are shipped by tool layers
# (gws, qbo, codex) — the foundation release has none, and the sweep is a
# no-op when no hooks exist.
(
  # Heuristic settle: poll for any tool-specific dir to appear under the
  # ramdisk root, with a 30s ceiling. If nothing shows up the agent has no
  # templates yet (foundation install) — skip the sweep cleanly.
  SEEN=0
  for _ in $(seq 1 60); do
    if compgen -G "${VOL_PATH}/*/*" >/dev/null 2>&1; then
      SEEN=1
      break
    fi
    sleep 0.5
  done

  if [[ "${SEEN}" = "1" ]]; then
    sleep 3   # let stragglers finish
    echo "$(date -u +%FT%TZ) post-init sweep: running every *-post-render.sh once" >> "${LOG}"
    for hook in "${HOOKS_DIR}"/*-post-render.sh; do
      [[ -x "${hook}" ]] || continue
      echo "$(date -u +%FT%TZ)   invoking ${hook}" >> "${LOG}"
      bash "${hook}" >> "${LOG}" 2>&1 || true
    done
    echo "$(date -u +%FT%TZ) post-init sweep complete" >> "${LOG}"
  else
    echo "$(date -u +%FT%TZ) post-init sweep skipped: no templates rendered (foundation install?)" >> "${LOG}"
  fi
) &

# Block on agent so launchd KeepAlive sees the correct lifecycle.
wait "${AGENT_PID}"
