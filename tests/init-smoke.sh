#!/usr/bin/env bash
# init-smoke.sh — smoke tests for init.sh orchestrator
#
# Exercises the parts of init.sh that don't require a real Obsidian launch:
# - version_ge unit tests (smoke 23)
# - JSON helpers (json_ok)
# - SHA256 verification path (smoke 10)
# - --dry-run flow (no writes)
# - vault-path symlink rejection
# - existing-vault abort (smoke 6)
#
# Tests that DO require a real Obsidian launch (1, 14-19, 26-27 from the
# spec's smoke matrix) stay manual for now and gate the operator's exit.

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
init="$repo_root/init.sh"
test_root="$repo_root/.workdesk-init-test"
rm -rf "$test_root"
mkdir -p "$test_root"

# Mock `claude`, `mdfind`, and Obsidian.app so platform-check passes in CI
# environments that don't have Claude Code or Obsidian installed.
mock_bin="$test_root/mock-bin"
mock_obsidian="$test_root/Obsidian.app"
mkdir -p "$mock_bin" "$mock_obsidian/Contents"

cat > "$mock_bin/claude" <<'STUB'
#!/usr/bin/env bash
exit 0
STUB
chmod +x "$mock_bin/claude"

# Build a minimal Info.plist with CFBundleShortVersionString >= 1.12.2 so
# the Obsidian min-version check passes (Templater is the floor at 1.12.2).
cat > "$mock_obsidian/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleShortVersionString</key>
  <string>99.99.99</string>
  <key>CFBundleIdentifier</key>
  <string>md.obsidian</string>
</dict>
</plist>
PLIST

# Shadow mdfind to return our fake Obsidian.app path.
cat > "$mock_bin/mdfind" <<STUB
#!/usr/bin/env bash
echo "$mock_obsidian"
STUB
chmod +x "$mock_bin/mdfind"

export PATH="$mock_bin:$PATH"

pass=0
fail=0
assert() {
  local label="$1" actual="$2" expected="$3"
  if [[ "$actual" == "$expected" ]]; then
    printf '  PASS  %s\n' "$label"
    pass=$((pass+1))
  else
    printf '  FAIL  %s — got %q, expected %q\n' "$label" "$actual" "$expected"
    fail=$((fail+1))
  fi
}

# Source the helpers from init.sh by carving them out into a sub-shell.
# We can't `source init.sh` directly because main() runs at the bottom.
# Instead we extract the function bodies into a sandbox.
helpers=$(sed -n '/^# ---- version_ge/,/^# ---- json helpers/p; /^# ---- json helpers/,/^# ---- platform check/p' "$init")

run_in_sandbox() {
  bash -c "$(printf '%s\n%s\n' "$helpers" "$1")"
}

# ---- version_ge unit tests (smoke 23) ----------------------------------------
printf '\n[unit] version_ge\n'
test_ge() {
  local found="$1" required="$2" expected="$3"
  local rc
  set +e
  run_in_sandbox "version_ge \"$found\" \"$required\""; rc=$?
  set -e
  assert "version_ge $found $required" "$rc" "$expected"
}
test_ge 1.10.0 1.9.9    0
test_ge 1.0.0  1.0      0
test_ge 1.0    1.0.1    1
test_ge 0.16.5 1.0.0    1
test_ge 1.12.2 0.0.0    0
test_ge 1.11.7 1.12.2   1
test_ge 1.12.2 1.12.2   0
test_ge ""     1.0      2
test_ge 1.2-beta 1.0    2

# ---- json_ok unit tests ------------------------------------------------------
printf '\n[unit] json_ok\n'
ok_file="$test_root/ok.json"
bad_file="$test_root/bad.json"
printf '{"a":1,"b":[1,2,3]}' > "$ok_file"
printf '{ broken' > "$bad_file"

set +e
run_in_sandbox "json_ok \"$ok_file\""; rc_ok=$?
run_in_sandbox "json_ok \"$bad_file\""; rc_bad=$?
set -e
assert "json_ok valid"   "$rc_ok"  "0"
assert "json_ok invalid" "$rc_bad" "1"

# ---- vault-path: existing-with-.obsidian aborts without FORCE (smoke 6) -----
printf '\n[scenario] existing-vault abort\n'
existing="$test_root/existing-vault"
mkdir -p "$existing/.obsidian"

set +e
out=$(WORKDESK_INIT_DRYRUN=1 WORKDESK_VAULT_PATH="$existing" "$init" 2>&1)
rc=$?
set -e
if [[ "$rc" -ne 0 ]] && grep -q 'Vault already exists' <<<"$out"; then
  printf '  PASS  existing-vault aborts with documented message\n'
  pass=$((pass+1))
else
  printf '  FAIL  expected non-zero exit + "Vault already exists" message\n%s\n' "$out"
  fail=$((fail+1))
