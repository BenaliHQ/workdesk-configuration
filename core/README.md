# Workdesk Core

Workdesk Core turns what you save, record and write into one linked body of context.

This folder holds the program. It is Python 3, standard library only, and runs on the Python that ships with macOS.

## Layout

| Path | What |
|---|---|
| `bin/wd` | The command. |
| `wd/` | The program. |
| `tests/` | The tests and the runner. |
| `tests/finish/` | One finish test per stage, written before the stage is built. |

## The command

```
core/bin/wd --help
```

A command that is not built yet says so and returns a failure code.

`wd` reads the vault location from `WD_VAULT` and the machine state location from `WD_STATE_DIR`, so every program can run on a copy.

## Tests

```
/usr/bin/python3 core/tests/run.py
```

Tests run with outside packages switched off.

A stage's finish test fails until the stage is built:

```
/usr/bin/python3 core/tests/run.py --finish 0 --vault <vault> --scorecard <note> --build-log <note>
```

A finish check that cannot run is reported as NOT RUN and counts as a failure.
