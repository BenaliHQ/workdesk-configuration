#!/usr/bin/env bash
# release.sh — build and publish a WorkDesk OS release.
#
# Reads version from config/VERSION, builds a tarball with this layout:
#
#   workdesk/        (snapshot of config/, excluding defaults/, state/, snapshots/)
#   manifest.json    ({"version": "1.3.0", "migrations": ["script.sh", ...]})
#   migrations/      (the actual scripts, copied from repo migrations/ dir)
#
# Then writes a SHA256 sidecar and creates a GitHub release with both files
# attached, via `gh release create`.
#
# Usage:
#   scripts/release.sh                    # build + publish
#   scripts/release.sh --dry-run          # build only; no upload
#   scripts/release.sh --notes-file FILE  # use FILE as release notes (default: auto)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DRY_RUN=0
NOTES_FILE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)    DRY_RUN=1; shift ;;
    --notes-file) NOTES_FILE="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

[[ -f "config/VERSION" ]] || { echo "Missing config/VERSION" >&2; exit 1; }
VERSION="$(head -n 1 config/VERSION | tr -d '[:space:]')"
TAG="v$VERSION"
TARBALL_NAME="workdesk-os-${VERSION}.tar.gz"

if (( DRY_RUN == 0 )); then
  command -v gh >/dev/null || { echo "gh CLI required" >&2; exit 1; }
  if gh release view "$TAG" >/dev/null 2>&1; then
    echo "Release $TAG already exists. Bump config/VERSION first." >&2
    exit 1
  fi
fi

# Stage the release tree in a temp dir.
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE/workdesk"

# Copy config/ into staging, excluding what shouldn't ship.
rsync -a \
  --exclude='defaults/' \
  --exclude='state/' \
  --exclude='snapshots/' \
  --exclude='.DS_Store' \
  config/ "$STAGE/workdesk/"

# Migrations: if migrations/ exists at repo root, copy and list scripts in
# lexicographic order. Manifest is JSON so the runtime has one structured
# source of truth for release metadata.
MIGS_JSON="[]"
if [[ -d "migrations" ]]; then
  mkdir -p "$STAGE/migrations"
  shopt -s nullglob
  declare -a migs=()
  for f in migrations/*.sh; do
    cp "$f" "$STAGE/migrations/"
    migs+=("$(basename "$f")")
  done
  shopt -u nullglob
  if (( ${#migs[@]} > 0 )); then
    MIGS_JSON=$(printf '%s\n' "${migs[@]}" | LC_ALL=C sort \
      | python3 -c "import json,sys; print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))")
  fi
fi

python3 -c "
import json
print(json.dumps({'version': '$VERSION', 'migrations': $MIGS_JSON}, indent=2))
" > "$STAGE/manifest.json"

# Build the tarball with mode bits and symlinks preserved.
DIST="$REPO_ROOT/dist"
mkdir -p "$DIST"
TARBALL="$DIST/$TARBALL_NAME"
tar -czpf "$TARBALL" -C "$STAGE" .

# SHA256 sidecar.
SHA_FILE="$TARBALL.sha256"
( cd "$DIST" && shasum -a 256 "$TARBALL_NAME" > "$TARBALL_NAME.sha256" )

echo "Built: $TARBALL"
echo "       $SHA_FILE"
echo "       sha256: $(awk '{print $1}' "$SHA_FILE")"

if (( DRY_RUN )); then
  echo "Dry-run; skipping gh release create."
  exit 0
fi

# Notes: use --generate-notes if no file provided.
GH_ARGS=(release create "$TAG" "$TARBALL" "$SHA_FILE" --title "WorkDesk OS $TAG")
if [[ -n "$NOTES_FILE" ]]; then
  GH_ARGS+=(--notes-file "$NOTES_FILE")
else
  GH_ARGS+=(--generate-notes)
fi

gh "${GH_ARGS[@]}"
echo "Released: https://github.com/BenaliHQ/workdesk-configuration/releases/tag/$TAG"
