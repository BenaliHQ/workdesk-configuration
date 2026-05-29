#!/usr/bin/env bash
# check-wikilinks.sh — scan markdown files for broken references.
#
# Scans the given files or directories for references to vault notes and
# reports any whose target does not exist. Two reference types are checked:
#
#   1. [[wikilinks]] (standard Obsidian shape)
#      Skips:
#        - Wikilinks inside fenced code blocks (``` ... ```)
#        - Wikilinks inside inline code spans (single backticks)
#        - Template patterns containing { or }
#        - Ellipsis placeholders [[...]]
#        - File embeds with media extensions ([[image.png]], [[doc.pdf]], etc.)
#      Handles aliases [[note|display]], header refs [[note#heading]], and
#      path-based wikilinks [[atlas/people/slug]] (resolved by basename, per
#      Obsidian).
#
#   2. Inbox-style backtick references: `[ACTION] slug`, `[REVIEW] slug`,
#      `[CONTENT] slug`, `[QUESTION] slug`, `[AWARENESS] slug`.
#      These are the inline references commonly used in meeting bodies,
#      decision notes, and status updates pointing at items in gtd/inbox/.
#      The reference resolves if a file with the same name (plus .md) exists
#      in the vault. Strips an optional trailing .md from the reference
#      before lookup.
#
# Default-excluded paths (treated as non-living-content):
#   - */_archive/*
#   - */defaults/*
#   - */config/source/*           (install snapshot)
#   - */vendor/*                  (third-party plugins)
#   - */node_modules/*
#   - */.git/*
#   - */system/session-log/*      (historical session captures, write-once)
#   - */system/transcripts/*      (raw inputs, write-once)
#
# Usage:
#   bash config/scripts/check-wikilinks.sh [-q|--quiet] <file-or-dir> [<file-or-dir> ...]
#
# Options:
#   -q, --quiet    Only output broken links; suppress the scan summary
#   -h, --help     Show this help
#
# Exit codes:
#   0 — all references resolve to existing notes (or no references found)
#   1 — at least one broken reference found
#   2 — bad input (no args, or unknown flag)
#
# Per [[instance-scaffolding]] and [[double-entry-knowledge]] — broken
# wikilinks are worse than plain text. Run this script after instance
# scaffolding, after legacy carry-forward, or as part of vault health checks.

set -u

QUIET=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    -q|--quiet)
      QUIET=1
      shift
      ;;
    -h|--help)
      sed -n '2,38p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    --)
      shift
      break
      ;;
    -*)
      echo "Unknown flag: $1" >&2
      exit 2
      ;;
    *)
      break
      ;;
  esac
done

if [[ $# -eq 0 ]]; then
  echo "Usage: $0 [-q|--quiet] <file-or-dir> [<file-or-dir> ...]" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

NOTES_FILE="$(mktemp)"
FOLDERS_FILE="$(mktemp)"
FILES_FILE="$(mktemp)"
trap 'rm -f "$NOTES_FILE" "$FOLDERS_FILE" "$FILES_FILE"' EXIT

EXCLUDE_ARGS=(
  -not -path '*_archive/*'
  -not -path '*defaults/*'
  -not -path '*config/source/*'
  -not -path '*vendor/*'
  -not -path '*node_modules/*'
  -not -path '*.git/*'
  -not -path '*system/session-log/*'
  -not -path '*system/transcripts/*'
  -not -path '*.workdesk-backups/*'
)

# Note basenames (markdown files in operator content)
find "$VAULT_ROOT" -type f -name '*.md' "${EXCLUDE_ARGS[@]}" \
  -exec basename {} .md \; | sort -u > "$NOTES_FILE"

# Folder basenames — Obsidian folder-note convention
find "$VAULT_ROOT" -type d "${EXCLUDE_ARGS[@]}" \
  -not -path '*/_archive' \
  -not -path '*/defaults' \
  -not -path '*/config/source' \
  -not -path '*/vendor' \
  -not -path '*/node_modules' \
  -not -path '*/.git' \
  -exec basename {} \; | sort -u > "$FOLDERS_FILE"

# Collect files to scan
: > "$FILES_FILE"
for target in "$@"; do
  if [[ -d "$target" ]]; then
    find "$target" -type f -name '*.md' "${EXCLUDE_ARGS[@]}" | sort >> "$FILES_FILE"
  elif [[ -f "$target" ]]; then
    # Only scan markdown files. Non-.md inputs (e.g., shell scripts) contain
    # syntax that overlaps with wikilink patterns (`[[ -f ... ]]` bash tests,
    # documentation comments with illustrative `[[wikilink]]` examples) and
    # produce noise.
    case "$target" in
      *.md) echo "$target" >> "$FILES_FILE" ;;
      *)    echo "Skipping $target (not a .md file)" >&2 ;;
    esac
  else
    echo "Skipping $target (not a file or directory)" >&2
  fi
done

