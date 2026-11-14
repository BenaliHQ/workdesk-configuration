"""`wd score <vault>`: how well would the linker do on the links already there?

A throwaway scorer for stage 0 (build spec, S0.4). It reads each
linkable object's name from its first heading. It takes every existing
link whose shown words are a name of two words or more, strips its
brackets in a scratch copy under machine state, runs the matcher over
the copy, and counts how often the matcher puts the same link back.

It never writes inside the vault, and it never opens the private folder.
"""

import datetime
import json
import os
import re
import shutil
from pathlib import Path

from wd import notes, places

REPORT = "score.json"
SCRATCH = "score-scratch"
PRIVATE = "personal"
EXAMPLES = 10

# The five types that are linked by name (build spec, "Object homes").
LINKABLE = ("person", "company", "term", "concept")
TYPES = ("person", "company", "project", "term", "concept")
LABELS = {"person": "People", "company": "Companies", "project": "Projects",
          "term": "Terms", "concept": "Concepts"}

WIKILINK = re.compile(r"(!?)\[\[([^\[\]\n]+)\]\]")
FENCE = re.compile(r"^\s*(```|~~~)")
HEADING = re.compile(r"^\s{0,3}#{1,6}\s")
CALLOUT_TITLE = re.compile(r"^\s*>\s*\[!")
INLINE_CODE = re.compile(r"`[^`\n]*`")
# What the linker leaves alone inside a line: code, links and embeds
# that are already there, web addresses and comments.
EXISTING_LINK = re.compile(r"!?\[\[[^\[\]\n]+\]\]")
LEFT_ALONE = [
    INLINE_CODE,
    EXISTING_LINK,
    re.compile(r"!?\[[^\]\n]*\]\([^)\n]*\)"),
    re.compile(r"https?://\S+"),
    re.compile(r"%%.*?%%"),
    re.compile(r"<!--.*?-->"),
]


def project_name(heading):
    """Build spec, "Names": the heading without a trailing Brief and its dash or colon."""
    # A hyphen, an en dash, an em dash or a colon.
    return re.sub(r"\s*[-\u2013\u2014:]?\s*Brief$", "", heading).strip()


def linkable(vault):
    """(type, note) for every object that is linked by name."""
    homes = dict(places.OBJECT_HOMES)
    found = [
        (kind, name) for kind in LINKABLE
        for name in vault.notes if places.in_home(name, homes[kind])
    ]
    return found + [("project", name) for name in vault.notes if places.is_project_brief(name)]


def workplace(vault):
    """The notes the linker may write in: the object homes and syntheses."""
    found = []
    for _, folder in places.OBJECT_HOMES:
        found += [name for name in vault.notes if places.in_home(name, folder)]
    found += [name for name in vault.notes if places.is_project_brief(name)]
    return found + [name for name in vault.notes if places.in_home(name, places.SYNTHESES)]


def names(vault):
    """Each name and the object it belongs to, and the names two objects share.

    A name two objects share is not linked. A person with one word in
    the heading has no full name, so is not linked either.
    """
    known, shared = {}, set()
    for kind, note in linkable(vault):
        _, body = notes.front(vault.text(note))
        name = notes.first_heading(body)
        if kind == "project":
            name = project_name(name)
        if not name or (kind == "person" and len(name.split()) < 2):
            continue
        if name in known:
            shared.add(name)
        else:
            known[name] = (note, kind)
    for name in shared:
        del known[name]
    return known, sorted(shared)


def name_pattern(known):
    """Exact names, whole words, the longest first."""
    if not known:
        return None
    longest_first = sorted(known, key=lambda name: (-len(name), name))
    return re.compile(
        r"(?<![^\W_])(?:%s)(?![^\W_])" % "|".join(re.escape(name) for name in longest_first)
    )


def body_start(text):
    """The number of the first line after the opening block."""
    _, body = notes.front(text)
    return len(text.split("\n")) - len(body.split("\n"))


def workable(lines, start):
    """Each line the linker may work in.

    Not a code block, a heading, a callout title, or a comment that
    runs over several lines.
    """
    code = False
    comment = None
    for index in range(start, len(lines)):
        line = lines[index]
        if comment:
            # The line that closes a comment is left alone as well.
            if comment in line:
                comment = None
            continue
        if FENCE.match(line):
            code = not code
            continue
        if code:
            continue
        for opens, closes in (("%%", "%%"), ("<!--", "-->")):
            rest = line
            while opens in rest and not comment:
                rest = rest.split(opens, 1)[1]
                if closes in rest:
                    rest = rest.split(closes, 1)[1]
                else:
                    comment = closes
        if not (comment or HEADING.match(line) or CALLOUT_TITLE.match(line)):
            yield index, line


def strip_links(vault, note, known):
    """Take the brackets off every link that shows a full name.

    Returns the new text, where each stripped link was and what it
    pointed at, and how many links could not be judged because their
    target is missing.
    """
    text = vault.text(note)
    lines = text.split("\n")
    wanted, unjudged = [], 0
    for index, line in workable(lines, body_start(text)):
        # A link inside code or a comment is not the linker's to make.
        skip = [
            found.span()
            for pattern in LEFT_ALONE if pattern is not EXISTING_LINK
            for found in pattern.finditer(line)
        ]
        pieces, last, length = [], 0, 0
        for found in WIKILINK.finditer(line):
            if found.group(1) or any(a <= found.start() < b for a, b in skip):
                continue
            target, _, shown = found.group(2).replace("\\|", "|").partition("|")
            target = target.split("#", 1)[0].strip()
            shown = shown.strip() or target.rsplit("/", 1)[-1]
            if shown not in known or len(shown.split()) < 2:
                continue
            truth = vault.resolve(target, note) if target else None
            if truth is None:
                unjudged += 1
                continue
            before = line[last:found.start()]
            wanted.append((index, length + len(before), len(shown), shown, truth))
            pieces += [before, shown]
            length += len(before) + len(shown)
            last = found.end()
        lines[index] = "".join(pieces) + line[last:]
    return "\n".join(lines), wanted, unjudged


