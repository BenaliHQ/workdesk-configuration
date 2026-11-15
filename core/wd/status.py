"""`wd status <vault>`: write the status page, `status.md`.

The page says what is in the vault, what the check found, and how many
words a session loads at its start. It holds counts and note paths and
nothing a note says, so nothing private reaches it. It has no opening
block and no links, so it never shows in the graph.

`--dry-run` prints the page and writes nothing. `--apply` writes
`status.md` at the top of the vault, through a hidden temporary file
and a rename, and writes nothing else.
"""

import datetime
import json
import os
import tempfile
from pathlib import Path

from wd import check, measure, notes, places

PAGE = "status.md"
BUDGETS = Path(__file__).resolve().parents[1] / "budgets.json"
SESSION_LIMIT = "Words loaded into a session, everything counted"
# How many problems the page lists. `wd check` shows every one.
FIRST_FEW = 5
WRITTEN = "Written on "
USAGE = "usage: wd status <vault> --dry-run\n       wd status <vault> --apply"


class StatusError(Exception):
    """The page could not be made or could not be written."""


def session_limit():
    """The most words a session may load, from the contract's Budgets table."""
    try:
        limit = json.loads(BUDGETS.read_text(encoding="utf-8"))[SESSION_LIMIT]
    except (OSError, ValueError, KeyError, TypeError):
        limit = None
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise StatusError("%s does not give the session limit." % BUDGETS)
    return limit


def session_words(root, home):
    """For each runtime: the words a session loads in all, from the vault, and from outside it.

    Words from outside are what the same home folder loads when a
    session starts in an empty folder. The rest is what the vault adds.
    That can be below zero, when the vault's settings switch off a
    plugin the user has switched on.
    """
    def totals(folder):
        return {
            runtime: sum(parts.values())
            for runtime, parts in measure.session_load(folder, home).items()
        }

    inside = totals(root)
    with tempfile.TemporaryDirectory() as empty:
        outside = totals(empty)
    return {
        runtime: {
            "total": inside[runtime],
            "vault": inside[runtime] - outside[runtime],
            "outside": outside[runtime],
        }
        for runtime in inside
    }


def number(count):
    return format(count, ",")


def load_line(label, words, limit):
    line = "- %s: %s words in all. %s from the vault and %s from outside it." % (
        label, number(words["total"]), number(words["vault"]), number(words["outside"])
    )
    if words["total"] <= limit:
        return line + " Under the limit."
    return line + " Over the limit by %s." % number(words["total"] - limit)


def page(report, counts, load, limit, written):
    """The words of the status page."""
    problems = report["problems"]
    lines = [
        "# Status",
        "",
        "This page is written by a program, `wd status`. Do not edit it by hand. "
        "The next run replaces it.",
        "",
        "%s%s at %s." % (WRITTEN, written.strftime("%Y-%m-%d"), written.strftime("%H:%M:%S")),
        "",
        "## Notes in each home",
        "",
    ]
    lines += ["- %s: %s" % (home, number(count)) for home, count in counts.items()]
    lines += ["", "## What the check found", ""]
    looked_at = check.looked_at(report)
    if not problems:
        lines.append("The check found 0 problems. It looked at %s." % looked_at)
    else:
        lines += [
            "The check found %s %s. It looked at %s."
            % (number(len(problems)), "problem" if len(problems) == 1 else "problems", looked_at),
            "",
            "By kind:",
            "",
        ]
        lines += [
            "- %s: %s" % (label, number(report["by_kind"][kind]))
            for kind, label in check.KINDS if report["by_kind"][kind]
        ]
        few = problems[:FIRST_FEW]
        lines += [
            "",
            "All of them:" if len(few) == len(problems) else "The first %d:" % len(few),
            "",
        ]
        # The note and the kind only. A problem's sentence can quote a
        # note, and nothing a note says belongs on this page.
        lines += ["- `%s`: %s" % (found["note"], check.LABELS[found["kind"]]) for found in few]
        lines += ["", "Run `wd check` to read each one in a sentence."]
    lines += [
        "",
        "## Words a session loads at its start",
        "",
        "The limit is %s words, everything counted." % number(limit),
        "",
    ]
    for runtime, label in measure.RUNTIME_NAMES:
        lines.append(load_line(label, load[runtime], limit))
    lines += [
        "",
        "Words from outside it are what the same user loads when a session starts in an "
        "empty folder: their own instructions, rules, skills and plugins.",
    ]
    for runtime, label in measure.RUNTIME_NAMES:
        words = load[runtime]
        if words["outside"] > limit:
            lines += ["", "In %s the words from outside the vault are over the limit "
                          "before the vault adds anything." % label]
        if words["vault"] < 0:
            lines += ["", "In %s the vault's number is below zero, because the vault's "
                          "settings switch off plugins the user has switched on." % label]
    return "\n".join(lines) + "\n"


def build(root, home, written=None):
    """Read the vault and make the page. Returns (page, files that could not be read)."""
    vault = notes.Vault(root)
    counts = {folder: len(names) for folder, names in measure.homes(vault).items()}
    report = check.examine(vault)
    load = session_words(vault.root, home)
    written = written or datetime.datetime.now().astimezone().replace(microsecond=0)
    return page(report, counts, load, session_limit(), written), report["unreadable"]


def current(path):
    """What is at the page's place now: its bytes, or None when nothing is there."""
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise StatusError("%s is not a plain file, so it was left alone." % path)
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as problem:
        raise StatusError("%s could not be read: %s" % (path, problem))


def write(root, text, before):
    """Put the page in place: a hidden temporary file, then a rename.

    `before` is what was there when the vault was read. If it has
    changed since, someone else wrote it, and nothing is written.
    """
    path = Path(root) / PAGE
    if current(path) != before:
        raise StatusError("%s changed while this ran, so nothing was written." % path)
    scratch = Path(root) / (".%s.%d.tmp" % (PAGE, os.getpid()))
    try:
        scratch.write_text(text, encoding="utf-8")
        os.replace(str(scratch), str(path))
    except OSError as problem:
        try:
            scratch.unlink()
        except OSError:
            pass
        raise StatusError("%s could not be written: %s" % (path, problem))
    return path


def run(arguments, out, err):
    """`wd status <vault> --dry-run` or `--apply`. Returns a code."""
    modes = [argument for argument in arguments if argument in ("--dry-run", "--apply")]
    rest = [argument for argument in arguments if argument not in ("--dry-run", "--apply")]
    if len(modes) != 1 or len(rest) != 1 or rest[0].startswith("-"):
        print(USAGE, file=err)
        return 2
    apply = modes[0] == "--apply"
    root = Path(rest[0]).expanduser()
    if not root.is_dir():
        print("wd status: there is no vault at %s." % root, file=err)
        return 1
    root = root.resolve()
    if apply and not (root / "objects").is_dir():
        print(
            "wd status: %s has no objects folder, so it is not a Workdesk vault. "
            "Nothing was written." % root,
            file=err,
        )
        return 1
    try:
        before = current(root / PAGE) if apply else None
        text, unreadable = build(root, places.home())
        if unreadable:
            print(
                "wd status: %d files or folders could not be read, so the page would "
                "not be right. Nothing was written." % len(unreadable),
                file=err,
            )
            for name in unreadable:
                print("  %s" % name, file=err)
            return 1
        if not apply:
            out.write(text)
            print("wd status: a dry run. Nothing was written.", file=err)
            return 0
        path = write(root, text, before)
    except StatusError as problem:
        print("wd status: %s" % problem, file=err)
        return 1
    print("Wrote %s" % path, file=out)
    return 0