if [[ ! -s "$FILES_FILE" ]]; then
  if [[ $QUIET -eq 0 ]]; then
    echo "Scanned 0 references; 0 broken."
  fi
  exit 0
fi

# Read filenames into an array using newline as the only separator so that
# filenames containing spaces, brackets ([ACTION] foo.md), and other special
# shell metacharacters survive. Replaces the earlier $(cat "$FILES_FILE")
# pattern which broke awk's positional args on any non-shell-safe name.
SCAN_FILES=()
while IFS= read -r f; do
  [[ -n "$f" ]] && SCAN_FILES+=("$f")
done < "$FILES_FILE"

awk -v notes_file="$NOTES_FILE" \
    -v folders_file="$FOLDERS_FILE" \
    -v vault_root="$VAULT_ROOT" \
    -v quiet="$QUIET" '
BEGIN {
  while ((getline line < notes_file) > 0) valid[line] = 1
  close(notes_file)
  while ((getline line < folders_file) > 0) valid[line] = 1
  close(folders_file)
  in_fence = 0
  total = 0
  broken = 0
  prev_file = ""
  vault_prefix = vault_root "/"
  vault_prefix_len = length(vault_prefix)
}

# Reset fence state when entering a new file
FNR == 1 {
  in_fence = 0
  prev_file = FILENAME
  rel_file = FILENAME
  if (substr(rel_file, 1, vault_prefix_len) == vault_prefix) {
    rel_file = substr(rel_file, vault_prefix_len + 1)
  }
}

# Toggle fenced code block
/^[[:space:]]*```/ {
  in_fence = 1 - in_fence
  next
}

in_fence == 1 { next }

{
  original = $0

  # --- Pass 1: inbox-style backtick references --------------------------
  # Pattern: `[PREFIX] anything-up-to-closing-backtick`
  # PREFIX is one of the documented inbox prefixes. Reference resolves if a
  # vault note exists with the same basename (optionally minus trailing .md).
  #
  # Documentation examples like `` `[ACTION] foo` `` (double-backtick wrap
  # used to render a literal single-backtick span in markdown) must be
  # skipped. We strip double-backtick spans first, then scan for real refs.
  ref_line = original
  # Strip double-backtick documentation spans. Pattern: `` content ``
  # where content may contain single backticks. Matches `` …`x`… `` with
  # at most one inner backtick pair (the typical doc shape). Repeat-applied
  # to handle multiple doc spans on one line.
  while (match(ref_line, /``[^`]*`[^`]*`[^`]*``/)) {
    ref_line = substr(ref_line, 1, RSTART - 1) substr(ref_line, RSTART + RLENGTH)
  }

  while (match(ref_line, /`\[(ACTION|REVIEW|CONTENT|QUESTION|AWARENESS)\][[:space:]]+[^`]+`/)) {
    full_match = substr(ref_line, RSTART, RLENGTH)
    ref_line = substr(ref_line, RSTART + RLENGTH)

    # Strip the outer backticks
    inner = substr(full_match, 2, length(full_match) - 2)

    # Tolerate trailing .md
    sub(/\.md$/, "", inner)

    total++

    if (!(inner in valid)) {
      print "BROKEN: " rel_file " → " full_match
      broken++
    }
  }

  # --- Pass 2: standard [[wikilinks]] -----------------------------------
  line = original
  # Strip inline code spans (single-backtick pairs on same line) so that
  # illustrative `[[wikilink]]` patterns in documentation are not scanned.
  gsub(/`[^`]*`/, "", line)
  while (match(line, /\[\[[^]]+\]\]/)) {
    full_match = substr(line, RSTART, RLENGTH)
    inner = substr(line, RSTART + 2, RLENGTH - 4)
    line = substr(line, RSTART + RLENGTH)

    # Skip template patterns
    if (inner ~ /[{}]/) continue
    # Skip ellipsis placeholders
    if (inner ~ /\.\.\./) continue
    # Skip media embeds
    if (inner ~ /\.(png|jpg|jpeg|gif|svg|webp|pdf|mp3|mp4|ogg|wav|webm)([|#]|$)/) continue

    total++

    # Unescape \| used inside Obsidian table cells. Aliased wikilinks in
    # tables use [[note\|Alias]] to keep the pipe from being parsed as a
    # cell delimiter. Without this fix, split below leaves a trailing
    # backslash on the target and the lookup fails.
    gsub(/\\[|]/, "|", inner)
    # Strip alias (|...) and header (#...)
    n = split(inner, parts, /[|#]/)
    target = parts[1]
    # Strip path prefix
    sub(/^.*\//, "", target)

    if (target == "") continue

    if (!(target in valid)) {
      print "BROKEN: " rel_file " → " full_match
      broken++
    }
  }
}

END {
  if (!quiet) {
    print ""
    print "Scanned " total " references; " broken " broken."
  }
  exit (broken > 0 ? 1 : 0)
}
' "${SCAN_FILES[@]}"