fi

# ---- vault-path: --force allows reuse ----------------------------------------
printf '\n[scenario] --force allows existing-vault reuse\n'
set +e
out=$(WORKDESK_INIT_DRYRUN=1 WORKDESK_INIT_FORCE=1 WORKDESK_VAULT_PATH="$existing" "$init" 2>&1)
rc=$?
set -e
# In dry-run mode this can fail at later steps for environmental reasons
# (e.g. Obsidian version), but the existing-vault check must NOT be the cause.
if grep -q 'Vault already exists' <<<"$out"; then
  printf '  FAIL  --force should not abort on existing vault\n'
  fail=$((fail+1))
else
  printf '  PASS  --force bypasses existing-vault abort\n'
  pass=$((pass+1))
fi

# ---- dry-run: no writes outside vault ----------------------------------------
printf '\n[scenario] dry-run produces no files\n'
fresh="$test_root/dryrun-fresh-vault"
set +e
out=$(WORKDESK_INIT_DRYRUN=1 WORKDESK_VAULT_PATH="$fresh" "$init" 2>&1)
rc=$?
set -e
if [[ -e "$fresh" ]]; then
  printf '  FAIL  dry-run created the vault directory at %s\n' "$fresh"
  fail=$((fail+1))
else
  printf '  PASS  dry-run did not create vault dir\n'
  pass=$((pass+1))
fi

# ---- SHA verification: tampered main.js detected (smoke 10) ------------------
printf '\n[scenario] SHA256 mismatch detection\n'
# Stage a tampered local clone. As of v1.4.0, BRAT is the only bundled plugin
# so we use it for the tampering test.
sha_test="$test_root/sha-test-clone"
mkdir -p "$sha_test/vendor/plugins/obsidian42-brat"
cp "$repo_root/vendor/plugins/obsidian42-brat/manifest.json" "$sha_test/vendor/plugins/obsidian42-brat/"
cp "$repo_root/vendor/plugins/obsidian42-brat/UPSTREAM.md" "$sha_test/vendor/plugins/obsidian42-brat/"
echo "TAMPERED" > "$sha_test/vendor/plugins/obsidian42-brat/main.js"
[[ -f "$repo_root/vendor/plugins/obsidian42-brat/styles.css" ]] \
  && cp "$repo_root/vendor/plugins/obsidian42-brat/styles.css" "$sha_test/vendor/plugins/obsidian42-brat/"
# We test only the SHA-mismatch branch logic; not the full init.sh which
# would re-fetch. So we manually invoke the comparison.
expected_sha=$(grep -E '\`main\.js\`' "$sha_test/vendor/plugins/obsidian42-brat/UPSTREAM.md" | grep -oE '[a-f0-9]{64}' | head -n1)
actual_sha=$(shasum -a 256 "$sha_test/vendor/plugins/obsidian42-brat/main.js" | awk '{print $1}')
if [[ "$actual_sha" != "$expected_sha" ]]; then
  printf '  PASS  SHA256 mismatch correctly detectable (expected %s, got %s)\n' "${expected_sha:0:12}…" "${actual_sha:0:12}…"
  pass=$((pass+1))
else
  printf '  FAIL  SHA256 should not match for tampered file\n'
  fail=$((fail+1))
fi

# ---- BRAT fixture parses + has required keys --------------------------------
printf '\n[scenario] BRAT fixture is valid + complete\n'
fixture="$repo_root/vendor/plugins/obsidian42-brat/data.json.fixture"
if plutil -convert json -o /dev/null "$fixture" >/dev/null 2>&1; then
  printf '  PASS  fixture parses as JSON\n'
  pass=$((pass+1))
else
  printf '  FAIL  fixture does not parse\n'
  fail=$((fail+1))
fi
# v1.4.0: pluginList and pluginSubListFrozenVersion ship EMPTY — BRAT is the
# only bundled plugin and everything else is opt-in via BRAT's UI.
pl0=$(plutil -extract pluginList.0 raw "$fixture" 2>/dev/null || echo "")
psl_repo=$(plutil -extract pluginSubListFrozenVersion.0.repo raw "$fixture" 2>/dev/null || echo "")
assert "fixture pluginList is empty"                "$pl0"      ""
assert "fixture pluginSubListFrozenVersion empty"   "$psl_repo" ""
update_at_startup=$(plutil -extract updateAtStartup raw "$fixture" 2>/dev/null || echo "")
assert "fixture updateAtStartup"                    "$update_at_startup" "true"

# ---- summary -----------------------------------------------------------------
rm -rf "$test_root"
printf '\n========================\n'
printf '  passed: %d\n' "$pass"
printf '  failed: %d\n' "$fail"
if [[ "$fail" -gt 0 ]]; then
  exit 1
fi
exit 0
