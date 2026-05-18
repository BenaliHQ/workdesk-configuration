#!/usr/bin/env bash
# regenerate-brat-fixture.sh — generate vendor/plugins/obsidian42-brat/data.json.fixture
#
# Per [[specs/workdesk-init]] r4.1 §BRAT data.json. Run when bumping the
# vendored BRAT version, then commit the new fixture.
#
# Two paths to a fixture, attempted in order:
#
#   PATH 1 — Real launch (spec letter):
#     Spin up a clean test vault with vendored BRAT pre-installed, launch
#     Obsidian, you click "Trust author and enable plugins", BRAT writes its
#     default data.json on first save, you quit. Script captures and overrides
#     pluginList + pluginSubListFrozenVersion.
#
#   PATH 2 — Bundle extraction (fallback):
#     If BRAT didn't persist a data.json after the launch (its onload pattern
#     `Object.assign({}, je, await this.loadData())` only writes via
#     saveSettings, which most plugins only call after a user setting change),
#     we extract the `je` defaults literal directly from the vendored main.js
#     and synthesize the equivalent fixture.
#
# Bundle extraction is strictly more rigorous than launch capture for the
# stated goal (defending against missing-default-keys upstream may add):
# `je` is read from the exact bundle being shipped, with zero UI/timing
# variability. Surfacing as a candidate spec amendment.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BRAT_DIR="$REPO_ROOT/vendor/plugins/obsidian42-brat"
FIXTURE="$BRAT_DIR/data.json.fixture"

step() { printf '\n[step] %s\n' "$*"; }
note() { printf '       %s\n' "$*"; }
fail() { printf '\n[ERROR] %s\n' "$*" >&2; }

if ! [[ -f "$BRAT_DIR/main.js" && -f "$BRAT_DIR/manifest.json" ]]; then
  fail "$BRAT_DIR is missing main.js or manifest.json. Run scripts/refresh-vendored-plugins.sh first."
  exit 1
fi

BRAT_VERSION=$(plutil -extract version raw "$BRAT_DIR/manifest.json")
step "Vendored BRAT version: $BRAT_VERSION"

if pgrep -x Obsidian >/dev/null; then
  fail "Obsidian is running. Quit it before regenerating the fixture."
  exit 1
fi

REGISTRY="$HOME/Library/Application Support/obsidian/obsidian.json"
REGISTRY_BACKUP="/tmp/obsidian.json.brat-fixture.bak.$$"
if [[ -f "$REGISTRY" ]]; then
  cp "$REGISTRY" "$REGISTRY_BACKUP"
  step "Backed up registry to $REGISTRY_BACKUP"
fi

TMPVAULT="/tmp/workdesk-brat-fixture-vault-$$"

dump_diagnostics() {
  printf '\n========== DIAGNOSTICS ==========\n'
  printf '\n--- temp vault tree ---\n'
  find "$TMPVAULT" -type f 2>/dev/null | sort
  printf '\n--- .obsidian/plugins/obsidian42-brat contents ---\n'
  ls -la "$TMPVAULT/.obsidian/plugins/obsidian42-brat/" 2>/dev/null || echo "(missing)"
  printf '\n--- data.json (if present) ---\n'
  if [[ -f "$TMPVAULT/.obsidian/plugins/obsidian42-brat/data.json" ]]; then
    cat "$TMPVAULT/.obsidian/plugins/obsidian42-brat/data.json"
  else
    echo "(not written by BRAT)"
  fi
  printf '\n--- community-plugins.json ---\n'
  cat "$TMPVAULT/.obsidian/community-plugins.json" 2>/dev/null || echo "(missing)"
  printf '\n--- workspace.json (created? indicates Obsidian fully loaded) ---\n'
  ls -la "$TMPVAULT/.obsidian/workspace.json" 2>/dev/null || echo "(missing — Obsidian may not have fully loaded the vault)"
  printf '\n--- app.json on disk ---\n'
  cat "$TMPVAULT/.obsidian/app.json" 2>/dev/null || echo "(missing)"
  printf '\n=================================\n\n'
}

