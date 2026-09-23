#!/usr/bin/env python3
"""Calculate due signals without weekday gates. Missing/malformed dates stay visible."""
import datetime as dt
import json
import sys
from pathlib import Path

BUILT_IN = (("daily-plan", 1), ("weekly-review", 7), ("vault-improvements", 7))
SCHEDULE_DAYS = {"daily": 1, "weekly": 7}


def declared_signals(signals_dir):
    """Operator-declared signals (config/signals/*.md) with a daily/weekly schedule.

    Lets an operator-local declaration (e.g. one created with /define-signal)
    surface as due without patching this shipped file. Built-ins keep their
    fixed cadence; unreadable or unscheduled declarations are ignored.
    """
    found = []
    builtin = {name for name, _ in BUILT_IN}
    try:
        paths = sorted(Path(signals_dir).glob("*.md"))
    except OSError:
        return found
    for path in paths:
        name = schedule = None
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        if not lines or lines[0].strip() != "---":
            continue
        for line in lines[1:]:
            if line.strip() == "---":
                break
            key, _, value = line.partition(":")
            value = value.strip().strip('"').strip("'")
            if key == "name":
                name = value
            elif key == "schedule":
                schedule = value
        if name and name not in builtin and schedule in SCHEDULE_DAYS:
            found.append((name, SCHEDULE_DAYS[schedule]))
    return found


def due_signals(state, today, declared=()):
    result = []
    for name, days in tuple(BUILT_IN) + tuple(declared):
        row = state.get(name) or {}
        if not isinstance(row, dict):
            row = {}
        try:
            suppressed = dt.date.fromisoformat(str(row.get("suppressed-until")).split("T", 1)[0])
        except ValueError:
            suppressed = None
        if suppressed and today < suppressed:
            continue
        try:
            last = dt.date.fromisoformat(str(row.get("last-fired")).split("T", 1)[0])
        except ValueError:
            last = None
        if last is None or last > today or (today - last).days >= days:
            result.append(name)
    return result

if __name__ == "__main__":
    path = Path(sys.argv[1])
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            raise ValueError("signal state must be an object")
    except (ValueError, OSError) as exc:
        print("Signal state unreadable: " + str(exc), file=sys.stderr)
        sys.exit(2)
    declared = declared_signals(path.resolve().parent.parent / "signals")
    print("\n".join(due_signals(state, dt.date.today(), declared)))
