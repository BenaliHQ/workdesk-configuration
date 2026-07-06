#!/usr/bin/env bash
# extract-transcript-gemini.sh — Pure ETL: send one intake transcript MD to
# Gemini 3.1 Flash Lite with a strict JSON schema, return structured output.
#
# This is the extraction step of /process-transcripts.  Heavy compute lives
# here (Gemini, ~$0.001-0.002 per transcript) so Claude can stay focused on
# vault integration: wikilink resolution, matching cross-updates, file ops.
#
# Pure ETL discipline:
#   - One transcript in, one JSON out (stdout).
#   - No vault writes.  No state files.  Caller owns those.
#   - Errors go to stderr + non-zero exit.
#
# Usage:
#   bash config/scripts/extract-transcript-gemini.sh <transcript-path> [--model <id>]
#
# Exit codes:
#   0  success — valid JSON on stdout
#   1  Gemini API returned an error (rate limit, malformed request, etc.)
#   2  hard failure (auth, bad args, transcript not readable)
#   3  Gemini returned output that doesn't parse as JSON

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
SKILL_DIR="$VAULT_ROOT/.claude/skills/process-transcripts"
PROMPT_FILE="$SKILL_DIR/prompt.txt"
SCHEMA_FILE="$SKILL_DIR/schema.json"
PERSONAL_PROJ_ID="df755029-00a8-4374-b195-43eeb3268430"

MODEL="gemini-3.1-flash-lite"
TRANSCRIPT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model) MODEL="$2"; shift 2 ;;
    --help|-h)
      sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) TRANSCRIPT="$1"; shift ;;
  esac
done

if [[ -z "$TRANSCRIPT" || ! -r "$TRANSCRIPT" ]]; then
  echo "ERROR: transcript not readable: $TRANSCRIPT" >&2
  exit 2
fi
if [[ ! -r "$PROMPT_FILE" ]]; then
  echo "ERROR: prompt missing: $PROMPT_FILE" >&2
  exit 2
fi
if [[ ! -r "$SCHEMA_FILE" ]]; then
  echo "ERROR: schema missing: $SCHEMA_FILE" >&2
  exit 2
fi

# Auth: the operator's `infisical login` user session (or an INFISICAL_TOKEN
# already exported by the caller). </dev/null on the fetch below keeps the CLI
# from dropping into its interactive wizard in non-interactive contexts
# (cron, agents) — it fails fast instead, and the error path says to re-login.

GEMINI_API_KEY="$(infisical secrets get PERSONAL_GEMINI_API_KEY \
  --projectId="$PERSONAL_PROJ_ID" --env=prod --plain </dev/null 2>/dev/null)"
if [[ -z "$GEMINI_API_KEY" || "${GEMINI_API_KEY:0:6}" != "AIzaSy" ]]; then
  echo "ERROR: PERSONAL_GEMINI_API_KEY not in Infisical (or wrong shape) — run 'infisical login' (user sessions expire every few weeks)" >&2
  exit 2
fi

# Read prompt + schema + transcript body (skip frontmatter)
PROMPT_BODY="$(cat "$PROMPT_FILE")"
SCHEMA_BODY="$(cat "$SCHEMA_FILE")"
TRANSCRIPT_BODY="$(awk '/^---$/{c++; next} c>=2 {print}' "$TRANSCRIPT")"

if [[ -z "$TRANSCRIPT_BODY" ]]; then
  echo "ERROR: transcript body is empty (no content after frontmatter)" >&2
  exit 2
fi

# Build request
REQUEST=$(jq -n \
  --arg prompt "$PROMPT_BODY" \
  --arg transcript "$TRANSCRIPT_BODY" \
  --argjson schema "$SCHEMA_BODY" \
  '{
    contents: [{
      parts: [{ text: ($prompt + "\n\n" + $transcript) }]
    }],
    generationConfig: {
      responseMimeType: "application/json",
      responseSchema: $schema,
      temperature: 0.2,
      maxOutputTokens: 8192
    }
  }')

# Call Gemini
RESPONSE_FILE="$(mktemp)"
trap 'rm -f "$RESPONSE_FILE"' EXIT

HTTP_CODE=$(curl -sS -o "$RESPONSE_FILE" -w '%{http_code}' \
  "https://generativelanguage.googleapis.com/v1beta/models/$MODEL:generateContent?key=$GEMINI_API_KEY" \
  -H 'Content-Type: application/json' \
  -d "$REQUEST")

if [[ "$HTTP_CODE" != "200" ]]; then
  echo "ERROR: Gemini HTTP $HTTP_CODE" >&2
  jq '.error // .' "$RESPONSE_FILE" >&2 2>/dev/null || cat "$RESPONSE_FILE" >&2
  exit 1
fi

# Check API-level error in body
if jq -e '.error' "$RESPONSE_FILE" >/dev/null 2>&1; then
  echo "ERROR: Gemini API error" >&2
  jq '.error' "$RESPONSE_FILE" >&2
  exit 1
fi

# Extract structured text from the candidate
EXTRACTED="$(jq -r '.candidates[0].content.parts[0].text' "$RESPONSE_FILE")"

# Validate JSON parse
if ! echo "$EXTRACTED" | jq empty 2>/dev/null; then
  echo "ERROR: Gemini output failed JSON parse" >&2
  echo "--- raw output (first 1KB): ---" >&2
  echo "$EXTRACTED" | head -c 1024 >&2
  echo >&2
  exit 3
fi

# Emit token usage to stderr so caller can log it without polluting JSON stdout
jq -c '.usageMetadata // {} | {prompt: .promptTokenCount, output: .candidatesTokenCount, total: .totalTokenCount}' "$RESPONSE_FILE" >&2

# JSON to stdout
echo "$EXTRACTED"
