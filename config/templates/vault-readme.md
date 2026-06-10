# Welcome to your WorkDesk

This vault is your WorkDesk OS — Obsidian + Claude Code wired together as one knowledge-work environment.

If you haven't yet, run `/onboarding` in the terminal panel to get oriented. It's a calm five-step walk-through that gets your profile set up and ends with either a real project or your first daily note.

## Zone tutorials

Six short videos — one per zone. Watch in order, or jump to any.

- [`personal/` — your space](https://supercut.ai/share/benali/L7AMBy2jCo2GPqw2S66eRU)
- [`atlas/` — what you manage](https://supercut.ai/share/benali/o8GxKPEpYFDBmSxuP79vRW)
- [`GTD/` — actions and projects](https://supercut.ai/share/benali/tTmAzLhiuqHSuE2v1FdINX)
- [`intel/` — what Claude observes](https://supercut.ai/share/benali/Sb94l7TDegwgPHsoniOZZT)
- [`system/` — sources and intake](https://supercut.ai/share/benali/vlxgd2Vpz9pQCjuUeS0x79)
- [`config/` — the harness](https://supercut.ai/share/benali/dBzNlZl8Yvwk3JT877kJ4F)

## Quick reference

- Run `/onboarding` to redo the orientation anytime
- Run `/workdesk-doctor` if anything feels off
- Each WorkDesk skill introduces itself the first time you run it — explore them in `config/skills/` when you're ready

## Where things live

| Zone | What | Who writes |
|---|---|---|
| `personal/` | Your space — daily notes, journal, reading | You only. Claude never writes here. |
| `atlas/` | Managed objects — people, decisions, meetings | Claude, from your input |
| `GTD/` | Actions and projects (David Allen shape) | Claude, from your input |
| `intel/` | Claude's observations — briefings, research, vault improvements | Claude, independently (lower trust) |
| `system/` | Sources — transcripts, bookmarks, session logs, intake | Mostly automated |
| `config/` | The harness — skills, hooks, state, templates | WorkDesk itself (invisible by default) |

## How processing works

Everything new lands in `system/_intake/` first. From there it gets processed and routed to the right zone. Objects in `atlas/` get updated or created from what arrives — that's how meetings become meeting notes, transcripts produce people and decisions, and bookmarks become reading.

## Need help

- Repo: https://github.com/BenaliHQ/workdesk-configuration
- Issues: file at the repo
