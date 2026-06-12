#!/usr/bin/env bash
# repo-session-test.sh - hermetic coverage for config/scripts/repo-session.sh.

set -euo pipefail
IFS=$'\n\t'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SCRIPT="$REPO_ROOT/config/scripts/repo-session.sh"

PASS=0
FAIL=0
OUT=""
RC=0

assert() {
  local label="$1"
  shift
  if "$@"; then
    printf '  PASS  %s\n' "$label"
    PASS=$((PASS + 1))
  else
    printf '  FAIL  %s\n' "$label"
    FAIL=$((FAIL + 1))
  fi
}

assert_eq() {
  local label="$1"
  local got="$2"
  local want="$3"
  if [[ "$got" == "$want" ]]; then
    printf '  PASS  %s\n' "$label"
    PASS=$((PASS + 1))
  else
    printf '  FAIL  %s\n         got:  %q\n         want: %q\n' "$label" "$got" "$want"
    FAIL=$((FAIL + 1))
  fi
}

assert_ne() {
  local label="$1"
  local got="$2"
  local not_want="$3"
  if [[ "$got" != "$not_want" ]]; then
    printf '  PASS  %s\n' "$label"
    PASS=$((PASS + 1))
  else
    printf '  FAIL  %s\n         both: %q\n' "$label" "$got"
    FAIL=$((FAIL + 1))
  fi
}

assert_contains() {
  local label="$1"
  local haystack="$2"
  local needle="$3"
  if [[ "$haystack" == *"$needle"* ]]; then
    printf '  PASS  %s\n' "$label"
    PASS=$((PASS + 1))
  else
    printf '  FAIL  %s\n         needle: %q\n         haystack: %q\n' "$label" "$needle" "$haystack"
    FAIL=$((FAIL + 1))
  fi
}

assert_nonzero() {
  local label="$1"
  local rc="$2"
  if [[ "$rc" -ne 0 ]]; then
    printf '  PASS  %s\n' "$label"
    PASS=$((PASS + 1))
  else
    printf '  FAIL  %s\n         expected non-zero exit\n' "$label"
    FAIL=$((FAIL + 1))
  fi
}

run_session() {
  set +e
  OUT="$("$SCRIPT" "$@" 2>&1)"
  RC=$?
  set -e
}

extract_worktree() {
  printf '%s\n' "$1" | awk -F= '/^WORKTREE=/{print $2}' | tail -n 1
}

json_parses() {
  python3 - "$1" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as f:
    json.load(f)
PY
}

backdate_lease() {
  local lease="$1"
  local days="$2"
  local old
  old="$(( $(date +%s) - (days * 86400) ))"
  python3 - "$lease" "$old" <<'PY'
import json
import os
import sys

path = sys.argv[1]
old = int(sys.argv[2])
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)
data["last_used"] = old
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, sort_keys=True)
    f.write("\n")
os.replace(tmp, path)
PY
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

export WORKTREES_ROOT="$TMP/worktrees"
export GIT_TERMINAL_PROMPT=0

REMOTE="$TMP/remote.git"
SEED="$TMP/seed"
SHARED="$TMP/code/demo-repo"

mkdir -p "$TMP/code"
git init --bare "$REMOTE" >/dev/null
git init "$SEED" >/dev/null
git -C "$SEED" checkout -b main >/dev/null
git -C "$SEED" config user.email "repo-session@example.test"
git -C "$SEED" config user.name "Repo Session Test"
printf 'hello\n' > "$SEED/README.md"
git -C "$SEED" add README.md
git -C "$SEED" commit -m "seed" >/dev/null
git -C "$SEED" remote add origin "$REMOTE"
git -C "$SEED" push -u origin main >/dev/null
git --git-dir="$REMOTE" symbolic-ref HEAD refs/heads/main
git clone "$REMOTE" "$SHARED" >/dev/null 2>&1
git -C "$SHARED" config user.email "repo-session@example.test"
git -C "$SHARED" config user.name "Repo Session Test"

