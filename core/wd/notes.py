"""Reading a vault: its files, each note's opening block, and its links.

Nothing here writes.
"""

import os
import re
from pathlib import Path

LINK = re.compile(r"\[\[([^\[\]\n]+)\]\]")
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`[^`\n]*`")
HEADING = re.compile(r"^#{1,6}\s+(.*)$")
KEY = re.compile(r"^([A-Za-z0-9_-]+):(.*)$")
HAS_LETTER_OR_DIGIT = re.compile(r"[^\W_]")


def words(text):
    """A word is anything with a letter or a digit in it."""
    return [word for word in text.split() if HAS_LETTER_OR_DIGIT.search(word)]


def unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1].strip()
    return value


def front(text):
    """Split a note into its opening block and its body.

    Returns (keys, body). Each top-level key maps to its value as one
    string, with any lines that continue it joined on.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = next(
        (number for number in range(1, len(lines)) if lines[number].strip() == "---"),
        None,
    )
    if end is None:
        return {}, text
    keys, current = {}, None
    for line in lines[1:end]:
        found = KEY.match(line)
        if found:
            current = found.group(1)
            keys[current] = re.sub(r"^[>|][+-]?\s*$", "", found.group(2).strip())
        elif current is not None and line.strip():
            keys[current] = (keys[current] + " " + line.strip()).strip()
    return {key: unquote(value) for key, value in keys.items()}, "\n".join(lines[end + 1:])


def without_code(text):
    """The text with code blocks and inline code taken out."""
    kept, inside = [], False
    for line in text.split("\n"):
        if FENCE.match(line):
            inside = not inside
            continue
        if not inside:
            kept.append(INLINE_CODE.sub("", line))
    return "\n".join(kept)


def link_targets(text):
    """What each link in the text points at, without its shown words or heading."""
    targets = []
    for inner in LINK.findall(without_code(text)):
        # Inside a table cell the bar before the shown words is written `\|`.
        target = inner.replace("\\|", "|").split("|", 1)[0].split("#", 1)[0].strip()
        if target:
            targets.append(target)
    return targets


def first_heading(body):
    for line in without_code(body).split("\n"):
        found = HEADING.match(line)
        if found:
            return found.group(1).strip()
    return ""


class Vault:
    """Every file in a vault, and what a link resolves to.

    Folders and files whose names start with a dot are left out, as
    Obsidian leaves them out.
    """

    def __init__(self, root):
        self.root = Path(root).resolve()
        self.files = []
        self.notes = []
        self.unreadable = []
        self._texts = {}
        for folder, folders, names in os.walk(str(self.root), onerror=self._could_not_open):
            folders[:] = sorted(name for name in folders if not name.startswith("."))
            for name in sorted(names):
                if name.startswith("."):
                    continue
                relative = (Path(folder) / name).relative_to(self.root).as_posix()
                self.files.append(relative)
                if name.endswith(".md"):
                    self.notes.append(relative)
        # Every way a link can name a file. Obsidian ignores case and
        # accepts any tail of the path. The shortest path wins.
        self._targets = {}
        for relative in sorted(self.files, key=lambda name: (name.count("/"), name)):
            names = [relative.lower()]
            if relative.endswith(".md"):
                names.append(relative[:-3].lower())
            for name in names:
                parts = name.split("/")
                for start in range(len(parts)):
                    self._targets.setdefault("/".join(parts[start:]), relative)

    def _could_not_open(self, problem):
        self.unreadable.append(str(problem.filename))

    def text(self, relative):
        if relative not in self._texts:
            try:
                self._texts[relative] = (self.root / relative).read_text(
                    encoding="utf-8", errors="replace"
                )
            except OSError:
                self.unreadable.append(relative)
                self._texts[relative] = ""
        return self._texts[relative]

    def resolve(self, target):
        """The file a link target names, or None."""
        return self._targets.get(target.strip().strip("/").lower())
