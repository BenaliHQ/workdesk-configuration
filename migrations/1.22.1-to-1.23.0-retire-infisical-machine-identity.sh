#!/usr/bin/env bash
# 1.22.1 → 1.23.0: retire the Infisical machine-identity + RAM-disk pattern.
#
# WorkDesk's Infisical layer now authenticates exclusively via the operator's
# `infisical login` user session, and tool auth state (gws, and any other tool
# that was on the ramdisk) lives in normal on-disk directories. This migration
# converts a machine that is still on the old layout:
#
#   1. Moves any state still on /Volumes/wd-ramdisk to safe on-disk locations
#      (gws → ~/Library/Application Support/gws as a real directory; anything
#      else → a timestamped backup the operator is told about).
#   2. Repairs known symlinks into the ramdisk (~/Library/Application
#      Support/gws, ~/.codex/auth.json) into real files/directories.
#   3. Unloads and removes the com.benali.workdesk.infisical-agent and
#      com.benali.workdesk.ramdisk LaunchAgents.
#   4. Ejects the ramdisk.
#   5. Removes the rendered (generated) agent config at config/infisical/.
#
# It does NOT touch the Universal Auth credentials in the macOS Keychain, and
# it does NOT delete anything from Infisical itself. Deleting the now-unused
# machine identity in the Infisical dashboard (Access Control → Machine
# Identities) is a manual, optional cleanup — the migration prints a reminder.
#
# Idempotent: on a machine already on the new layout every step is a no-op.
#
# Env (set by migrate.sh):
#   WORKDESK_VAULT — vault root
#   WORKDESK_WD    — control-plane directory ($VAULT/config)

set -u

WD="${WORKDESK_WD:?WORKDESK_WD not set}"
RAMDISK="/Volumes/wd-ramdisk"
GWS_DIR="${HOME}/Library/Application Support/gws"
LA_DIR="${HOME}/Library/LaunchAgents"
TS="$(date +%s)"
CHANGED=0

note() { echo "retire-infisical-machine-identity: $*"; }

# ── 1+2. gws: real directory with state, never a ramdisk symlink ────────────
if [[ -L "${GWS_DIR}" ]]; then
  tmp_dir="$(mktemp -d)"
  # Copy whatever the link still resolves to (empty if the ramdisk is gone).
  cp -a "${GWS_DIR}/." "${tmp_dir}/" 2>/dev/null || true
  rm "${GWS_DIR}"
  mkdir -p "${GWS_DIR}"
  cp -a "${tmp_dir}/." "${GWS_DIR}/" 2>/dev/null || true
  rm -rf "${tmp_dir}"
  chmod 700 "${GWS_DIR}"
  if compgen -G "${GWS_DIR}/credentials.*.enc" >/dev/null; then
    note "converted gws symlink to a real directory (state carried over)."
  else
    note "converted gws symlink to a real directory, but no auth state was recoverable — run config/scripts/setup-gws.sh to restore from Infisical."
  fi
  CHANGED=1
fi

# codex auth.json symlink → real file (codex layer is optional; no-op if absent).
CODEX_AUTH="${HOME}/.codex/auth.json"
if [[ -L "${CODEX_AUTH}" ]]; then
  target_content="$(cat "${CODEX_AUTH}" 2>/dev/null || true)"
  rm "${CODEX_AUTH}"
  if [[ -n "${target_content}" ]]; then
    printf '%s' "${target_content}" > "${CODEX_AUTH}"
    chmod 600 "${CODEX_AUTH}"
    note "converted ~/.codex/auth.json symlink to a real file."
  else
    note "removed dangling ~/.codex/auth.json symlink — re-run codex login (or restore from Infisical) when you next use codex."
  fi
  CHANGED=1
fi

# Any other state still on the ramdisk (qbo, custom layers): back it up before
# the eject so nothing is lost. The infisical/ dir (dead agent tokens) is skipped.
if mount | grep -q "on ${RAMDISK} "; then
  backup_root="${HOME}/Library/Application Support/wd-ramdisk-backup-${TS}"
  for d in "${RAMDISK}"/*/; do
    [[ -d "${d}" ]] || continue
    name="$(basename "${d}")"
    case "${name}" in
      infisical|gws) continue ;;   # infisical = dead tokens; gws handled above
    esac
    mkdir -p "${backup_root}"
    cp -a "${d}" "${backup_root}/${name}"
    note "backed up ramdisk ${name}/ to ${backup_root}/${name} — point that tool at an on-disk location and move the state there."
    CHANGED=1
  done
  [[ -d "${backup_root:-/nonexistent}" ]] && chmod -R go-rwx "${backup_root}"
fi

# ── 3. LaunchAgents ──────────────────────────────────────────────────────────
for label in com.benali.workdesk.infisical-agent com.benali.workdesk.ramdisk; do
  plist="${LA_DIR}/${label}.plist"
  if launchctl list 2>/dev/null | grep -q "${label}"; then
    launchctl bootout "gui/$(id -u)/${label}" 2>/dev/null \
      || launchctl unload "${plist}" 2>/dev/null || true
    note "unloaded LaunchAgent ${label}."
    CHANGED=1
  fi
  if [[ -f "${plist}" ]]; then
    rm "${plist}"
    note "removed ${plist}."
    CHANGED=1
  fi
done

# Belt and braces: kill any straggling agent process.
pkill -f "infisical agent --config" 2>/dev/null && { note "stopped running infisical agent process."; CHANGED=1; }

# ── 4. Eject the ramdisk ─────────────────────────────────────────────────────
if mount | grep -q "on ${RAMDISK} "; then
  if hdiutil detach "${RAMDISK}" >/dev/null 2>&1; then
    note "ejected ${RAMDISK}."
  else
    note "WARNING: could not eject ${RAMDISK} (something may have files open) — eject manually with: hdiutil detach ${RAMDISK}"
  fi
  CHANGED=1
fi

# ── 5. Rendered agent config (generated file, not shipped) ───────────────────
if [[ -d "${WD}/infisical" ]]; then
  rm -rf "${WD}/infisical"
  note "removed generated ${WD}/infisical/ (agent.yaml + templates)."
  CHANGED=1
fi

if [[ "${CHANGED}" = "1" ]]; then
  cat <<EOF
retire-infisical-machine-identity: done. Two manual follow-ups:
  1. Run \`infisical login\` if you haven't — user sessions are now the only
     auth path (they expire every few weeks; re-login when fetches fail).
  2. Optional cleanup: delete the old Universal Auth machine identity in the
     Infisical dashboard (Access Control → Machine Identities) and its
     credentials in macOS Keychain (items 'infisical-ua-client-id' and
     'infisical-ua-client-secret').
EOF
else
  note "already on the user-login layout; nothing to do."
fi

exit 0
