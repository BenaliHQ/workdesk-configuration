# WorkDesk OS

A giveable Obsidian + Claude Code working surface for knowledge work with AI.

WorkDesk OS turns a fresh vault into a five-zone, agent-guided system that captures your work, surfaces signal, and keeps up with your life. You experience it as furniture — not an application.

> **V1 status.** Mac-only. Greenfield (empty vault) only. The vault content architecture is OS-agnostic; only the install/runtime layer is Mac-specific.

## What ships

**Five zones.** Each zone manages one unit type and has one job.

| Zone | Unit | Job | Agent writes? |
|---|---|---|---|
| `personal/` | practice | Practice management (journal, daily, reading) | Never — read-only |
| `atlas/` | object | Object management — single-source identified | Yes |
| `gtd/` | action | Action management — projects, actions, inbox | Yes |
| `intel/` | signal | Signal management — multi-source synthesis | Yes |
| `system/` | source | Source management — raw inputs + activity infra | Yes (hooks) |

**Six meta-skills** for extending the system without code: `/define-object`, `/define-signal`, `/define-source`, `/define-practice`, `/define-tool`, `/define-rule`.

**Three pre-built signals.** `daily-plan` (rich → sparse → cold-start fallback), `weekly-review` (mandatory, active week 1), `vault-improvements` (suppressed first 14 days).

**Eleven semantic event classes** logged via a `PostToolUse` hook to monthly event files in `system/events/{YYYY-MM}.md`.

**Codex rescue** — vault is plain markdown, model-portable. If Claude is down, `/codex-rescue` packages context for OpenAI Codex CLI.

## Install

Three steps, each one-click:

1. Install **Obsidian** (≥1.12.2) from https://obsidian.md/download — drag to `/Applications`, open it once, approve any macOS prompts, then quit.
2. Install **Claude Code** from https://claude.com/claude-code.
3. Run the install:

```bash
curl -fsSL https://raw.githubusercontent.com/BenaliHQ/workdesk-configuration/main/init.sh | bash
```

Defaults: vault at `~/Workdesk-OS/`. Configure via env vars:

| Env var | Default | Purpose |
|---|---|---|
| `WORKDESK_VAULT_PATH` | `~/Workdesk-OS/` | Vault location |
| `WORKDESK_INIT_DRYRUN` | unset | Print the plan, no writes |
| `WORKDESK_INIT_FORCE` | unset | Reuse a non-empty vault per ownership list |
| `WORKDESK_INIT_OPEN` | unset | Launch Obsidian at the new vault on success |

The orchestrator verifies prerequisites (Obsidian present + version + non-quarantined, Claude Code on PATH, Obsidian not currently running), downloads the pinned tarball, runs `bootstrap.sh`, vendors BRAT (the only bundled plugin) with SHA256 verification per artifact, and registers the vault in Obsidian's registry. **No sudo, no Homebrew, no Xcode CLT.** All macOS-native tooling.

Other plugins (surface appearance, calendar, periodic-notes, templater, minimal-settings, custom-sort) are **opt-in via BRAT** from inside Obsidian once the install completes — operators choose what they want, nothing is pre-installed by the WorkDesk OS distribution.

Preview without writing anything:

```bash
WORKDESK_INIT_DRYRUN=1 curl -fsSL https://raw.githubusercontent.com/BenaliHQ/workdesk-configuration/main/init.sh | bash
```

`bootstrap.sh` remains as the lower-level primitive — advanced users can invoke it directly with a path argument — but `init.sh` is the V1.1 user-visible install.

## First session

```bash
cd /path/to/empty-vault
claude
```

Then:

1. `/workdesk-doctor` — verifies hooks, locks, and runtime behavior
2. `/onboarding` — six phases, ~10 minutes, captures your role mix
3. `/daily-ops` — first daily plan
4. `/weekly-review` at end of week 1

## Architecture

| Layer | What | Where |
|---|---|---|
| **Vault content** | Your work | `personal/` `atlas/` `gtd/` `intel/` `system/` |
| **Control plane** | Declarations, scripts, hooks | `config/` (visible) + `.claude` (symlink) |
| **Skills** | Workflow entry points | `config/skills/` |
| **Rules** | Hard constraints | `config/rules/` |
| **Declarations** | Object/signal/source/practice/tool definitions | `config/{objects,signals,sources,practices,tools}/` |

The `config/` directory is the visible source of truth. Claude Code reads through `.claude/` (a symlink) for tool compatibility.

