#!/usr/bin/env bash
# session-end-session-dump.sh
#
# SessionEnd hook. Exports the Claude Code transcript JSONL to a raw
# markdown file in system/session-log/{date}-{time}-{session_id}-raw.md.
#
# /extract --summarize {raw-file} produces the final summarized note.
# This hook does NOT summarize — it only exports.

set -euo pipefail
IFS=$'\n\t'

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
JSON_GET="$DIR/json-get.sh"
VAULT="${CLAUDE_PROJECT_DIR:-$(cd "$DIR/../.." && pwd)}"
# Nested projects inherit the containing vault. Preserve explicit standalone
# scratch roots used by the hook benchmark and isolated runtime probes.
VAULT_CANDIDATE="$VAULT"
while [[ "$VAULT_CANDIDATE" != / && ! -f "$VAULT_CANDIDATE/config/scripts/json-get.sh" ]]; do
  VAULT_CANDIDATE="$(dirname "$VAULT_CANDIDATE")"
done
if [[ -f "$VAULT_CANDIDATE/config/scripts/json-get.sh" ]]; then
  VAULT="$VAULT_CANDIDATE"
fi
LOG_DIR="$VAULT/system/session-log"

input="$(cat)"
session_id=$(printf '%s' "$input" | "$JSON_GET" session_id 2>/dev/null || true)
transcript=$(printf '%s' "$input" | "$JSON_GET" transcript_path 2>/dev/null || true)

[[ -z "$session_id" ]] && session_id="unknown"
[[ -z "$transcript" || ! -f "$transcript" ]] && exit 0

# Defense in depth before these values land in YAML frontmatter or the
# file path: strip control chars and quote characters that would forge
# additional frontmatter entries when interpolated unescaped.
yaml_safe() {
  printf '%s' "$1" | LC_ALL=C tr -d '\000-\037\177"'
}
session_id=$(yaml_safe "$session_id")
transcript_safe=$(yaml_safe "$transcript")
# Filename component cannot contain slashes or quotes either.
session_id_fname=$(printf '%s' "$session_id" | LC_ALL=C tr -d '/\\')

mkdir -p "$LOG_DIR"
ts=$(date '+%Y-%m-%d-%H-%M')
out="$LOG_DIR/${ts}-${session_id_fname}-raw.md"

{
  echo "---"
  echo "type: source"
  echo "source-kind: session-log"
  echo "date: $(date '+%Y-%m-%d')"
  echo "session-id: $session_id"
  echo "transcript-path: \"$transcript_safe\""
  echo "processed: false"
  echo "summarized: false"
  echo "complete: true"
  echo "---"
  echo ""
  echo "# Conversation"
  echo ""
  # M3: parse the JSONL transcript with python's json module rather than
  # regex/awk. Each line is a JSON object; we extract role + the
  # concatenated text of any string content blocks. Malformed lines are
  # skipped silently — the engine should never lose a session over a
  # single bad line.
  TRANSCRIPT="$transcript" /usr/bin/python3 - <<'PY'
import json, os, sys

path = os.environ["TRANSCRIPT"]
last_role = None
try:
    f = open(path, "r", encoding="utf-8", errors="replace")
except OSError:
    sys.exit(0)

with f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        # A line may legitimately decode to a scalar or list — only
        # dicts carry messages we care about.
        if not isinstance(obj, dict):
            continue

        # Claude Code transcript shape: {"message": {"role": ..., "content": ...}}
        # plus older flat shapes {"role": ..., "content": ...}. Tolerate both.
        msg = obj.get("message") if isinstance(obj.get("message"), dict) else obj
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue

        content = msg.get("content")
        chunks = []
        if isinstance(content, str):
            chunks.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    t = block.get("text")
                    if isinstance(t, str):
                        chunks.append(t)
                elif isinstance(block, str):
                    chunks.append(block)
        text = "\n".join(c for c in chunks if c).strip()
        if not text:
            continue

        if role != last_role:
            print(f"## {role.capitalize()}\n")
            last_role = role
        print(text)
        print()
PY
} > "$out" 2>/dev/null

exit 0