def matches(text, pattern, known, own):
    """Where the matcher would put a link: (line, column, length, object)."""
    if pattern is None:
        return []
    found = []
    lines = text.split("\n")
    for index, line in workable(lines, body_start(text)):
        for left_alone in LEFT_ALONE:
            line = left_alone.sub(lambda hit: "\0" * len(hit.group(0)), line)
        for hit in pattern.finditer(line):
            if hit.group(0) != own:
                found.append((index, hit.start(), len(hit.group(0)), known[hit.group(0)][0]))
    return found


def judge(wanted, made):
    """For one stripped link: did the matcher put it back?"""
    index, column, length, _, truth = wanted
    for line, start, size, target in made:
        if line == index and start < column + length and column < start + size:
            exact = start == column and size == length
            return "correct" if exact and target == truth else "wrong"
    return "missed"


def score(root, scratch):
    """Score one vault. Writes only into the scratch folder. Returns the report."""
    vault = notes.Vault(root, leave_out=(PRIVATE,))
    known, shared = names(vault)
    pattern = name_pattern(known)
    own = {note: name for name, (note, _) in known.items()}
    by_type = {kind: {"correct": 0, "wrong": 0, "missed": 0} for kind in TYPES}
    examples = {"wrong": [], "missed": []}
    unjudged = 0
    for note in workplace(vault):
        stripped, wanted, skipped = strip_links(vault, note, known)
        unjudged += skipped
        copy = Path(scratch) / note
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_text(stripped, encoding="utf-8")
        made = matches(stripped, pattern, known, own.get(note))
        for link in wanted:
            result = judge(link, made)
            by_type[known[link[3]][1]][result] += 1
            if result != "correct" and len(examples[result]) < EXAMPLES:
                examples[result].append("%s line %d: %s" % (note, link[0] + 1, link[3]))
    correct, wrong, missed = (
        sum(counts[name] for counts in by_type.values())
        for name in ("correct", "wrong", "missed")
    )
    return {
        "vault": str(vault.root),
        "run_at": datetime.datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "by_type": by_type,
        "right_rate": correct / float(correct + wrong) if correct + wrong else None,
        "miss_rate": missed / float(correct + wrong + missed) if correct + wrong + missed else None,
        "scratch": str(Path(scratch).resolve()),
        "names": len(known),
        "names_shared_by_two_objects": shared,
        "links_with_a_missing_target": unjudged,
        "examples": examples,
        "unreadable": sorted(set(vault.unreadable)),
    }


def table(report):
    lines = ["Scored %s at %s" % (report["vault"], report["run_at"]), "",
             "%-10s %8s %8s %8s" % ("", "right", "wrong", "missed")]
    for kind in TYPES:
        counts = report["by_type"][kind]
        lines.append("%-10s %8s %8s %8s" % (
            LABELS[kind], format(counts["correct"], ","), format(counts["wrong"], ","),
            format(counts["missed"], ",")))
    lines.append("")
    if report["right_rate"] is None or report["miss_rate"] is None:
        lines.append("No links that show a full name were found, so there is nothing to score.")
    else:
        lines.append("Right %.1f times in 100. Misses %.1f in 100."
                     % (report["right_rate"] * 100, report["miss_rate"] * 100))
    if report["names_shared_by_two_objects"]:
        lines.append("Names two objects share, so not linked: %d."
                     % len(report["names_shared_by_two_objects"]))
    return "\n".join(lines)


def save(report, state):
    scratch = state / (".%s.%d" % (REPORT, os.getpid()))
    scratch.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    os.replace(str(scratch), str(state / REPORT))
    return state / REPORT


def run(arguments, out, err):
    """`wd score <vault>`. Returns a code."""
    if len(arguments) != 1:
        print("usage: wd score <vault>", file=err)
        return 2
    root = Path(arguments[0]).expanduser()
    if not root.is_dir():
        print("wd score: there is no vault at %s." % root, file=err)
        return 1
    root, state = root.resolve(), places.state_dir().resolve()
    if state == root or root in state.parents:
        print("wd score: machine state is inside the vault (%s). Nothing was scored, "
              "because this command never writes there." % state, file=err)
        return 1
    scratch = state / SCRATCH
    if root == scratch or scratch in root.parents:
        print("wd score: %s is this command's own scratch folder, which it clears "
              "at the start of a run. Nothing was scored." % root, file=err)
        return 1
    state.mkdir(parents=True, exist_ok=True)
    if scratch.is_dir():
        # Last run's scratch copy. It is ours, and it is under machine state.
        shutil.rmtree(str(scratch))
    scratch.mkdir()
    report = score(root, scratch)
    saved = save(report, state)
    print(table(report), file=out)
    print("\nSaved to %s" % saved, file=out)
    if report["unreadable"]:
        print("wd score: %d files or folders could not be read, so the numbers are "
              "not complete. They are listed in the saved report."
              % len(report["unreadable"]), file=err)
        return 1
    return 0