Bootstrap also creates `config/defaults/` — a frozen snapshot of the control plane as it shipped. Treat it as read-only. The `/update` skill 3-way merges `defaults/` (what shipped), `config/` (what you have now), and each new release — keeping your edits, applying release changes to untouched files, and walking you through any conflicts. Editing `defaults/` defeats the merge.

## Extending

Six meta-skills cover everything you'll add over time. Each scaffolds a declaration and creates the corresponding vault folder when needed. Each carries a **detection clause** — a deterministic rule for when Claude should propose creating something, not just when you ask.

| Skill | Scaffolds |
|---|---|
| `/define-object` | Atlas content types (book, vendor, deal, anything structured) |
| `/define-signal` | Intel signal types (briefings, observations) |
| `/define-source` | System source types (bookmark, screenshot, ocr) |
| `/define-practice` | Personal practice types (journal, reading log) |
| `/define-tool` | Claude capabilities (CLI, API, MCP server) |
| `/define-rule` | Behavioral constraints |

`/define-skill`, `/define-agent`, `/define-zone` are explicitly **not** in V1.

## Resilience

- **Codex rescue** — vault content is plain markdown, fully portable. `/codex-rescue` hands the active task to OpenAI Codex with full context.
- **Sparse-data daily-plan** — useful output even with no calendar, no transcripts, three manual notes.
- **Hook fallbacks** — `/workdesk-doctor` chooses `SessionEnd` (preferred) or `Stop` (upserted, one file per session_id) for raw transcript export.

## Vendored components

As of v1.4.0, WorkDesk OS bundles a single Obsidian plugin under [`vendor/plugins/`](vendor/plugins/): **BRAT** (Beta Reviewers Auto-update Tool). BRAT is the gateway — operators install everything else they want (surface appearance, calendar, periodic-notes, templater, minimal-settings, custom-sort, etc.) opt-in from inside Obsidian using BRAT's "Add a beta plugin" command. BRAT's release artifacts (`main.js`, `manifest.json`, `styles.css`) are vendored at a pinned upstream tag, with SHA256s recorded in `vendor/plugins/obsidian42-brat/UPSTREAM.md` and verified by `init.sh` at install time. The upstream `LICENSE` is preserved alongside the artifacts.

| Plugin | Upstream | Tag | License |
|---|---|---|---|
| BRAT (`obsidian42-brat`) | [TfTHacker/obsidian42-brat](https://github.com/TfTHacker/obsidian42-brat) | `2.0.4` | MIT |

Updates to BRAT itself flow through `scripts/refresh-vendored-plugins.sh` plus a workdesk-os release. Updates to plugins installed *via* BRAT flow automatically through BRAT — operators get new releases on next Obsidian launch without re-installing.

### Suggested opt-in plugins

Plugins previously bundled in WorkDesk OS that operators may want to install via BRAT after first launch (use BRAT's "Add a beta plugin" command and paste the GitHub repo):

- [BenaliHQ/workdesk-operating-system](https://github.com/BenaliHQ/workdesk-operating-system) — the WorkDesk OS visual surface (zones, command palette, quick capture)
- [SilentVoid13/Templater](https://github.com/SilentVoid13/Templater) — advanced templating (required if you want `<% tp.* %>` syntax in templates beyond the core Daily Notes `{{date}}`)
- [kepano/obsidian-minimal-settings](https://github.com/kepano/obsidian-minimal-settings) — Minimal theme configuration UI
- [SebastianMC/obsidian-custom-sort](https://github.com/SebastianMC/obsidian-custom-sort) — custom file-explorer sorting
- [liamcain/obsidian-calendar-plugin](https://github.com/liamcain/obsidian-calendar-plugin) — sidebar calendar
- [liamcain/obsidian-periodic-notes](https://github.com/liamcain/obsidian-periodic-notes) — weekly/monthly/yearly notes

## License

MIT. Fork it, ship it, make it yours.

The bundled BRAT plugin retains its own license. See `vendor/plugins/obsidian42-brat/LICENSE` and `vendor/plugins/obsidian42-brat/UPSTREAM.md`.

## Source

Plan: [BenaliHQ/workdesk-os-internal/plans/workdesk-os-v1.md](https://github.com/BenaliHQ/workdesk-os-internal). Codex variant: [BenaliHQ/workdesk-os-codex](https://github.com/BenaliHQ/workdesk-os-codex).
