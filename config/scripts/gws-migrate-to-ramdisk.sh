#!/usr/bin/env bash
# gws-migrate-to-ramdisk.sh — replace ~/Library/Application Support/gws with a
# symlink to /Volumes/wd-ramdisk/gws so all gws state lives in RAM.
#
# Safe to re-run. On first run it backs up the existing dir to
# ~/Library/Application Support/gws.bak.<timestamp>/.
#
# DOES NOT push state to Infisical — that's gws-push-tokens-to-infisical.sh.
# Run that AFTER you've authenticated against the ramdisk for the first time.

set -euo pipefail

REAL_DIR="${HOME}/Library/Application Support/gws"
RAMDISK_DIR="/Volumes/wd-ramdisk/gws"
BACKUP="${HOME}/Library/Application Support/gws.bak.$(date +%Y%m%d-%H%M%S)"

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
