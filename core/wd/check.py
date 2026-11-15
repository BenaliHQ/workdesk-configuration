"""`wd check <vault>`: is every note an agent wrote in the right shape?

It reads the vault and writes one file, `check.json`, into machine
state. It never writes inside the vault.

What it checks (build spec, S1.4, and contract rules 3, 5 and 9):

1. Every object against its declaration. The note's home decides its
   type. The `type` key says that type. Every required key is there.
   The opening keys are in the build spec's order. On the five types
   linked by name, `name` is the first heading and no two objects share
   a name. Each `##` section is one the declaration lists.
2. The summary, the first paragraph after the title, is three lines
   and 60 words at most.
3. Every link in an object or a synthesis goes somewhere. A link to a
   passage goes somewhere only if that file has that marker.
4. No link to a person shows one word alone.
5. No object is left without a link in or out. See `wd.graph`.

Each problem has the note, a short kind and one plain sentence.
"""

import datetime
import re
from pathlib import Path

from wd import declarations, graph, measure, notes, places

REPORT = "check.json"
# How many problems the command prints. The saved report has them all.
PRINTED = 20

# Build spec, "Object frontmatter": every object opens with these, in
# this order, then the keys its declaration lists.
OPENING_KEYS = ("type", "name", "aliases", "private")
# Contract rule 9 and build spec, "Object body".
SUMMARY_MAX_LINES = 3
# A declaration's `sections` says which sections a note may carry. Any
# type may leave these two out while they would be empty. Every other
# listed section is always there, so a meeting always has Decisions,
# Promises and Detail.
MAY_BE_LEFT_OUT = ("Currently", "History")

# Each kind of problem, with the plain words the table and the status
# page show for it.
KINDS = [
    ("missing-key", "A required key is missing"),
    ("wrong-type", "The type does not match the home"),
    ("key-order", "The opening keys are out of order"),
    ("name-not-heading", "The name is not the first heading"),
    ("name-not-unique", "A name is used by two objects"),
    ("missing-section", "A section that is always there is missing"),
    ("unknown-section", "A section the type does not have"),
    ("summary-too-long", "The summary is too long"),
    ("link-goes-nowhere", "A link goes nowhere"),
    ("first-name-link", "A link to a person shows one word"),
    ("unlinked", "An object has no link in or out"),
]
LABELS = dict(KINDS)
ORDER = {kind: number for number, (kind, _) in enumerate(KINDS)}

SECTION = re.compile(r"^##\s+(.+?)\s*$")
MARKER = re.compile(r"(?:^|[ \t])\^([A-Za-z0-9-]+)[ \t]*$", re.MULTILINE)


def problem(note, kind, sentence):
    return {"note": note, "kind": kind, "sentence": sentence}


def listed(words):
    """`a`, `a and b`, or `a, b and c`."""
    words = list(words)
    if len(words) < 2:
        return "".join(words)
    return "%s and %s" % (", ".join(words[:-1]), words[-1])


def looked_at(report):
    """`8 objects and 1 synthesis`: how many notes the check read."""
    objects, syntheses = report["checked"]["objects"], report["checked"]["syntheses"]
    return "%s %s and %s %s" % (
        format(objects, ","), "object" if objects == 1 else "objects",
        format(syntheses, ","), "synthesis" if syntheses == 1 else "syntheses",
    )


def key_order(declared):
    """The order a type's keys are written in: the opening keys, then its own."""
    required = declared["required-keys"]
    return (
        [key for key in OPENING_KEYS if key in required]
        + [key for key in required if key not in OPENING_KEYS]
    )


def summary(body):
    """The lines of the first paragraph after the title.

    The title is the first heading. A note that goes from its title
    straight to a section has no summary, which is within the limit.
    """
    lines = notes.without_code(body).split("\n")
    start = next(
        (number + 1 for number, line in enumerate(lines) if notes.HEADING.match(line)), 0
    )
    while start < len(lines) and not lines[start].strip():
        start += 1
    end = start
    while end < len(lines) and lines[end].strip() and not notes.HEADING.match(lines[end]):
        end += 1
    return lines[start:end]


