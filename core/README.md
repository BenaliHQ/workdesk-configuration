# Workdesk Core

Workdesk Core turns what you save, record and write into one linked body of context.

This folder holds the program. It is Python 3, standard library only, and runs on the Python that ships with macOS.

## Layout

| Path | What |
|---|---|
| `bin/wd` | The command. |
| `wd/` | The program. |
| `budgets.json` | The limits from the contract's Budgets table. |
| `tests/` | The tests and the runner. |
| `tests/stage<N>_finish.py` | One finish test per stage, written before the stage is built. |

## The command

```
core/bin/wd --help
```

A command that is not built yet says so and returns a failure code.

Built so far:

```
core/bin/wd check --measure <vault>
```

It counts what is in a vault today: notes in each home, links with a missing target, objects nothing links to, people without a full name, meetings with a missing source, sources not processed, and the words each agent loads at the start of a session. It prints a table and saves `measure.json` in machine state. It never writes inside the vault.

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
```

A finish check that cannot run is reported as NOT RUN and counts as a failure.