WORK=""
cleanup() {
  EXIT_CODE=$?
  if [[ $EXIT_CODE -ne 0 ]]; then
    dump_diagnostics
  fi
  [[ -n "$WORK" && -f "$WORK" ]] && rm -f "$WORK"
  rm -rf "$TMPVAULT"
  if [[ -f "$REGISTRY_BACKUP" ]]; then
    cp "$REGISTRY_BACKUP" "$REGISTRY"
    rm -f "$REGISTRY_BACKUP"
    echo "[trap] Restored registry from backup."
  fi
}
trap cleanup EXIT

step "Setting up temp vault: $TMPVAULT"
mkdir -p "$TMPVAULT/.obsidian/plugins/obsidian42-brat"
cp "$BRAT_DIR/main.js" "$BRAT_DIR/manifest.json" "$TMPVAULT/.obsidian/plugins/obsidian42-brat/"
[[ -f "$BRAT_DIR/styles.css" ]] && cp "$BRAT_DIR/styles.css" "$TMPVAULT/.obsidian/plugins/obsidian42-brat/"

echo '["obsidian42-brat"]' > "$TMPVAULT/.obsidian/community-plugins.json"
cat > "$TMPVAULT/.obsidian/app.json" <<'JSON'
{
  "alwaysUpdateLinks": false,
  "newFileLocation": "root"
}
JSON
echo "# WorkDesk BRAT fixture vault" > "$TMPVAULT/README.md"

step "Registering temp vault in obsidian.json"
NEW_ID=$(openssl rand -hex 8)
NOW_MILLIS=$(($(date +%s) * 1000))

mkdir -p "$(dirname "$REGISTRY")"
if ! [[ -f "$REGISTRY" ]]; then
  echo '{"vaults":{}}' > "$REGISTRY"
fi