def sections(body):
    """The `##` sections of a note, in the order they are written."""
    found = []
    for line in notes.without_code(body).split("\n"):
        match = SECTION.match(line)
        if match:
            found.append(match.group(1))
    return found


def markers(text):
    """Every passage marker in a file: the `p0003` of ` ^p0003` at the end of a block."""
    return set(MARKER.findall(text))


def object_problems(note, kind, declared, text):
    """Everything wrong with one object, judged against its type's declaration."""
    found = []
    keys, body = notes.front(text)
    home = declared["home"]

    missing = [key for key in key_order(declared) if key not in keys]
    if missing and not keys:
        found.append(problem(note, "missing-key", (
            "It has no opening block, so it is missing the %s %s."
            % ("key" if len(missing) == 1 else "keys", listed(missing))
        )))
    elif missing:
        found.append(problem(note, "missing-key", (
            "It is missing the %s %s."
            % ("key" if len(missing) == 1 else "keys", listed(missing))
        )))

    if "type" in keys and keys["type"] != kind:
        found.append(problem(note, "wrong-type", (
            "Its type is \"%s\", but a note in %s is a %s." % (keys["type"], home, kind)
        )))

    # Keys the declaration does not name, such as `email` or `sample`,
    # may sit anywhere. Only the named keys have an order.
    wanted = [key for key in key_order(declared) if key in keys]
    written = [key for key in keys if key in wanted]
    if written != wanted:
        found.append(problem(note, "key-order", (
            "Its opening keys are written %s. The order is %s."
            % (", ".join(written), ", ".join(wanted))
        )))

    if declared["linkable"] and keys.get("name"):
        heading = notes.first_heading(body)
        if not heading:
            found.append(problem(note, "name-not-heading", (
                "Its name is \"%s\", but it has no heading." % keys["name"]
            )))
        elif heading != keys["name"]:
            found.append(problem(note, "name-not-heading", (
                "Its name is \"%s\", but its first heading is \"%s\"."
                % (keys["name"], heading)
            )))

    has = sections(body)
    always = [name for name in declared["sections"] if name not in MAY_BE_LEFT_OUT]
    gone = [name for name in always if name not in has]
    if gone:
        found.append(problem(note, "missing-section", (
            "It has no %s section. A %s always has %s."
            % (listed(gone), kind, listed(always))
        )))
    allowed = "only " + listed(declared["sections"]) if declared["sections"] else "no sections"
    for name in has:
        if name not in declared["sections"]:
            found.append(problem(note, "unknown-section", (
                "It has a section called \"%s\". A %s has %s." % (name, kind, allowed)
            )))

    opening = summary(body)
    count = len(notes.words(" ".join(opening)))
    limit = declared["summary-max-words"]
    if len(opening) > SUMMARY_MAX_LINES or count > limit:
        found.append(problem(note, "summary-too-long", (
            "Its summary has %d lines and %d words. The limit is %d lines and %d words."
            % (len(opening), count, SUMMARY_MAX_LINES, limit)
        )))
    return found


def link_problems(vault, note):
    """Links in one note that go nowhere, and links to a person that show one word.

    The same link written twice in a note is one problem.
    """
    found, nowhere, one_word = [], set(), set()
    people = places.home_of("person")
    for target, part, shown in notes.links(vault.text(note)):
        if not target and not part:
            continue
        written = target + ("#" + part if part else "")
        # A link with no file, such as `[[#^p0003]]`, points into the note itself.
        resolved = vault.resolve(target, note) if target else note
        why = None
        if resolved is None:
            why = "Its link to %s goes nowhere." % written
        elif (part.startswith("^") and resolved.endswith(".md")
              and part[1:] not in markers(vault.text(resolved))):
            why = "Its link to %s goes nowhere: %s has no passage %s." % (
                written, resolved, part)
        if why and written not in nowhere:
            nowhere.add(written)
            found.append(problem(note, "link-goes-nowhere", why))
        if resolved is None or resolved == note or not places.in_home(resolved, people):
            continue
        # With no shown words a link shows its target. A path is not a name.
        words = shown or ("" if "/" in target else target)
        if len(notes.words(words)) == 1 and (target, words) not in one_word:
            one_word.add((target, words))
            found.append(problem(note, "first-name-link", (
                "Its link to %s shows one word, \"%s\". "
                "A link to a person shows the full name." % (target, words)
            )))
    return found