REMOTE_MAIN_SHA="$(git --git-dir="$REMOTE" rev-parse refs/heads/main)"

echo "Scenario 1: start creates origin-based private workspace"
run_session start "$SHARED" alpha --agent claude
WT_ALPHA="$(extract_worktree "$OUT")"
LEASE_ALPHA="$WORKTREES_ROOT/.registry/demo-repo--alpha.json"
assert_eq "start exits 0" "$RC" "0"
assert_contains "start prints WORKTREE" "$OUT" "WORKTREE="
assert "alpha worktree exists" test -d "$WT_ALPHA"
assert_eq "alpha branch name" "$(git -C "$WT_ALPHA" rev-parse --abbrev-ref HEAD)" "claude/alpha"
assert_eq "alpha starts at remote main" "$(git -C "$WT_ALPHA" rev-parse HEAD)" "$REMOTE_MAIN_SHA"
assert "alpha lease exists" test -f "$LEASE_ALPHA"
set +e
json_parses "$LEASE_ALPHA"
JSON_RC=$?
set -e
assert_eq "alpha lease JSON parses" "$JSON_RC" "0"

echo
echo "Scenario 2: shared checkout ahead does not affect new base"
printf 'local only\n' >> "$SHARED/README.md"
git -C "$SHARED" add README.md
git -C "$SHARED" commit -m "local shared change" >/dev/null
LOCAL_MAIN_SHA="$(git -C "$SHARED" rev-parse main)"
run_session start "$SHARED" beta --agent claude
WT_BETA="$(extract_worktree "$OUT")"
assert_eq "beta start exits 0" "$RC" "0"
assert_contains "beta warns about unshared commits" "$OUT" "haven't been shared yet"
assert_eq "beta starts at remote main" "$(git -C "$WT_BETA" rev-parse HEAD)" "$REMOTE_MAIN_SHA"
assert_ne "beta is not based on local main" "$(git -C "$WT_BETA" rev-parse HEAD)" "$LOCAL_MAIN_SHA"

echo
echo "Scenario 3: start resumes idempotently"
run_session start "$SHARED" alpha --agent claude
WT_ALPHA_AGAIN="$(extract_worktree "$OUT")"
LEASE_COUNT="$(find "$WORKTREES_ROOT/.registry" -type f -name 'demo-repo--alpha.json' -print | wc -l | tr -d ' ')"
assert_eq "resume exits 0" "$RC" "0"
assert_contains "resume says Resuming" "$OUT" "Resuming"
assert_eq "resume returns same path" "$WT_ALPHA_AGAIN" "$WT_ALPHA"
assert_eq "no duplicate alpha lease" "$LEASE_COUNT" "1"

echo
echo "Scenario 4: status lists leases and self-heals missing worktrees"
run_session status
assert_eq "status exits 0" "$RC" "0"
assert_contains "status lists alpha" "$OUT" "alpha"
assert_contains "status lists beta" "$OUT" "beta"
rm -rf "$WT_BETA"
run_session status
assert_eq "status after removal exits 0" "$RC" "0"
assert "beta lease pruned" test ! -f "$WORKTREES_ROOT/.registry/demo-repo--beta.json"

echo
echo "Scenario 5: finish --no-pr pushes and cleans up"
printf 'alpha work\n' > "$WT_ALPHA/alpha.txt"
git -C "$WT_ALPHA" add alpha.txt
git -C "$WT_ALPHA" commit -m "alpha change" >/dev/null
run_session finish alpha --no-pr
assert_eq "finish exits 0" "$RC" "0"
assert "alpha branch pushed" git --git-dir="$REMOTE" rev-parse --verify refs/heads/claude/alpha >/dev/null
assert "alpha worktree removed" test ! -d "$WT_ALPHA"
assert "alpha lease removed" test ! -f "$LEASE_ALPHA"

