#!/usr/bin/env bash
# 1.15.0 → 1.16.0: add the `daily-plan:` preferences block to operator-profile.md.
#
# The daily-plan signal (v1.2) is now operator-configurable. It reads a
# `daily-plan:` frontmatter block (calendar-scope, calendar-lookahead-days,
# daily-note-lookback-days, action-email-label, exclude-calendars) from
# operator-profile.md. The signal degrades gracefully when fields are missing
# (each falls back to a default), so this migration is a courtesy: it pre-adds
# the block with defaults so the operator can see and edit it.
#
# Runs AFTER file-merge, so it lands the block regardless of how the operator
# resolved any operator-profile.md conflict (mine / theirs / merged).
#
# Preserves all existing frontmatter values — only inserts the new block if it
# isn't already present.
#
# Idempotent: if a `daily-plan:` key already exists in the frontmatter, exit 0.
#
# Env (set by migrate.sh):
#   WORKDESK_VAULT — vault root
#   WORKDESK_WD    — control-plane directory ($VAULT/config)

set -u

WD="${WORKDESK_WD:?WORKDESK_WD not set}"
PROFILE="$WD/operator-profile.md"

# No profile yet (fresh/edge vault) — nothing to migrate.
if [[ ! -f "$PROFILE" ]]; then
  echo "add-daily-plan-prefs: no operator-profile.md found; skipping."
  exit 0
fi

python3 - "$PROFILE" <<'PYEOF'
import sys

path = sys.argv[1]
with open(path, "r") as f:
    lines = f.readlines()

# Locate the YAML frontmatter: must start with a '---' line, then a closing '---'.
if not lines or lines[0].strip() != "---":
    print("add-daily-plan-prefs: no frontmatter detected; leaving file unchanged.")
    sys.exit(0)

close_idx = None
for i in range(1, len(lines)):
    if lines[i].strip() == "---":
        close_idx = i
        break

if close_idx is None:
    print("add-daily-plan-prefs: unterminated frontmatter; leaving file unchanged.")
    sys.exit(0)

frontmatter = lines[1:close_idx]

# Idempotency: a top-level `daily-plan:` key already present → no-op.
for ln in frontmatter:
    if ln.startswith("daily-plan:"):
        print("add-daily-plan-prefs: daily-plan block already present; no-op.")
        sys.exit(0)

block = [
    "daily-plan:\n",
    "  calendar-scope: own\n",
    "  calendar-lookahead-days: 7\n",
    "  daily-note-lookback-days: 7\n",
    '  action-email-label: ""\n',
    "  exclude-calendars: []\n",
]

# Insert the block just before the closing '---', preserving everything else.
new_lines = lines[:close_idx] + block + lines[close_idx:]
with open(path, "w") as f:
    f.writelines(new_lines)

print("add-daily-plan-prefs: inserted daily-plan block with defaults.")
PYEOF
