#!/usr/bin/env bash
# learnings-scan.sh — Stop hook. Propose promotion when a correction repeats
# across skills.
#
# The read half of the co-evolution loop (config/rules/claude-md-coevolution.md).
# learnings-capture.sh writes corrections into each skill's learnings.md; this
# script looks for the same correction appearing in TWO OR MORE skills within
# 30 days and writes a [REVIEW] inbox item proposing it be promoted to a rule.
#
# It proposes. It never applies — promotion always needs the operator.
#
# Cheap by design: runs on every Stop, but exits in milliseconds unless some
# learnings.md has actually changed since the last scan.
#
# Matching is fuzzy token overlap, NOT semantic similarity. Specifically the
# overlap coefficient (shared tokens / smaller token set) over normalised,
# stop-worded tokens. Jaccard was tried first and rejected: it punishes the
# common real shape where one correction is terse and the other is a sentence,
# and it failed the canonical example in the rule itself ("don't use leverage"
# vs "avoid leverage in drafts" scores 0.29 on Jaccard, 1.0 on overlap).
#
# The ceiling: two corrections that mean the same thing in entirely different
# words will not match. That is a known limit, not a bug to report — the
# fallback is /weekly-review, which the rule already names as the manual
# backstop. False positives are the cheaper error here, since every proposal is
# operator-reviewed and a rejected cluster is never surfaced again.
#
# State: config/state/learnings-scan.json
#   last-scan   epoch seconds of the last run
#   proposed    cluster keys already surfaced (never re-proposed)
#   rejected    cluster keys the operator declined (never re-proposed)
#
# Reads hook JSON on stdin and ignores it; nothing here needs session context.

# set -e is on to match the repo convention (tests/hardening-test.sh enforces it).
# Every failure-capable command below is explicitly guarded, and the arithmetic
# tests use if-blocks rather than `(( ... )) && cmd` — a false `(( ))` returns 1,
# which under -e would kill the hook instead of skipping the branch.
set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VAULT="${CLAUDE_PROJECT_DIR:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
SKILLS_DIR="$VAULT/config/skills"
STATE_FILE="$VAULT/config/state/learnings-scan.json"

# Drain stdin so the hook never blocks on an unread pipe.
cat >/dev/null 2>&1 || true

[[ -d "$SKILLS_DIR" ]] || exit 0

# --- fast path: nothing to do unless a learnings.md changed -------------------
last_scan=0
if [[ -f "$STATE_FILE" ]]; then
  last_scan=$(python3 -c "
import json, sys
try:
    print(int(json.load(open(sys.argv[1])).get('last-scan', 0)))
except Exception:
    print(0)
" "$STATE_FILE" 2>/dev/null || echo 0)
fi

newest=0
while IFS= read -r f; do
  m=$(stat -f '%m' "$f" 2>/dev/null || stat -c '%Y' "$f" 2>/dev/null || echo 0)
  if (( m > newest )); then
    newest=$m
  fi
done < <(find "$SKILLS_DIR" -mindepth 2 -maxdepth 2 -name 'learnings.md' -type f 2>/dev/null)

# No learnings files at all, or none touched since the last scan.
if (( newest == 0 )) || (( newest <= last_scan )); then
  exit 0
fi

# --- scan ---------------------------------------------------------------------
python3 - "$VAULT" "$STATE_FILE" <<'PY' || true
import datetime as dt
import json
import os
import re
import sys
import time

vault, state_path = sys.argv[1], sys.argv[2]
skills_dir = os.path.join(vault, "config", "skills")
inbox = os.path.join(vault, "gtd", "inbox")

WINDOW_DAYS = 30
SIMILARITY = 0.5   # overlap coefficient, not Jaccard

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "do", "dont", "for",
    "from", "in", "into", "is", "it", "its", "not", "of", "on", "or", "so", "than",
    "that", "the", "then", "these", "this", "to", "use", "using", "was", "when",
    "with", "you", "your", "always", "never", "should", "must", "avoid", "prefer",
}

ENTRY = re.compile(r"^-\s+(\d{4}-\d{2}-\d{2})\s+`\[([A-Z]+)\]`\s+(.*\S)\s*$")