echo
echo "Scenario 6: dirty finish refuses"
run_session start "$SHARED" dirty --agent claude
WT_DIRTY="$(extract_worktree "$OUT")"
printf 'not committed\n' > "$WT_DIRTY/dirty.txt"
run_session finish dirty --no-pr
assert_nonzero "dirty finish exits non-zero" "$RC"
assert_contains "dirty finish explains unsaved changes" "$OUT" "unsaved changes"
assert "dirty worktree remains" test -d "$WT_DIRTY"
assert "dirty lease remains" test -f "$WORKTREES_ROOT/.registry/demo-repo--dirty.json"

echo
echo "Scenario 7: cleanup reaps old clean work and skips dirty work"
run_session start "$SHARED" oldclean --agent claude
WT_OLDCLEAN="$(extract_worktree "$OUT")"
LEASE_OLDCLEAN="$WORKTREES_ROOT/.registry/demo-repo--oldclean.json"
run_session start "$SHARED" olddirty --agent claude
WT_OLDDIRTY="$(extract_worktree "$OUT")"
LEASE_OLDDIRTY="$WORKTREES_ROOT/.registry/demo-repo--olddirty.json"
printf 'dirty old\n' > "$WT_OLDDIRTY/old.txt"
backdate_lease "$LEASE_OLDCLEAN" 8
backdate_lease "$LEASE_OLDDIRTY" 8
run_session cleanup --days 7
assert_eq "cleanup exits 0" "$RC" "0"
assert_contains "cleanup warns about skipped dirty work" "$OUT" "Skipping 'olddirty'"
assert "old clean worktree removed" test ! -d "$WT_OLDCLEAN"
assert "old clean lease removed" test ! -f "$LEASE_OLDCLEAN"
assert "old dirty worktree remains" test -d "$WT_OLDDIRTY"
assert "old dirty lease remains" test -f "$LEASE_OLDDIRTY"

echo
echo "Scenario 8: locks exclude concurrent writers"
"$SCRIPT" lock demo -- sleep 3 >"$TMP/lock-demo.out" 2>&1 &
LOCK_PID=$!
for _ in 1 2 3 4 5; do
  [[ -f "$WORKTREES_ROOT/.locks/demo.lock/meta.json" ]] && break
  sleep 1
done
assert "first lock acquired" test -f "$WORKTREES_ROOT/.locks/demo.lock/meta.json"
set +e
OUT="$(REPO_SESSION_LOCK_TIMEOUT=1 "$SCRIPT" lock demo -- true 2>&1)"
RC=$?
set -e
assert_nonzero "second lock attempt fails" "$RC"
assert_contains "second lock explains resource is in use" "$OUT" "is in use"
wait "$LOCK_PID"
run_session lock demo -- true
assert_eq "lock works again after release" "$RC" "0"

echo
echo "Scenario 9: stale locks are taken over"
mkdir -p "$WORKTREES_ROOT/.locks/stale.lock"
python3 - "$WORKTREES_ROOT/.locks/stale.lock/meta.json" <<'PY'
import json
import sys

with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump({"pid": 99999999, "agent": "claude", "started": 1}, f)
PY
run_session lock-acquire stale
assert_eq "stale acquire exits 0" "$RC" "0"
assert_contains "stale acquire notes takeover" "$OUT" "stale lock"
run_session lock-release stale --force
assert_eq "forced stale release exits 0" "$RC" "0"

echo
echo "Scenario 10: explicit codex agent changes attribution"
run_session start "$SHARED" zeta --agent codex
WT_ZETA="$(extract_worktree "$OUT")"
assert_eq "codex start exits 0" "$RC" "0"
assert_eq "codex branch name" "$(git -C "$WT_ZETA" rev-parse --abbrev-ref HEAD)" "codex/zeta"

echo
echo "Result: $PASS passed, $FAIL failed"
exit $((FAIL > 0 ? 1 : 0))
