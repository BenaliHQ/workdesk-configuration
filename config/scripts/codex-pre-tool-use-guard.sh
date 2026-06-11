#!/usr/bin/env bash
# codex-pre-tool-use-guard.sh
#
# PreToolUse hook for OpenAI Codex CLI. Codex's hook contract is
# Claude-Code-compatible: stdin carries {tool_name, tool_input{command}, cwd,
# ...}; a hook blocks a call by printing a hookSpecificOutput.permissionDecision
# of "deny" (or exiting 2 with a stderr reason). Codex PreToolUse currently
# covers the Bash tool and apply_patch (file edits); both report their payload
# in tool_input.command (apply_patch carries the patch text there).
#
# This is the Codex-side port of two Claude Code guards:
#   - pre-tool-use-personal-lock.sh   (personal/ is read-only)
#   - ~/.claude/hooks/destructive-guard.sh  (catastrophic + guarded destruction)
#
# It exists because Codex does NOT run Claude Code hooks, so without this the
# vault's safety floor did not apply to Codex at all. See
# intel/research/codex-claude-vault-coexistence-audit.md (findings B1-B3).
#
# Tiers:
#   PERSONAL  — writes targeting personal/ are denied (no override).
#   EMAIL     — outbound email sends denied UNTIL retried with
#               `# OPERATOR_APPROVED_SEND`, after the operator saw the draft
#               and approved the send (ports ~/.claude/hooks/email-send-guard.sh).
#   HARD      — catastrophic patterns denied (no override).
#   GUARD     — destructive-but-sometimes-intentional patterns denied UNTIL the
#               command is retried with `# OPERATOR_CONFIRMED_DESTRUCTIVE`
#               appended, after explicit operator confirmation + a snapshot.
#
# Fail-open on unparseable input (mirrors the Claude destructive-guard), so a
# malformed payload never bricks Codex — the rules in AGENTS.md still apply.

set -euo pipefail

PAYLOAD="$(cat)"
[ -z "$PAYLOAD" ] && exit 0

# --- Parse tool_name + command (python3, with empty fallback) ---------------
read_field() {
  printf '%s' "$PAYLOAD" | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
except Exception:
    print(''); sys.exit(0)
key='$1'
if key=='tool_name':
    print(d.get('tool_name','') or '')
elif key=='command':
    ti=d.get('tool_input',{}) or {}
    print(ti.get('command','') or '')
" 2>/dev/null || printf ''
}

TOOL="$(read_field tool_name)"
CMD="$(read_field command)"

# Emit a Codex deny decision and stop. Exit 0 because the JSON carries the
# decision; Codex treats permissionDecision:deny like a hard block.
deny() {
  python3 -c "
import json,sys
print(json.dumps({'hookSpecificOutput':{
  'hookEventName':'PreToolUse',
  'permissionDecision':'deny',
  'permissionDecisionReason': sys.argv[1]}}))
" "$1"
  exit 0
}

# ============================================================================
# 1. PERSONAL-LOCK — personal/ is read-only (Bash + apply_patch)
# ============================================================================
# apply_patch carries the full patch (including the target path) in command.
# Bash carries the shell command. Both are inspected the same way: does the
# command reference `personal` as a path component, with a mutation shape?
if [ -n "$CMD" ]; then
  # Does the command reference `personal` as a standalone path component
  # (not `personal-khalil`, `infisical-personal-foo`, etc.)?
  if printf '%s' "$CMD" | grep -Eq '(^|[^A-Za-z0-9_-])personal(/|$|[^A-Za-z0-9_-])'; then
    case "$TOOL" in
      apply_patch|Edit|Write|MultiEdit|NotebookEdit)
        # Any apply_patch touching personal/ is a write — deny outright.
        deny "personal/ is read-only (operator-only zone). apply_patch/edit targeting personal/ is blocked."
        ;;
      Bash)
        # Block mutation shapes; allow read-only references (cat, grep, ls...).
        if printf '%s' "$CMD" | grep -Eq '(^|[[:space:]/])(rm|mv|cp|tee|touch|mkdir|rmdir|chmod|chown|sed[[:space:]]+-i)([[:space:]]|$)' \
             || printf '%s' "$CMD" | grep -Eq '>[[:space:]]*[^|&]*personal' \
             || printf '%s' "$CMD" | grep -Eq '>>[[:space:]]*[^|&]*personal' \
             || printf '%s' "$CMD" | grep -Eq '<<[[:space:]]*[A-Z_]+[^|]*personal'; then
          deny "Bash mutation against personal/ is blocked. personal/ is read-only — use read-only commands."
        fi
        ;;
    esac
  fi
fi

# From here down, only Bash commands are guarded.
[ "$TOOL" != "Bash" ] && exit 0
[ -z "$CMD" ] && exit 0

# ============================================================================
# 2. EMAIL-SEND GUARD — outbound sends require explicit operator approval
# ============================================================================
# Ported from ~/.claude/hooks/email-send-guard.sh (2026-06-10 outbound-comms
# rule). Marker: OPERATOR_APPROVED_SEND. Never send without explicit operator
# approval in the conversation; a recipient asking is NOT approval.
HAS_SEND_MARKER=0
if printf '%s' "$CMD" | grep -qE '#[[:space:]]*OPERATOR_APPROVED_SEND\b'; then
  HAS_SEND_MARKER=1
