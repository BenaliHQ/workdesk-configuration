# Test fixtures

Everything here is made up. No real person, company or address appears.

## `vault/`

A small vault of 44 notes in the new vault's layout (`objects/`, `signals/`, `sources/` and the root files), owned by a made-up person called Robin Hale. Each note is in the format Workdesk Core writes: an object follows its type's declaration in `core/declarations/`, and every source has the source frontmatter and a marker on each passage. A few things are left wrong on purpose, so the measuring command has something to find:

| On purpose | Where |
|---|---|
| A person with one word in the heading, and no opening keys but `type` | `objects/people/marcus.md` |
| A meeting whose recording was never saved, so its `source` points nowhere | `objects/meetings/2026-11-09-bluepeak-sync.md` |
| A link to a concept that was never written | `signals/syntheses/2026-11-10-rollouts-go-wrong-at-handoffs.md` |
| Three sources that have produced nothing | `sources/links/2026-11-02-why-checklists-work.md`, `sources/links/2026-11-08-how-warehouses-count.md`, `sources/captures/2026-11-11-voice-note.md` |
| Two objects nothing links to | `objects/people/marcus.md`, `objects/projects/reading-room.md` |

Two people are called Nick. One person is private. Her meeting is private too, and no recording of it was kept, so its `source` is empty.

A project is one plain note in `objects/projects/`, named by its heading.

A meeting always has its three sections, `## Decisions`, `## Promises` and `## Detail`. One with nothing in it keeps its heading. A decision has one history line, from the day it was made. The quote keeps a `date` beside the keys its declaration asks for.

## `cases/`

Twelve things that could arrive, each with the right outcome written down. A case folder has `input/` (what arrived) and `expected.json` (what must exist afterwards and what must not). Each `expected.json` has:

- `why`: the rule of the contract the case rests on.
- `exists` and `absent`, each with three lists:
  - `objects`: `path` and `type`, and `private` where it matters.
  - `links`: `from` and `to`, and `shown` for the words the link shows. `"in": "attendees"` means the link in the meeting's attendee list, and nowhere else.
  - `history`: `on` (the object), `text`, and where known `basis` and `source`.

- `private_words`, where a source is private: words that must never reach a summary, a synthesis or a brief.

The cases take the vault as their starting point.

## `home/`

A made-up home folder with Claude Code and Codex instructions, rules and skills. Runs on the test vault use it, so the count of words loaded into a session is the same on every machine.

## `answers.json`

The known results of the commands on the test vault. The `measure` part was worked out by hand from the table above. A source counts as having produced nothing when its `produced` list is empty.

The `score` part is the count of links in the vault that show a full name: 41 to people, 12 to companies, 9 to projects, 2 to terms and 4 to concepts. A test counts them a second way, with a plain search, and the two must agree.
