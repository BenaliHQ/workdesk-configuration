"""The declarations: one file for each object type and each source kind.

A declaration says where a type lives in a vault and what a note of that
type holds. The files are in `core/declarations/`:

    objects/<type>.json    home, linkable, name-from, required-keys,
                           sections, summary-max-words
    sources/<kind>.json    kind, home, required-keys

This is the one place the homes are written down. `wd.places` takes its
homes from here.
"""

import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1] / "declarations"

# The types and kinds, in the build spec's order. Each has one file.
OBJECT_TYPES = (
    "person", "company", "project", "term", "concept", "meeting", "decision", "quote",
)
SOURCE_KINDS = (
    "meeting-recording", "article", "post", "video", "podcast", "book",
    "agent-session", "capture", "calendar",
)

OBJECT_KEYS = (
    "home", "linkable", "name-from", "required-keys", "sections", "summary-max-words",
)
SOURCE_KEYS = ("kind", "home", "required-keys")
# The one way a name is taken, for the types that are linked by name.
FIRST_HEADING = "first-heading"

_loaded = {}


class DeclarationError(ValueError):
    """The declaration files are missing or not right."""


def _names(value):
    return isinstance(value, list) and all(
        isinstance(entry, str) and entry.strip() for entry in value
    )


def _folder(value):
    """A home is a folder inside the vault, written without a slash at either end."""
    return (
        isinstance(value, str)
        and value.strip()
        and value == value.strip("/")
        and ".." not in value.split("/")
    )


def _read(path):
    """The values in one file, or a line saying why not."""
    try:
        found = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        return None, "there is no file"
    except ValueError as problem:
        return None, "not valid JSON: %s" % problem
    if not isinstance(found, dict):
        return None, "not a group of values"
    return found, None


def _object_problems(found):
    problems = []
    linkable = found.get("linkable")
    allowed = [set(OBJECT_KEYS)]
    if linkable is False:
        # A type that is not linked by name may leave name-from out.
        allowed.append(set(OBJECT_KEYS) - {"name-from"})
    if set(found) not in allowed:
        problems.append("its keys are not exactly %s" % ", ".join(OBJECT_KEYS))
    if not _folder(found.get("home")):
        problems.append("home is not a folder in the vault")
    if not isinstance(linkable, bool):
        problems.append("linkable is not true or false")
    elif linkable and found.get("name-from") != FIRST_HEADING:
        problems.append("name-from is not %s" % FIRST_HEADING)
    elif not linkable and found.get("name-from") is not None:
        problems.append("it is not linked by name, so name-from is null")
    required = found.get("required-keys")
    if not _names(required) or "type" not in required:
        problems.append("required-keys is not a list of keys with type among them")
    if not _names(found.get("sections")):
        problems.append("sections is not a list of headings")
    limit = found.get("summary-max-words")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        problems.append("summary-max-words is not a whole number above zero")
    return problems


def _source_problems(found, kind):
    problems = []
    if set(found) != set(SOURCE_KEYS):
        problems.append("its keys are not exactly %s" % ", ".join(SOURCE_KEYS))
    if found.get("kind") != kind:
        problems.append("kind is not %s" % kind)
    if found.get("home") is not None and not _folder(found.get("home")):
        problems.append("home is not a folder in the vault, and not null")
    if not _names(found.get("required-keys")):
        problems.append("required-keys is not a list of keys")
    return problems


def read(folder=None):
    """Read every declaration. Returns (object types, source kinds, problems).

    Each group is in the build spec's order. A file that is missing or
    not right is left out of its group and named in the problems.
    """
    folder = Path(folder) if folder else FOLDER
    objects, sources, problems = {}, {}, []
    for part, names, check, group in (
        ("objects", OBJECT_TYPES, lambda found, name: _object_problems(found), objects),
        ("sources", SOURCE_KINDS, _source_problems, sources),
    ):
        for name in names:
            where = "%s/%s.json" % (part, name)
            found, why_not = _read(folder / part / (name + ".json"))
            wrong = [why_not] if why_not else check(found, name)
            if wrong:
                problems += ["%s: %s" % (where, line) for line in wrong]
                continue
            if part == "objects":
                found.setdefault("name-from", None)
            group[name] = found
        here = folder / part
        for path in sorted(here.glob("*.json")) if here.is_dir() else []:
            if path.stem not in names:
                problems.append(
                    "%s/%s: not one of the %d that are declared" % (part, path.name, len(names))
                )
    homes = {}
    for name, found in objects.items():
        homes.setdefault(found["home"], []).append(name)
    for home, shared in sorted(homes.items()):
        if len(shared) > 1:
            problems.append("%s: the home of %s" % (home, " and ".join(shared)))
    return objects, sources, problems


def load(folder=None):
    """The declarations, or a DeclarationError that lists what is wrong."""
    objects, sources, problems = read(folder)
    if problems:
        raise DeclarationError(
            "The declarations in %s are not right:\n  %s"
            % (Path(folder) if folder else FOLDER, "\n  ".join(problems))
        )
    return objects, sources


def _shipped():
    if not _loaded:
        _loaded["objects"], _loaded["sources"] = load()
    return _loaded


def objects():
    """Each object type's declaration, by type, in the build spec's order."""
    return _shipped()["objects"]


def sources():
    """Each source kind's declaration, by kind, in the build spec's order."""
    return _shipped()["sources"]


def object_homes():
    """(type, home) for each object type."""
    return [(name, found["home"]) for name, found in objects().items()]


def linkable():
    """The object types that are linked by name."""
    return tuple(name for name, found in objects().items() if found["linkable"])


def source_homes():
    """The folders sources live in, each once. The calendar has none."""
    homes = []
    for found in sources().values():
        if found["home"] and found["home"] not in homes:
            homes.append(found["home"])
    return homes
