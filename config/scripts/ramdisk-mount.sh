#!/usr/bin/env bash
# ramdisk-mount.sh — idempotent macOS RAM disk for secret materialization.
#
# Creates an APFS-formatted RAM disk at /Volumes/wd-ramdisk if one is not
# already mounted. Sized to 128 MB (262144 × 512-byte sectors) — secrets are
# small, headroom is for token caches.
#
# Called by:
#   - config/launchagents/com.benali.workdesk.ramdisk.plist (RunAtLoad at login)
#   - Manually:  bash config/scripts/ramdisk-mount.sh
#
# Exits 0 if the ramdisk is mounted (created here or already present),
# non-zero on hard failure.

set -euo pipefail

VOL_NAME="wd-ramdisk"
VOL_PATH="/Volumes/${VOL_NAME}"
SIZE_SECTORS=262144   # 128 MB

if [[ -d "${VOL_PATH}" ]] && mount | grep -q "on ${VOL_PATH} "; then
  echo "ramdisk already mounted at ${VOL_PATH}"
  exit 0
fi

DEV=$(hdiutil attach -nomount "ram://${SIZE_SECTORS}")
DEV=$(echo "${DEV}" | tr -d '[:space:]')

if [[ -z "${DEV}" ]]; then
  echo "ERROR: hdiutil attach returned empty device" >&2
  exit 1
fi

diskutil erasevolume APFS "${VOL_NAME}" "${DEV}" >/dev/null

# Lock down — only this user can read/write.
chmod 700 "${VOL_PATH}"

echo "ramdisk created: ${VOL_PATH} on ${DEV}"
