# Welcome to your WorkDesk

This vault is your WorkDesk OS — Obsidian + Claude Code wired together as one knowledge-work environment.

If you haven't yet, run `/onboarding` in the terminal panel to get oriented. It's a calm five-step walk-through that gets your profile set up and ends with either a real project or your first daily note.

## Zone tutorials

Five short videos — one per zone. Watch in order, or jump to any.

- [`personal/` — your space](#)
- [`atlas/` — what you manage](#)
- [`GTD/` — actions and projects](#)
- [`intel/` — what Claude observes](#)
- [`system/` — sources and intake](#)

*(Video links populated as the videos are recorded.)*

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
