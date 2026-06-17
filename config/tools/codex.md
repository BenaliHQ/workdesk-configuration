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

## Troubleshooting

- **"Codex CLI is not authenticated" can be a lie — check the config first.** On codex ≥0.125.0, an invalid value in `~/.codex/config.toml` makes the binary fail to *parse its config* and exit before it ever checks auth; wrappers/companions then misreport this as "not authenticated." Verify with `/opt/homebrew/bin/codex login status` (full path, bypassing the shell wrapper) — if it errors with `Error loading configuration: …/config.toml:<line>: unknown variant …`, it's a config problem, not auth. Seen 2026-06-17: `service_tier = "default"` was rejected (0.125.0 accepts only `fast` or `flex`). Fix: set a valid value or remove the key (removing reverts to codex's built-in default tier).
- **Bare `codex` bails in non-interactive shells with `ramdisk auth.json missing at  —` (note the empty path).** The `codex` shell function is preserved in Claude Code's Bash snapshot, but its helper variable `__wd_codex_ram` is a non-exported shell var that comes back empty — so the wrapper aborts before reaching the binary. Fix: source the env in the same command — `source <vault>/config/shell/codex-env.sh && codex …` (where `<vault>` is your WorkDesk OS vault root) — which re-sets the wrapper's variables and preserves the secure ramdisk→SSD→restore flow. For read-only one-offs you can instead call the real binary directly at `/opt/homebrew/bin/codex`, but that bypasses the wrapper's token-write protection, so prefer sourcing the env.
- **At `xhigh` reasoning, a Codex doc review can hang in the search phase for tens of minutes.** For bounded read-only reviews, drop to `-c model_reasoning_effort="medium"` and pre-specify the exact files to read (so it doesn't search) — returns in 1–2 min instead of stalling.

## Linked use cases

- `intel/research/codex-claude-vault-coexistence-audit.md` — the audit that produced this wiring.
- `intel/research/parallel-agent-collision-protocol.md` — what to do when Codex and Claude collide on the same files.
