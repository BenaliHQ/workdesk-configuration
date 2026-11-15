# Test fixtures

Everything here is made up. No real person, company or address appears.

## `vault/`

A small vault of 45 notes in the new vault's layout (`objects/`, `signals/`, `sources/` and the root files), owned by a made-up person called Robin Hale. Each note is in the format Workdesk Core writes: an object follows its type's declaration in `core/declarations/`, and every source has the source frontmatter and a marker on each passage. A few things are left wrong on purpose, so the measuring command and the check have something to find:

| On purpose | Where |
|---|---|
| A person with one word in the heading, and no opening keys but `type` | `objects/people/marcus.md` |
| A meeting whose recording was never saved, so its `source` points nowhere | `objects/meetings/2026-11-09-bluepeak-sync.md` |
| A link to a concept that was never written | `signals/syntheses/2026-11-10-rollouts-go-wrong-at-handoffs.md` |
| Three sources that have produced nothing | `sources/links/2026-11-02-why-checklists-work.md`, `sources/links/2026-11-08-how-warehouses-count.md`, `sources/captures/2026-11-11-voice-note.md` |
| One object with no link in or out | `objects/people/marcus.md` |
| A meeting that lost its `## Promises` heading | `objects/meetings/2026-11-09-bluepeak-sync.md` |
| A stray second note about the Reading Room, filed among the terms, with eight things wrong (listed below) | `objects/terms/reading-room.md` |

Two people are called Nick. One person is private. Her meeting is private too, and no recording of it was kept, so its `source` is empty.

A project is one plain note in `objects/projects/`, named by its heading.

A meeting always has its three sections, `## Decisions`, `## Promises` and `## Detail`. One with nothing in it keeps its heading. The Bluepeak sync is the one meeting that breaks this, on purpose. A decision has one history line, from the day it was made. A quote is dated, so its `date` is one of the keys its declaration asks for.

The project `objects/projects/reading-room.md` is a correct note. Nothing links to it, and it links to a concept, so it has a link out and is not left unlinked.

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

The known results of the commands on the test vault. The `measure` part was worked out by hand from the table above. A source counts as having produced nothing when its `produced` list is empty. An object counts as unlinked when it has no link to or from another object, a synthesis or the owner's writing. A link to or from a source does not count, and neither does a source's `produced` list.

The `check` part is what `wd check` must find, worked out by reading the notes: 13 problems.

| Kind | Count | Where | What is wrong |
|---|---|---|---|
| `missing-key` | 1 | `objects/people/marcus.md` | No `name`, `aliases` or `private`. One problem for the note, however many keys are missing. |
| `unlinked` | 1 | `objects/people/marcus.md` | No link in or out. |
| `missing-section` | 1 | `objects/meetings/2026-11-09-bluepeak-sync.md` | No `## Promises`. |
| `link-goes-nowhere` | 3 | `objects/meetings/2026-11-09-bluepeak-sync.md` | Its `source` names a recording that was never saved. |
| | | `signals/syntheses/2026-11-10-rollouts-go-wrong-at-handoffs.md` | A link to a concept that was never written. |
| | | `objects/terms/reading-room.md` | A link to passage `^p0009` of an article that has three passages. |
| `wrong-type` | 1 | `objects/terms/reading-room.md` | `type: project` in the terms home. |
| `key-order` | 1 | `objects/terms/reading-room.md` | `name` is written before `type`. |
| `name-not-heading` | 1 | `objects/terms/reading-room.md` | The name is Reading Room. The heading is The reading room. |
| `name-not-unique` | 1 | `objects/terms/reading-room.md` | The project already has the name Reading Room. |
| `unknown-section` | 1 | `objects/terms/reading-room.md` | `## Notes`. A term has only `## History`. |
| `summary-too-long` | 1 | `objects/terms/reading-room.md` | Four lines. The limit is three. |
| `first-name-link` | 1 | `objects/terms/reading-room.md` | A link to a person that shows one word. |

Every other object follows its declaration, every other link goes somewhere, and every passage a note cites is marked in its source.

The `score` part is the count of links in the vault that show a full name: 41 to people, 12 to companies, 9 to projects, 2 to terms and 4 to concepts. A test counts them a second way, with a plain search, and the two must agree.
