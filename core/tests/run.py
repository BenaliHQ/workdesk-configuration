#!/usr/bin/python3
"""Test runner for Workdesk Core.

    /usr/bin/python3 core/tests/run.py
        Run the tests.

    /usr/bin/python3 core/tests/run.py --contract <file>
        Also run the budget test against the contract page.

    /usr/bin/python3 core/tests/run.py --finish 0 \
            --vault <vault> --scorecard <note> --build-log <note>
        Run a stage's finish test. It fails until the stage is built.

Tests run with outside packages switched off, so anything that is not
in the standard library fails here before it fails on someone's Mac.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

TESTS = Path(__file__).resolve().parent
CORE = TESTS.parent
DEFAULT_STATE = "~/.local/state/workdesk/core"


def main(arguments=None):
    parser = argparse.ArgumentParser(description="Run the Workdesk Core tests.")
    parser.add_argument("--contract", help="the contract page, for the budget test")
    parser.add_argument("--finish", metavar="STAGE", type=int,
                        help="run this stage's finish test instead")
    parser.add_argument("--vault", help="finish test: the vault to check")
    parser.add_argument("--state", default=DEFAULT_STATE,
                        help="finish test: the machine state folder")
    parser.add_argument("--scorecard", help="finish test: the scorecard note")
    parser.add_argument("--build-log", help="finish test: the build log")
    options = parser.parse_args(arguments)

    environment = dict(os.environ)
    # -I ignores the user's Python settings. -S switches off outside packages.
    command = [sys.executable, "-I", "-S", "-m", "unittest", "discover"]

    if options.finish is None:
        if options.contract:
            environment["WD_CONTRACT"] = options.contract
        command += ["-s", str(TESTS), "-t", str(CORE), "-p", "test_*.py", "-v"]
    else:
        finish = TESTS / "finish"
        name = "stage%d.py" % options.finish
        if not (finish / name).is_file():
            print("There is no finish test for stage %d." % options.finish,
                  file=sys.stderr)
            return 2
        for setting, value in (
            ("WD_FINISH_VAULT", options.vault),
            ("WD_FINISH_STATE", options.state),
            ("WD_FINISH_SCORECARD", options.scorecard),
            ("WD_FINISH_BUILD_LOG", options.build_log),
        ):
            if value:
                environment[setting] = value
            else:
                environment.pop(setting, None)
        command += ["-s", str(finish), "-t", str(finish), "-p", name, "-v"]

    return subprocess.call(command, env=environment)


if __name__ == "__main__":
    sys.exit(main())
