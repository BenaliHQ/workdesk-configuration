---
paths:
  - "**/*.md"
---

# Obsidian CLI — Tool Reference

Command-line interface for reading, searching, and managing notes in the Obsidian vault. Requires the Obsidian desktop app to be running.

## Access Method

CLI binary: `OBS="/Applications/Obsidian.app/Contents/MacOS/Obsidian"`

## Common Commands

| Command | What it does | Example |
|---|---|---|
| `$OBS read file="note-name"` | Read a note by wikilink name | `$OBS read file="transcript-processing-sop"` |
| `$OBS search query="term" limit=10` | Keyword search across vault | `$OBS search query="pipeline review" limit=10` |
| `$OBS daily:read` | Read today's daily note | `$OBS daily:read` |
| `$OBS unresolved total` | Count broken wikilinks | `$OBS unresolved total` |
| `$OBS orphans` | List notes with no backlinks | `$OBS orphans` |
| `$OBS deadends` | List notes with no outgoing links | `$OBS deadends` |

## Known Limitations

- Requires the Obsidian desktop app to be running. If the app is closed, all commands will fail.
- Search results are limited by the `limit` parameter — increase it for broader searches.

## Common Mistakes

- Forgetting to set the `OBS` variable before running commands. Always define it first or use the full path.
- Using file paths instead of wikilink names with the `read` command — use the note name without extension or path.

## Fallback

If Obsidian CLI is unavailable (app not running), fall back to Read/Glob/Grep for vault files at `~/<primary-vault>/`.

## Authentication

None required. The CLI communicates with the running Obsidian app directly.
