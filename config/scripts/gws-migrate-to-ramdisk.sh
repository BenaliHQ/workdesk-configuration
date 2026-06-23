#!/usr/bin/env bash
# gws-migrate-to-ramdisk.sh — replace gws's real data dir with a symlink to
# /Volumes/wd-ramdisk/gws so all gws state lives in RAM.
#
# Safe to re-run. On first run it backs up the existing dir alongside itself as
# <data-dir>.bak.<timestamp>/.
#
# DOES NOT push state to Infisical — that's gws-push-tokens-to-infisical.sh.
# Run that AFTER you've authenticated against the ramdisk for the first time.
#
# gws's data dir is NOT hardcoded: older builds used
# ~/Library/Application Support/gws, but current googleworkspace-cli (≥0.22.5)
# uses the XDG path ~/.config/gws. We ask gws where it actually keeps state
# (via `gws auth status`) so the symlink lands on the dir gws really reads —
# symlinking the wrong dir leaves real creds on the SSD and the ramdisk orphaned.

set -euo pipefail

# Resolve gws's real data dir. Prefer what gws reports; fall back to an existing
# dir; default to the XDG path used by current builds.
detect_gws_dir() {
  local cfg
  cfg=$(gws auth status 2>/dev/null | sed -nE 's/.*"client_config":[[:space:]]*"([^"]+)".*/\1/p' | head -1)
  if [[ -n "${cfg}" ]]; then
    dirname "${cfg}"
  elif [[ -d "${HOME}/.config/gws" ]]; then
    echo "${HOME}/.config/gws"
  elif [[ -d "${HOME}/Library/Application Support/gws" ]]; then
    echo "${HOME}/Library/Application Support/gws"
  else
    echo "${HOME}/.config/gws"
  fi
}

REAL_DIR="$(detect_gws_dir)"
RAMDISK_DIR="/Volumes/wd-ramdisk/gws"
BACKUP="${REAL_DIR}.bak.$(date +%Y%m%d-%H%M%S)"

if ! mount | grep -q "on /Volumes/wd-ramdisk "; then
  echo "ERROR: ramdisk not mounted. Run config/scripts/ramdisk-mount.sh first." >&2
  exit 1
fi

mkdir -p "${RAMDISK_DIR}"
chmod 700 "${RAMDISK_DIR}"

if [[ -L "${REAL_DIR}" ]]; then
  TARGET=$(readlink "${REAL_DIR}")
  if [[ "${TARGET}" = "${RAMDISK_DIR}" ]]; then
    echo "already symlinked: ${REAL_DIR} -> ${TARGET}"
    exit 0
  fi
  echo "ERROR: ${REAL_DIR} is a symlink to ${TARGET} — refusing to overwrite." >&2
  exit 1
fi

if [[ -d "${REAL_DIR}" ]]; then
  echo "backing up ${REAL_DIR} -> ${BACKUP}"
  mv "${REAL_DIR}" "${BACKUP}"
  echo "copying contents of backup into ramdisk so existing auth survives this run"
  cp -a "${BACKUP}/." "${RAMDISK_DIR}/"
fi

ln -s "${RAMDISK_DIR}" "${REAL_DIR}"
echo "symlink in place: ${REAL_DIR} -> ${RAMDISK_DIR}"

if [[ -d "${BACKUP}" ]]; then
  echo
  echo "NOTE: backup at ${BACKUP} still exists on disk."
  echo "Once you've verified gws works against the ramdisk AND pushed tokens to"
  echo "Infisical via gws-push-tokens-to-infisical.sh, scrub it with:"
  echo "  rm -rf \"${BACKUP}\""
fi
