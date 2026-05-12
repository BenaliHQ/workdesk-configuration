---
name: define-tool
description: Meta-skill — scaffold a new tool integration (CLI binary, MCP server, or HTTP API) so Claude can use it. Installs it, writes a tool reference, updates the tool note at config/tools/<slug>.md (flips connected:true on smoke-test pass), and links it from the operator profile.
---

# /define-tool

Tools are how Claude reaches outside the vault. Defining a tool installs it (when possible), documents it, and wires it into the system.

> **Operates under [[type-scaffolding]]** — design every required field, section, and structure deliberately. A type definition is a contract, not a folder layout. Apply the senior-teammate cold-pickup test, mark required vs optional explicitly, and validate by walking a real instance before locking the schema.

## Detection clause

Surface proactively when:
- A workflow has failed ≥2 times in 14 days because of missing capability ("I can't read your Slack" recurring)
- The operator pastes data manually that a tool could fetch (calendar events, emails, transcripts)

Ask: *"You've pasted {data type} from {source} a few times this week. Want to wire it up so I can fetch it directly?"*

## JTBD-first interview

1. **What tool?** Name + purpose — the capability gap it fills.
2. **How does Claude reach it?** CLI binary, MCP server, or HTTP API.
3. **Authentication?** API key (where? always `.env`), OAuth, none.
4. **Common commands?** 5-10 most-used invocations with examples.
5. **Limitations?** What it can't do, what fails silently, what's flaky.
6. **Detection clause** — when should Claude propose using this tool proactively?

## Install

Pick install method based on tool type:

- **CLI** — Run install command (Homebrew, npm, pip, curl). Verify with `which {binary}`.
- **MCP** — Add entry to `.mcp.json` at vault root. Operator restarts Claude Code to load.
- **API** — Add key to `.env` (operator pastes; never commit). Confirm `.gitignore` includes `.env`.

If install fails, document the manual steps and surface to operator.

## Seed the tool note (pre-verification)

If `config/tools/<slug>.md` doesn't already exist (operator may have named the tool in onboarding, in which case it's seeded), create it now with `connected: false`:

```yaml
---
tool: {Tool Name}
slug: {kebab-slug}
category: {comms | meetings | crm | ...}
class: operator-named
connected: false
added-on: {today}
connector: unknown
---
```

The note's body has stub `## What it is`, `## Best practices`, `## Connection notes`, `## Linked use cases` sections. This tracks the tool exists even if smoke verification fails.

## Verify

Run a smoke test command appropriate to the tool. On pass, continue to scaffold. On fail, append to the tool note's `## Connection notes` what failed (one short paragraph), leave `connected: false`, and stop — do not write the tool reference doc. The operator can retry via `/define-tool <name>` later.

## Scaffold the reference (only on smoke pass)

Create `config/rules/tools/{name}.md` (the tool reference doc — usage, commands, limitations):

```markdown
# {Tool Name} — Tool Reference

{One-paragraph description and when to use}

## Access Method

{CLI binary path / MCP server name / API base URL}

## Common Commands

| Command | What it does | Example |
|---|---|---|
| ... | ... | ... |

## Known Limitations

- ...

## Common Mistakes

- ...

## Authentication

{None / API key in .env / OAuth flow}

## Detection clause

{When Claude should propose using this tool proactively}
```

## Flip the tool note connected

After the reference is written:

- Flip `connected: true` on `config/tools/<slug>.md` frontmatter
- Fill in `## Connection notes` with how Claude reaches it (CLI path, MCP server name, env var name)
- Link the tool note from the operator profile's `## Tools in use` section if not already linked

The PostToolUse hook fires `declaration-changed` on the reference write — install is now logged.

## What NOT to do

- Don't commit secrets. `.env` only, `.gitignore` enforced.
- Don't write a tool reference for a tool that isn't installed and verified. Untested docs lie.
- Don't define a tool that overlaps an existing one — check `config/rules/tools/` and `config/tools/` first.
- Don't skip the detection clause. A tool nobody knows when to use is dead weight.
- Don't flip `connected: true` on the tool note before the smoke test passes. The connection state is the system's truth about whether Claude can actually reach the tool.
