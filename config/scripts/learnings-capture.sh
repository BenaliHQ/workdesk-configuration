#!/usr/bin/env bash
# learnings-capture.sh — record an operator correction so it survives the session.
#
# The write half of the co-evolution loop (see config/rules/claude-md-coevolution.md).
# Claude calls this the moment the operator corrects something: a voice preference,
# a process rule, a tool gotcha. Without it, corrections live only in the session
# transcript and have to be rediscovered.
#
# Every correction lands in the skill's own learnings.md, which is what
# learnings-scan.sh reads when looking for the same correction showing up across
# two or more skills. Corrections tagged STYLE are ALSO appended to
# config/rules/writing-style.md, per the contract in that rule.
#
# Usage:
#   learnings-capture.sh --skill <slug> --tag <TAG> --text "the correction"
#   learnings-capture.sh --skill daily-ops --tag PROCESS --text "check project status before planning"
#
# Tags:
#   STYLE    voice / wording / formatting preference   (also → writing-style.md)
#   PROCESS  workflow or sequencing correction
#   TOOL     tool behaviour, flag shape, gotcha
#   FACT     a factual correction about the operator's world
#   OTHER    anything else
#
# Exit codes:
#   0 — captured
#   2 — bad usage

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT="${CLAUDE_PROJECT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"

SKILL=""
TAG="OTHER"
TEXT=""

usage() {
  sed -n '3,28p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
  exit 2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skill) SKILL="${2:-}"; shift 2 ;;
    --tag)   TAG="${2:-}";   shift 2 ;;
    --text)  TEXT="${2:-}";  shift 2 ;;
    -h|--help) usage ;;
    *) echo "learnings-capture: unknown argument '$1'" >&2; usage ;;
  esac
done

[[ -n "$SKILL" ]] || { echo "learnings-capture: --skill is required" >&2; exit 2; }
[[ -n "$TEXT"  ]] || { echo "learnings-capture: --text is required"  >&2; exit 2; }

case "$TAG" in
  STYLE|PROCESS|TOOL|FACT|OTHER) ;;
  *) echo "learnings-capture: --tag must be STYLE, PROCESS, TOOL, FACT, or OTHER" >&2; exit 2 ;;
esac

SKILL_DIR="$VAULT/config/skills/$SKILL"
if [[ ! -d "$SKILL_DIR" ]]; then
  echo "learnings-capture: no such skill '$SKILL' (looked in config/skills/)" >&2
  exit 2
fi

TODAY="$(date '+%Y-%m-%d')"
LEARNINGS="$SKILL_DIR/learnings.md"

# Seed the file on first capture.
if [[ ! -f "$LEARNINGS" ]]; then
  cat > "$LEARNINGS" <<EOF
---
type: skill-learnings
skill: $SKILL
---

# Learnings — /$SKILL

Operator corrections captured during real runs of this skill. Appended by
\`config/scripts/learnings-capture.sh\`. Scanned for cross-skill repeats by
\`config/scripts/learnings-scan.sh\` per [[claude-md-coevolution]] — when the same
correction lands in two or more skills within 30 days, it gets proposed for
promotion to a rule.

## Entries

EOF
fi

# One line per correction: date, tag, text. Format is load-bearing —
# learnings-scan.sh parses it.
printf -- '- %s `[%s]` %s\n' "$TODAY" "$TAG" "$TEXT" >> "$LEARNINGS"
echo "learnings-capture: recorded [$TAG] on /$SKILL"

# STYLE corrections also belong in the operator's own writing-style rule,
# per its documented contract. That file is operator-owned and never shipped,
# so it may not exist in a fresh vault — skip quietly if absent.
if [[ "$TAG" == "STYLE" ]]; then
  STYLE_RULE="$VAULT/config/rules/writing-style.md"
  if [[ -f "$STYLE_RULE" ]]; then
    python3 - "$STYLE_RULE" "$TODAY" "$TEXT" "$SKILL" <<'PY'
import sys

path, today, text, skill = sys.argv[1:5]
entry = f"- `[STYLE]` ({today}, from /{skill}) {text}\n"
lines = open(path, encoding="utf-8").read().splitlines(keepends=True)

heading = "## Words and phrases to avoid\n"
if heading not in lines:
    # Section missing (operator restructured the file) — append at the end.
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"\n{heading}\n{entry}")
    print("learnings-capture: appended [STYLE] to writing-style.md (new section)")
    raise SystemExit

idx = lines.index(heading) + 1
# Walk to the end of the section, then back up past trailing blanks so the
# entry sits directly under the last bullet rather than after a gap.
end = idx
while end < len(lines) and not lines[end].startswith("## "):
    end += 1
insert = end
while insert > idx and lines[insert - 1].strip() == "":
    insert -= 1

lines.insert(insert, entry)
open(path, "w", encoding="utf-8").writelines(lines)
print("learnings-capture: appended [STYLE] to writing-style.md")
PY
  else
    echo "learnings-capture: writing-style.md absent; [STYLE] entry kept on /$SKILL only" >&2
  fi
fi

exit 0
