# Workdesk Core

Workdesk Core turns what you save, record and write into one linked body of context.

This folder holds the program. It is Python 3, standard library only, and runs on the Python that ships with macOS.

## Layout

| Path | What |
|---|---|
| `bin/wd` | The command. |
| `wd/` | The program. |
| `declarations/` | One file for each object type and each source kind: where it lives in a vault and what a note of it holds. |
| `product/` | What `wd init` copies into a new vault: the rulebook, the skills, the nine sample notes, and the colors and link settings for Obsidian. |
| `budgets.json` | The limits from the contract's Budgets table. |
| `tests/` | The tests and the runner. |
| `tests/stage<N>_finish.py` | One finish test per stage, written before the stage is built. |

## The command

```
core/bin/wd --help
```

A command that is not built yet says so, names the package that builds it, and returns a failure code.

## The vault it works on

Workdesk Core works on a vault laid out like this:

```
sources/    recordings/  links/  sessions/  captures/
objects/    people/  companies/  projects/  terms/  concepts/
            meetings/  decisions/  quotes/
writing/
signals/    briefs/  syntheses/
AGENTS.md   CLAUDE.md   status.md
```

An object's type is decided by its home folder. A project is one plain note in `objects/projects/`. The homes are written down once, in `declarations/`, and `wd/places.py` reads them from there.

`declarations/objects/<type>.json` holds `home`, `linkable`, `name-from`, `required-keys`, `sections` and `summary-max-words`. `declarations/sources/<kind>.json` holds `kind`, `home` and `required-keys`. The calendar is read live and has no files, so its home is null.

## Making a vault

```
core/bin/wd init <vault>
core/bin/wd init <vault> --samples
```

`wd init` makes the folders above, copies `AGENTS.md`, `CLAUDE.md` and the four skills (into `.claude/skills/` and `.agents/skills/`), and writes the Obsidian settings. It finishes by writing `status.md`, the way `wd status` does, so a new vault has all three root files. It refuses a path that exists and is not empty, and a path that is a link, and changes nothing there. It writes nothing outside the folder it is given and nothing under `writing/`.

`--samples` adds nine made-up notes from `product/samples/`: one of each object type and one recording, all marked `sample: true` and linked to each other. Every history line and every current fact in them points at a passage of the sample recording.

```
core/bin/wd graph-setting <vault> --dry-run
core/bin/wd graph-setting <vault> --apply
```

`wd graph-setting` owns five keys in two files and leaves every other key alone:

| File | Key | Value |
|---|---|---|
| `.obsidian/graph.json` | `colorGroups` | One color for each object type, picked by its home folder. |
| `.obsidian/graph.json` | `search` | Hides everything under `sources/` and `signals/briefs/` at the top of the vault, and the three root files, and nothing else. |
| `.obsidian/app.json` | `alwaysUpdateLinks` | `true`: a rename in Obsidian carries every link with it. |
| `.obsidian/app.json` | `newLinkFormat` | `absolute`: a new link is written with its full path. |
| `.obsidian/app.json` | `useMarkdownLinks` | `false`: links are written in double brackets. |

The colors and the three link settings are in `product/obsidian.json`. `--dry-run` prints what would change and writes nothing. `--apply` writes through a hidden temporary file with a name of its own, and a rename. It refuses when `.obsidian` or either settings file is a link. Close the graph view in Obsidian before `--apply`. An open graph keeps its own copy of these settings and can save it back over the file.

The filter is five terms, each a regular expression tied to the start of the path:

```
-path:/^sources\// -path:/^signals\/briefs\// -path:/^AGENTS\.md$/ -path:/^CLAUDE\.md$/ -path:/^status\.md$/
```

Obsidian's plain `path:` and `file:` match their words anywhere in a path, so `-file:status.md` would also hide `writing/project-status.md`. Whether Obsidian hides exactly these is proven by looking at the graph, not by a test.

Built so far:

```
core/bin/wd check <vault>
core/bin/wd check --measure <vault>
core/bin/wd status <vault> --dry-run
core/bin/wd status <vault> --apply
```

`wd check` checks every note an agent wrote. Every object against its type's declaration: the `type` key matches the home, every required key is there, the opening keys are in order, the name is the first heading and is used once, and each `##` section is one the type has. The summary is three lines and 60 words at most. Every link in an object or a synthesis goes somewhere, a link to a passage only if that file has that marker. No link to a person shows one word alone. No object is left without a link in or out. It prints a short table, saves `check.json` in machine state, and returns 0 only when there are no problems. It never writes inside the vault.

A declaration's `sections` lists the sections a note of that type may carry. Any type may leave out `Currently` and `History` while they would be empty. Every other listed section is always there, so a meeting always has `Decisions`, `Promises` and `Detail`.

An object is unlinked when it has no link to or from another note that shows in the graph: an object, a synthesis or the owner's writing. A link to or from a source does not count, and neither does a source's `produced` list, a brief, or a file at the top of the vault. The rule is written once, in `wd/graph.py`, and the check, the measure and the status page all use it.

`wd status` writes `status.md` at the top of the vault: the notes in each home, what the check found, and the words a session loads at its start in Claude Code and in Codex. Each of those is split into what the vault adds and what comes from outside it, which is what the same user loads when a session starts in an empty folder. The limit from `budgets.json` is shown beside them. The page holds counts and note paths and nothing a note says. `--dry-run` prints the page and writes nothing. `--apply` writes the one file, through a temporary file and a rename.

```
core/bin/wd score <vault>
```

A throwaway scorer from stage 0, in `score/`. It takes every existing link that shows a full name, strips its brackets in a scratch copy under machine state, runs the matcher, and counts how often the matcher puts the same link back. It saves `score.json`. It never writes inside the vault and never opens `writing/`, the operator's own folder.

`wd check --measure` counts what is in a vault today: notes in each home, links with a missing target, objects with no link in or out, people without a full name, meetings whose `source` points at a file that is missing, sources whose `produced` list is empty, and the words each agent loads at the start of a session. It prints a table and saves `measure.json` in machine state. It never writes inside the vault.

`wd` keeps its machine state in `~/.local/state/workdesk/core/`. Set `WD_STATE_DIR` to point it somewhere else, so a test can run on a scratch folder.

## Tests

```
/usr/bin/python3 core/tests/run.py
```

Tests run with outside packages switched off. The plain form works too:

```
python3 -m unittest discover -s core/tests
```

The budget test checks the word and rule limits the contract sets on itself. The contract page is not in this repository, so point the runner at it:

```
/usr/bin/python3 core/tests/run.py --contract <file>
```

Without it, the checks on the page are reported as NOT RUN.

A stage's finish test fails until the stage is built:

```
/usr/bin/python3 core/tests/run.py --finish 0 --vault <vault> --scorecard <note> --build-log <note>
/usr/bin/python3 core/tests/run.py --finish 1 --new-vault <the new vault> --build-log <note>
```

Stage 1's finish test looks for the new vault at `~/Workdesk` when `--new-vault` is not given.

The test vault in `tests/fixtures/vault/` and the twelve cases beside it are in the layout above. `tests/fixtures/README.md` lists what is left wrong in the vault on purpose.

A finish check that cannot run is reported as NOT RUN and counts as a failure.