def examine(vault):
    """Check one vault that has been opened. Returns the report."""
    declared = declarations.objects()
    by_note = {}
    names = {}
    checked = []
    for kind, home in places.OBJECT_HOMES:
        for note in vault.notes:
            if not places.in_home(note, home):
                continue
            checked.append(note)
            text = vault.text(note)
            by_note[note] = object_problems(note, kind, declared[kind], text)
            if declared[kind]["linkable"]:
                name = notes.front(text)[0].get("name")
                if name and name in names:
                    by_note[note].append(problem(note, "name-not-unique", (
                        "Its name, \"%s\", is already the name of %s." % (name, names[name])
                    )))
                elif name:
                    names[name] = note
    syntheses = [note for note in vault.notes if places.in_home(note, places.SYNTHESES)]
    for note in checked + syntheses:
        by_note.setdefault(note, [])
        by_note[note] += link_problems(vault, note)
    for note in graph.unlinked_objects(vault):
        by_note[note].append(problem(note, "unlinked", (
            "It has no link to or from another object, a synthesis or your writing."
        )))

    problems = []
    for note in checked + syntheses:
        problems += sorted(by_note[note], key=lambda found: ORDER[found["kind"]])
    return {
        "vault": str(vault.root),
        "run_at": datetime.datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "checked": {"objects": len(checked), "syntheses": len(syntheses)},
        "problems": problems,
        "by_kind": {
            kind: len([found for found in problems if found["kind"] == kind])
            for kind, _ in KINDS
        },
        "unreadable": sorted(set(vault.unreadable)),
    }


def check(root):
    """Check one vault. Returns the report."""
    return examine(notes.Vault(root))


def table(report):
    problems = report["problems"]
    lines = [
        "Checked %s at %s" % (report["vault"], report["run_at"]),
        "It looked at %s." % looked_at(report),
        "",
    ]
    if not problems:
        return "\n".join(lines + ["No problems."])
    lines += ["%d %s" % (len(problems), "problem" if len(problems) == 1 else "problems"), ""]
    counts = [(label, report["by_kind"][kind]) for kind, label in KINDS if report["by_kind"][kind]]
    width = max(len(label) for label, _ in counts)
    lines += [
        "  %s  %s" % (label.ljust(width), format(count, ",").rjust(5)) for label, count in counts
    ]
    last = None
    for found in problems[:PRINTED]:
        if found["note"] != last:
            lines += ["", found["note"]]
            last = found["note"]
        lines.append("  %s" % found["sentence"])
    if len(problems) > PRINTED:
        lines += ["", "And %d more. The saved report has every one." % (len(problems) - PRINTED)]
    return "\n".join(lines)


def run(arguments, out, err):
    """`wd check <vault>`. Returns a code: 0 only when there are no problems."""
    if len(arguments) != 1 or arguments[0].startswith("-"):
        print("usage: wd check <vault>\n       wd check --measure <vault>", file=err)
        return 2
    root = Path(arguments[0]).expanduser()
    if not root.is_dir():
        print("wd check: there is no vault at %s." % root, file=err)
        return 1
    root, state = root.resolve(), places.state_dir().resolve()
    if state == root or root in state.parents:
        print(
            "wd check: machine state is inside the vault (%s). "
            "Nothing was checked, because this command never writes there." % state,
            file=err,
        )
        return 1
    report = check(root)
    saved = measure.save(report, state, REPORT)
    print(table(report), file=out)
    print("\nSaved to %s" % saved, file=out)
    if report["unreadable"]:
        print(
            "wd check: %d files or folders could not be read, so the check is "
            "not complete. They are listed in the saved report."
            % len(report["unreadable"]),
            file=err,
        )
        return 1
    return 1 if report["problems"] else 0