# Promotion targets, per the table in claude-md-coevolution.md.
TARGET = {
    "STYLE": "`config/rules/writing-style.md`",
    "PROCESS": "a new or updated `config/rules/{name}.md`",
    "TOOL": "the relevant `config/rules/tools/{slug}.md`",
    "FACT": "`config/operator-profile.md`",
    "OTHER": "a rule or CLAUDE.md, whichever fits",
}


def load_state():
    try:
        with open(state_path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_state(state):
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    with open(state_path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
        fh.write("\n")


def tokens(text):
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def overlap(a, b):
    """Shared tokens over the SMALLER set. Forgiving of terse-vs-verbose pairs."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


cutoff = dt.date.today() - dt.timedelta(days=WINDOW_DAYS)
entries = []

for skill in sorted(os.listdir(skills_dir)):
    path = os.path.join(skills_dir, skill, "learnings.md")
    if not os.path.isfile(path):
        continue
    for line in open(path, encoding="utf-8"):
        m = ENTRY.match(line.rstrip("\n"))
        if not m:
            continue
        date_s, tag, text = m.groups()
        try:
            when = dt.date.fromisoformat(date_s)
        except ValueError:
            continue
        if when < cutoff:
            continue
        entries.append({"skill": skill, "date": date_s, "tag": tag,
                        "text": text, "tokens": tokens(text)})

state = load_state()
seen = set(state.get("proposed", [])) | set(state.get("rejected", []))
today = dt.date.today().isoformat()
written = 0

# Cluster by transitive similarity, but only count a cluster when it spans
# more than one skill — a skill correcting itself twice is local, per the rule.
used = set()
for i, a in enumerate(entries):
    if i in used:
        continue
    cluster = [i]
    for j in range(i + 1, len(entries)):
        if j in used:
            continue
        if overlap(a["tokens"], entries[j]["tokens"]) >= SIMILARITY:
            cluster.append(j)
    skills = {entries[k]["skill"] for k in cluster}
    if len(skills) < 2:
        continue
    for k in cluster:
        used.add(k)

    key_tokens = sorted(set.intersection(*(entries[k]["tokens"] for k in cluster)))
    key = "+".join(sorted(skills)) + "::" + "-".join(key_tokens[:6])
    if key in seen:
        continue

    tag = entries[cluster[0]]["tag"]
    target = TARGET.get(tag, TARGET["OTHER"])
    slug = re.sub(r"[^a-z0-9]+", "-", "-".join(key_tokens[:4]) or "correction").strip("-")
    fname = f"{today}-promote-{slug}.md"
    path = os.path.join(inbox, fname)
    if os.path.exists(path):
        state.setdefault("proposed", []).append(key)
        continue

    occurrences = "\n".join(
        f"- **/{entries[k]['skill']}** ({entries[k]['date']}): {entries[k]['text']}"
        for k in cluster
    )

    body = f"""---
type: inbox-item
prefix: REVIEW
created: {today}
source: learnings-scan
---
# [REVIEW] Same correction in {len(skills)} skills — promote it to a rule?

## Operator review

- {""}

---

## The correction, as captured

{occurrences}

## Why you're seeing this

Per [[claude-md-coevolution]], a correction that lands in two or more skills
within 30 days belongs at the rules level, not repeated in each skill's
`learnings.md`. Otherwise the same fix gets entered five times in five places.

**Proposed target:** {target}

Say go and I'll draft the promotion, apply it, and append a `[PROMOTED]`
back-link to each source `learnings.md`. Say no and this cluster is marked
operator-rejected and never surfaced again.

---

*Detected by `config/scripts/learnings-scan.sh` on {today}. Matching is fuzzy
token overlap, not semantic, so this can be a false positive — saying no costs
nothing and the cluster never comes back.*
"""
    os.makedirs(inbox, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    state.setdefault("proposed", []).append(key)
    written += 1

state["last-scan"] = int(time.time())
state.setdefault("proposed", state.get("proposed", []))
state.setdefault("rejected", state.get("rejected", []))
save_state(state)

if written:
    print(f"learnings-scan: {written} promotion candidate(s) written to gtd/inbox/",
          file=sys.stderr)
PY

exit 0
