# Test fixtures

Everything here is made up. No real person, company or address appears.

## `vault/`

A small vault of 44 notes, owned by a made-up person called Robin Hale. Most notes are in the format Workdesk Core writes. A few are left wrong on purpose, so the measuring command has something to find:

| On purpose | Where |
|---|---|
| A person with one word in the heading | `atlas/people/marcus.md` |
| A meeting whose transcript was never saved | `atlas/meetings/2026-11-09-bluepeak-sync.md` |
| A link to a concept that was never written | `intel/syntheses/2026-11-10-rollouts-go-wrong-at-handoffs.md` |
| Two older sources that were never processed | `system/bookmarks/2026-11-02-why-checklists-work.md`, `system/intake/2026-11-11-voice-note.md` |
| Two objects nothing links to | `atlas/people/marcus.md`, `gtd/projects/reading-room/brief.md` |

Two people are called Nick. One person is private.

## `cases/`

Twelve things that could arrive, each with the right outcome written down. A case folder has `input/` (what arrived) and `expected.json` (what must exist afterwards and what must not). Each `expected.json` has:

- `why`: the rule of the contract the case rests on.
- `exists` and `absent`, each with three lists:
  - `objects`: `path` and `type`, and `private` where it matters.
  - `links`: `from` and `to`, and `shown` for the words the link shows.
  - `history`: `on` (the object), `text`, and where known `basis` and `source`.

The cases take the vault as their starting point.

## `home/`

A made-up home folder with Claude Code and Codex instructions, rules and skills. Runs on the test vault use it, so the count of words loaded into a session is the same on every machine.

## `answers.json`

The known results of the commands on the test vault. The `measure` part was worked out by hand from the table above.