EXISTING_IDS=$(plutil -extract vaults json -o - "$REGISTRY" 2>/dev/null \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(" ".join(d.keys()))' 2>/dev/null || echo "")
for vid in $EXISTING_IDS; do
  plutil -remove "vaults.$vid.open" "$REGISTRY" 2>/dev/null || true
done

plutil -insert "vaults.$NEW_ID" -dictionary "$REGISTRY"
plutil -insert "vaults.$NEW_ID.path" -string "$TMPVAULT" "$REGISTRY"
plutil -insert "vaults.$NEW_ID.ts" -integer "$NOW_MILLIS" "$REGISTRY"
plutil -insert "vaults.$NEW_ID.open" -bool true "$REGISTRY"
plutil -p "$REGISTRY" >/dev/null
note "Registered with id $NEW_ID (open=true)"

cat <<EOF

============================================================
Launching Obsidian against the temp vault.

When Obsidian opens you'll see ONE of:
  (a) "Trust author and enable plugins?" → click TRUST.
  (b) Empty vault loads with BRAT disabled — ignore, quit anyway.
      The bundle-extraction fallback will produce the fixture.

OPTIONAL but improves PATH 1 success: open Obsidian's settings
(Cmd-,) → Community Plugins → BRAT → toggle any setting (then
toggle back). This forces BRAT.saveSettings() and writes data.json.

Wait ~5 seconds, then QUIT Obsidian (Cmd-Q).
============================================================

Press ENTER to launch.
EOF
read -r

step "Launching Obsidian"
open -a Obsidian

echo "Waiting up to 30s for Obsidian to start..."
for _ in {1..30}; do
  pgrep -x Obsidian >/dev/null && break
  sleep 1
done

if ! pgrep -x Obsidian >/dev/null; then
  fail "Obsidian did not start within 30s."
  exit 1
fi
note "Obsidian PID(s): $(pgrep -x Obsidian | tr '\n' ' ')"

echo "Waiting for you to Cmd-Q Obsidian..."
while pgrep -x Obsidian >/dev/null; do sleep 1; done
step "Obsidian quit"

DATA_JSON="$TMPVAULT/.obsidian/plugins/obsidian42-brat/data.json"
WORKSPACE_JSON="$TMPVAULT/.obsidian/workspace.json"

# Confirm Obsidian fully loaded the vault — workspace.json is written even if BRAT didn't save.
if ! [[ -f "$WORKSPACE_JSON" ]]; then
  fail "Obsidian did not appear to fully load the vault (no workspace.json). It may have opened a different vault. Re-check the registry registration."
  exit 1
fi
note "workspace.json present — Obsidian loaded the temp vault."

WORK="$BRAT_DIR/.data.json.work.$$"

if [[ -f "$DATA_JSON" ]]; then
  step "PATH 1 success — BRAT wrote data.json"
  cat "$DATA_JSON"
  cp "$DATA_JSON" "$WORK"
else
  step "PATH 1 did not yield data.json — falling back to bundle extraction"
  note "Extracting 'je' defaults literal from vendored main.js"

  # Pull the literal: var je={...}
  JE_LITERAL=$(grep -oE 'var je=\{[^}]+\}' "$BRAT_DIR/main.js" | head -1 | sed 's/^var je=//')
  if [[ -z "$JE_LITERAL" ]]; then
    fail "Could not locate 'je' defaults literal in $BRAT_DIR/main.js. BRAT bundle structure may have changed; inspect manually."
    exit 1
  fi
  note "Raw je literal:"
  printf '       %s\n' "$JE_LITERAL"

  # Convert JS object literal → strict JSON.
  # je uses unquoted keys, !0/!1 booleans, and JS string escaping (which is
  # JSON-compatible for these defaults — only string values present are
  # ASCII without backslashes). Transformations:
  #   1. !0 → true, !1 → false
  #   2. Quote unquoted keys: {key: → {"key":  and ,key: → ,"key":
  JSON_LITERAL=$(printf '%s' "$JE_LITERAL" \
    | sed -E 's/!0/true/g; s/!1/false/g' \
    | python3 -c '
import re, sys, json
s = sys.stdin.read()
# Quote unquoted JS object keys: {key: or ,key:
s = re.sub(r"([{,])\s*([A-Za-z_][A-Za-z0-9_]*)\s*:",
           lambda m: m.group(1) + chr(34) + m.group(2) + chr(34) + ":",
           s)
print(json.dumps(json.loads(s), indent=2))
')
  echo "$JSON_LITERAL" > "$WORK"
  note "Bundle-extracted defaults written to working file."
fi

step "Applying empty-list overrides (v1.4.0 ships empty for opt-in plugin install)"
plutil -replace pluginList -json '[]' "$WORK" 2>/dev/null \
  || plutil -insert pluginList -json '[]' "$WORK"
plutil -replace pluginSubListFrozenVersion -json '[]' "$WORK" 2>/dev/null \
  || plutil -insert pluginSubListFrozenVersion -json '[]' "$WORK"

step "Validating fixture"
plutil -p "$WORK" >/dev/null

# Required-keys check matching the spec's BRAT validation rule.
for required in pluginList pluginSubListFrozenVersion updateAtStartup; do
  plutil -extract "$required" raw "$WORK" >/dev/null 2>&1 \
    || plutil -extract "$required" json -o - "$WORK" >/dev/null 2>&1 \
    || { fail "Fixture missing required key: $required"; exit 1; }
done
note "Required keys present: pluginList, pluginSubListFrozenVersion, updateAtStartup"

# Verify the lists are empty.
PL0=$(plutil -extract pluginList.0 raw "$WORK" 2>/dev/null || echo "")
[[ -z "$PL0" ]] || { fail "pluginList non-empty ('$PL0'); v1.4.0 ships empty"; exit 1; }
note "pluginList is empty ✓"

PSL0=$(plutil -extract pluginSubListFrozenVersion.0.repo raw "$WORK" 2>/dev/null || echo "")
[[ -z "$PSL0" ]] || { fail "pluginSubListFrozenVersion non-empty ('$PSL0'); v1.4.0 ships empty"; exit 1; }
note "pluginSubListFrozenVersion is empty ✓"

mv "$WORK" "$FIXTURE"
step "Fixture written to $FIXTURE"
plutil -p "$FIXTURE"