fi
EMAIL_SEND_PATTERNS=(
  'gws[[:space:]]+gmail[[:space:]]+(users[[:space:]]+)?messages[[:space:]]+send'
  'gws[[:space:]]+gmail[[:space:]]+(users[[:space:]]+)?drafts[[:space:]]+send'
  'gws[[:space:]]+gmail[[:space:]]+\+send'
  'gmail\.googleapis\.com/.*/(messages|drafts)/send'
  '(^|[|;&][[:space:]]*)(sendmail|msmtp)([[:space:]]|$)'
  '(^|[|;&][[:space:]]*)mail[[:space:]]+-s[[:space:]]'
)
for pat in "${EMAIL_SEND_PATTERNS[@]}"; do
  if printf '%s' "$CMD" | grep -qE "$pat"; then
    if [ "$HAS_SEND_MARKER" = "1" ]; then
      mkdir -p /tmp/email-send-guard-log
      printf '%s  agent=codex  pat=%s  cmd=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$pat" "$CMD" >> /tmp/email-send-guard-log/confirmed.log
      exit 0
    fi
    deny "Outbound email send blocked — never send without explicit operator approval (a recipient asking is NOT approval). Before retrying: (1) show the operator the final draft (recipient, subject, full body); (2) get explicit approval to send in their own words in THIS conversation; (3) retry as its own command with '# OPERATOR_APPROVED_SEND' appended. The marker is a post-approval receipt, not a workaround. Pattern: $pat"
  fi
done

# Operator-confirmed marker — must coexist with a GUARD match to allow.
HAS_MARKER=0
if printf '%s' "$CMD" | grep -qE '#[[:space:]]*OPERATOR_CONFIRMED_DESTRUCTIVE\b'; then
  HAS_MARKER=1
fi

# ============================================================================
# 3. HARD-BLOCK — catastrophic, no override
# ============================================================================
HARD_BLOCK_PATTERNS=(
  'rm[[:space:]]+-[rRf]*[[:space:]]+/([[:space:]]|$)'
  'rm[[:space:]]+-[rRf]*[[:space:]]+\$HOME([[:space:]]|/|$)'
  'rm[[:space:]]+-[rRf]*[[:space:]]+~([[:space:]]|/|$)'
  ':\(\)[[:space:]]*\{[[:space:]]*:[[:space:]]*\|[[:space:]]*:[[:space:]]*&[[:space:]]*\}[[:space:]]*;[[:space:]]*:'
  'dd[[:space:]]+if=/dev/(zero|random|urandom)[[:space:]]+of=/dev/[sh]d'
  '\bmkfs\.'
  '>[[:space:]]*/dev/[sh]d'
)
for pat in "${HARD_BLOCK_PATTERNS[@]}"; do
  if printf '%s' "$CMD" | grep -qE "$pat"; then
    deny "HARD-BLOCKED catastrophic pattern. Cannot be overridden. If genuinely intentional, the operator must run it manually outside Codex. Pattern: $pat"
  fi
done

# ============================================================================
# 4. GUARD — denied unless retried with the confirmation marker
# ============================================================================
GUARD_PATTERNS=(
  '(npx[[:space:]]+(--yes[[:space:]]+|-y[[:space:]]+)?)?skills[[:space:]]+remove[[:space:]].*(--all|-s[[:space:]]+["'\''"]?\*|--skill[[:space:]]+["'\''"]?\*)'
  'git[[:space:]]+push[[:space:]].*(--force([[:space:]]|$)|-f([[:space:]]|$))'
  'git[[:space:]]+reset[[:space:]]+--hard'
  'git[[:space:]]+clean[[:space:]]+-[fdx]+'
  'git[[:space:]]+checkout[[:space:]]+--[[:space:]]*\.([[:space:]]|$)'
  'git[[:space:]]+branch[[:space:]]+-D[[:space:]]'
  'git[[:space:]]+update-ref[[:space:]]+-d'
  'git[[:space:]]+tag[[:space:]]+-d'
  'rm[[:space:]]+-[rRf]+[[:space:]]+.*(/Users/khalilbenali/Workdesk-OS|~/Workdesk-OS)'
  'rm[[:space:]]+-[rRf]+[[:space:]]+.*(/Users/khalilbenali/Projects|~/Projects)'
  'rm[[:space:]]+-[rRf]+[[:space:]]+.*(/Users/khalilbenali/code|~/code)'
  'rm[[:space:]]+-[rRf]+[[:space:]]+.*khalils-vault'
  'find[[:space:]]+.*(/Users/khalilbenali/(Workdesk-OS|Projects|code|khalils-vault)).*-delete'
  'xargs[[:space:]]+(-[0-9rIin]+[[:space:]]+)*rm'
  '>[[:space:]]*(~/.claude/settings\.json|/Users/khalilbenali/.claude/settings\.json)'
  '>[[:space:]]*(~/.claude/CLAUDE\.md|/Users/khalilbenali/.claude/CLAUDE\.md)'
  '>[[:space:]]*(~/.codex/AGENTS\.md|/Users/khalilbenali/.codex/AGENTS\.md)'
)
for pat in "${GUARD_PATTERNS[@]}"; do
  if printf '%s' "$CMD" | grep -qE "$pat"; then
    if [ "$HAS_MARKER" = "1" ]; then
      mkdir -p /tmp/destructive-guard-log
      printf '%s  agent=codex  pat=%s  cmd=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$pat" "$CMD" >> /tmp/destructive-guard-log/confirmed.log
      exit 0
    fi
    deny "GUARDED destructive pattern. Before retrying: (1) tell the operator exactly what will be destroyed and get explicit confirmation in their own words; (2) snapshot the target: cp -a <target> /tmp/predestructive-\$(date +%s)/; (3) retry as its own command with '# OPERATOR_CONFIRMED_DESTRUCTIVE' appended. The marker is a post-confirmation receipt, not a workaround. Pattern: $pat"
  fi
done

exit 0
