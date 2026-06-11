---
tool: Codex
slug: codex
category: dev
class: operator-named
connected: true
added-on: 2026-05-01
connector: cli
preferred-for: []
confirmed-by-operator: true
---

## What it is

OpenAI Codex CLI — second-opinion coding agent.

OpenAI Codex CLI — second-opinion coding agent that also operates directly in this vault. Runs fully autonomous (`approval_policy = "never"`, `sandbox_mode = "danger-full-access"`, vault trusted in `~/.codex/config.toml`).

## Best practices

- Codex does **not** read `config/rules/` or `~/.claude/CLAUDE.md`. It is governed by `AGENTS.md` files: the project `~/Workdesk-OS/AGENTS.md` (points it at `config/rules/` + inlines the non-negotiables) and the global `~/.codex/AGENTS.md` (mirror of `~/.claude/CLAUDE.md`). Keep both in sync when the Claude-side instructions change.
- Auth rides the Infisical + RAM-disk pattern (the `codex` shell function copies `auth.json` ramdisk→ssd before running, mirrors back + re-pushes after). Same shape as `gws`/`qbo`.

## Connection notes

- **Safety hooks (added 2026-06-10, Tier 1 of the coexistence audit).** A PreToolUse guard at `config/scripts/codex-pre-tool-use-guard.sh`, wired via `.codex/hooks.json`, ports the Claude-side `personal-lock` + `destructive-guard` to Codex. It blocks: writes to `personal/` (Bash + `apply_patch`), catastrophic destruction (no override), and guarded destructive shapes (until `# OPERATOR_CONFIRMED_DESTRUCTIVE` is appended after operator confirmation + snapshot). Verified live against Codex 0.125.0 — Codex fires `PreToolUse`, honors `permissionDecision: deny`, and reports "PreToolUse Blocked".
- Codex `PreToolUse` currently covers Bash and `apply_patch` (file edits), not every tool. The hook is a floor; the `AGENTS.md` rules are the ceiling.
- `codex_hooks` is a stable, enabled feature in 0.125.0. Hooks are discovered at `~/.codex/hooks.json` (global) and `<repo>/.codex/hooks.json` (project). No project-dir env var is set for non-plugin hooks — script paths in `.codex/hooks.json` must be absolute.

## Linked use cases

- `intel/research/codex-claude-vault-coexistence-audit.md` — the audit that produced this wiring.
- `intel/research/parallel-agent-collision-protocol.md` — what to do when Codex and Claude collide on the same files.
