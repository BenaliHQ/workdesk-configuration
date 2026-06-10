# Claude Code Status Line

A modular, configurable status line for Claude Code.

## What it shows

**Line 1** (session info):
```
── ━━━╌╌╌╌╌╌╌╌╌╌╌╌╌ 23% | Opus | DEFAULT | 8m0s | 207K ↓  8K ↑ | $1.37
```

**Line 2** (environment):
```
── 5h:12% | 7d:3% | 13 skills | 2 mcp | khalils-vault
```

**Line 3** (optional, full mode only):
```
── FILES: CLAUDE.md, ~CLAUDE.md, 8 rules
```

Segments appear/hide based on data availability (agent name only shows when a subagent is active, worktree only when in a worktree, rate limits only when data is present).

## Setup

**In a WorkDesk OS vault: no setup.** This directory ships at `config/statusline/` and the vault's `config/settings.json` (project-level Claude Code settings) wires it up automatically — the `statusLine` command there extracts the vault path from the stdin JSON (`workspace.project_dir`) and runs this script. `/update` keeps both in sync.

Requires `jq` (ships with recent macOS at `/usr/bin/jq`; otherwise `brew install jq` — the statusline prints an install hint instead of rendering until it's present).

To use it outside a WorkDesk vault:

1. Copy the `statusline/` directory to `~/.claude/statusline/`
2. Make it executable: `chmod +x ~/.claude/statusline/statusline.sh`
3. Add to `~/.claude/settings.json`:
   ```json
   {
     "statusLine": {
       "type": "command",
       "command": "/path/to/home/.claude/statusline/statusline.sh"
     }
   }
   ```
4. Restart Claude Code

## Configuration

Create `~/.claude/statusline.conf` to override defaults:

```bash
# Choose which sections to display (order matters)
STATUSLINE_SECTIONS="context,env,tokens,cost,rate,skills,mcps,agent,dir"

# Theme: dark | light | minimal
STATUSLINE_THEME="dark"

# Show loaded context files on line 3
STATUSLINE_FILES_ENABLED=true

# Show a daily quote on line 3
STATUSLINE_QUOTE_ENABLED=true

# Context bar width: auto | 8 | 12 | 16 ...
STATUSLINE_CONTEXT_BAR_WIDTH="auto"
```

See `statusline.defaults.conf` for all options.

## Available sections

| Section   | What it shows | Line |
|-----------|--------------|------|
| `context` | Context window bar + percentage | 1 |
| `env`     | Model, permissions, session time | 1 |
| `tokens`  | Input/output token counts | 1 (full) or 2 |
| `cost`    | Session cost in USD | 1 |
| `rate`    | 5-hour and 7-day rate limit usage | 2 |
| `skills`  | Number of loaded skills | 2 |
| `mcps`    | Number of MCP servers | 2 |
| `agent`   | Active agent name + worktree | 1 (when active) |
| `dir`     | Working directory name | 2 |
| `files`   | Loaded context files list | 3 (full) or 2 |
| `quote`   | Quote of the day | 3 |

## Themes

- **dark** — 24-bit color, designed for dark terminals (default)
- **light** — 24-bit color, designed for light terminals
- **minimal** — 16-color ANSI, works everywhere

Create your own: copy `themes/dark.sh`, change the color values, set `STATUSLINE_THEME="mytheme"`.

## Adding a section

1. Create `sections/mysection.sh`
2. Define a `render_mysection()` function
3. Use `append_line1`, `append_line2`, or `append_line3` to add content
4. Add `mysection` to `STATUSLINE_SECTIONS` in your config

```bash
# sections/mysection.sh
render_mysection() {
    append_line2 "${GREEN}hello${R}"
}
```

## Architecture

```
statusline/
  statusline.sh              # Main entrypoint
  statusline.defaults.conf   # Default config (don't edit)
  lib/
    parse.sh                 # JSON parsing (single jq call)
    helpers.sh               # Formatting functions
    layout.sh                # Width detection, line buffers, bar rendering
    cache.sh                 # File-based caching for expensive lookups
  sections/                  # One file per section
  themes/                    # Color definitions
  cache/                     # Runtime cache (gitignored)
  tools/                     # Background update scripts
```

## Requirements

- bash 4+
- jq
