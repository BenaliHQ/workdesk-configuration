# Workdesk Core

Workdesk Core turns what you save, record and write into one linked body of context.

This folder holds the program. It is Python 3, standard library only, and runs on the Python that ships with macOS.

## Layout

| Path | What |
|---|---|
| `bin/wd` | The command. |
| `wd/` | The program. |
| `declarations/` | One file for each object type and each source kind: where it lives in a vault and what a note of it holds. |
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

Built so far:

```
core/bin/wd check --measure <vault>
```

```
core/bin/wd score <vault>
```

A throwaway scorer from stage 0, in `score/`. It takes every existing link that shows a full name, strips its brackets in a scratch copy under machine state, runs the matcher, and counts how often the matcher puts the same link back. It saves `score.json`. It never writes inside the vault and never opens `writing/`, the operator's own folder.

`wd check --measure` counts what is in a vault today: notes in each home, links with a missing target, objects nothing links to, people without a full name, meetings whose `source` points at a file that is missing, sources whose `produced` list is empty, and the words each agent loads at the start of a session. It prints a table and saves `measure.json` in machine state. It never writes inside the vault.

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
