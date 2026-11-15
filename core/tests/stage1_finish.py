"""Finish test for stage 1, Structure.

This file was written and committed before the rest of stage 1 existed,
so it fails until the stage is built. Only the operator seeing it pass
finishes the stage.

Every check names the build spec line it comes from. A check that cannot
run is reported as NOT RUN and counts as a failure. Unknown is never
healthy.

Run it through the runner:

    /usr/bin/python3 core/tests/run.py --finish 1 \
        --new-vault <the new vault> --build-log <note>

Without `--new-vault` the new vault is looked for at `~/Workdesk`, or
where the environment variable WD_NEW_VAULT points.

What the packages that follow must meet. The build spec fixes the first
group. The rest are choices this test had to make because it was written
first.

Fixed by the build spec

- The folders, the object homes and the source homes under "The new
  vault's folders".
- The command list under "Commands".
- The six keys of an object type's declaration (S1.1), the 1,200 words
  of the rulebook and the 40 words of a skill description (S1.2).

Declarations (S1.1)

- `core/declarations/objects/<type>.json`, one for each of the eight
  object types, and `core/declarations/sources/<kind>.json`, one for
  each of the nine source kinds.
- An object declaration's `home` is its folder, such as
  `objects/people`. `name-from` is `first-heading` on the five types
  that are linked by name, and null or left out on the other three.
- A source declaration holds `kind`, `home` and `required-keys`. The
  calendar has no files, so its `home` is null.

The product files (S1.2)

- `core/product/AGENTS.md` and `core/product/CLAUDE.md`.
- `core/product/skills/<name>/SKILL.md` for context, correct, track and
  status, each with a `description` in its opening block.

Commands (S1.3 and S1.4)

- `wd init <vault>` and `wd init <vault> --samples`: the path first.
  It makes all three root files, the status page among them.
- A sample is a note with `sample: true` in its opening block. With
  samples there are nine notes in the vault: one in each object home
  and one recording in `sources/recordings/`.
- The Obsidian settings are `.obsidian/app.json` and
  `.obsidian/graph.json`. In `graph.json`, `colorGroups` holds one
  group for each object type, whose `query` is `path:<home>`, and
  `search` holds `-path:sources`, `-path:signals/briefs` and
  `-file:<name>` for each root file.
- `wd graph-setting <vault> --dry-run` changes nothing. With `--apply`
  it writes the settings above into the two files and keeps every
  other key that was in them.
- `wd check <vault>` writes `check.json` into machine state, with
  `vault`, `run_at` and `problems`, a list with one entry for each
  problem. An entry holds `note`, the note's path in the vault, and
  `kind`, a fixed word. Among the kinds: `missing-key`,
  `summary-too-long`, `link-goes-nowhere`, `first-name-link`,
  `unlinked` and `name-not-unique`. It never writes inside the vault.
- `wd status <vault> --dry-run` writes nothing. `wd status <vault>
  --apply` writes `status.md` at the top of the vault and nothing else.
  The page names each home with its count, has a line with the word
  "check" and the number of problems, and for each runtime a line with
  its name (Claude Code, Codex) and two numbers: the words that come
  "from the vault" and the words that come "from outside it". Words
  from outside are what the same home folder loads in an empty folder.
- `wd` reads the machine state location from WD_STATE_DIR and finds the
  user's own instruction files through HOME, as in stage 0.

The two checks that moved here from stage 0 (S1.R2)

One line each in the build log, in the form stage 0 uses:

    S0.5 (a): verified. Evidence: <what was done and seen>.
    S0.5 (e): failed. Evidence: <...>. Consequence: <...>.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

import stage0_finish as stage0  # noqa: E402

CORE = TESTS.parent
WD = CORE / "bin" / "wd"
FIXTURES = TESTS / "fixtures"
TEST_VAULT = FIXTURES / "vault"
CASES_HOME = FIXTURES / "cases"
ANSWERS = FIXTURES / "answers.json"
DECLARATIONS = CORE / "declarations"
PRODUCT = CORE / "product"

# Build spec, "Object homes": the type, its home, and whether it is
# linked by name.
OBJECT_TYPES = [
    ("person", "objects/people", True),
    ("company", "objects/companies", True),
    ("project", "objects/projects", True),
    ("term", "objects/terms", True),
    ("concept", "objects/concepts", True),
    ("meeting", "objects/meetings", False),
    ("decision", "objects/decisions", False),
    ("quote", "objects/quotes", False),
]

# Build spec, "Source homes, permanent from arrival".
SOURCE_KINDS = [
    ("meeting-recording", "sources/recordings"),
    ("article", "sources/links"),
    ("post", "sources/links"),
    ("video", "sources/links"),
    ("podcast", "sources/links"),
    ("book", "sources/links"),
    ("agent-session", "sources/sessions"),
    ("capture", "sources/captures"),
    ("calendar", None),
]

# Build spec, S1.1: the keys of an object type's declaration.
OBJECT_KEYS = [
    "home", "linkable", "name-from", "required-keys", "sections", "summary-max-words",
]
# Build spec, "Object body".
SUMMARY_MAX_WORDS = 60
WITH_CURRENTLY = ("person", "company", "project")
# Build spec, "Source frontmatter".
SOURCE_KEYS = [
    "type", "kind", "title", "date", "author", "sent-by", "status", "starred",
    "private", "take", "produced", "sha256-original",
]

# Build spec, "The new vault's folders".
FOLDERS = [
    "sources/recordings", "sources/links", "sources/sessions", "sources/captures",
    "objects/people", "objects/companies", "objects/projects", "objects/terms",
    "objects/concepts", "objects/meetings", "objects/decisions", "objects/quotes",
    "writing",
    "signals/briefs", "signals/syntheses",
]
ROOT_FILES = ("AGENTS.md", "CLAUDE.md", "status.md")
# Build spec, S1.3: `wd init` creates the root files, all three. It
# writes `status.md` the way `wd status` does.
FILES_FROM_INIT = ROOT_FILES
STATUS_PAGE = "status.md"
SETTINGS = ".obsidian"
SKILL_FOLDERS = (".claude/skills", ".agents/skills")
HIDDEN = (SETTINGS,) + SKILL_FOLDERS
WRITING = "writing"
RECORDINGS = "sources/recordings"
# The current vault's top folders. Nothing in the new layout uses them.
OLD_FOLDERS = ("atlas", "gtd", "intel", "system")

# Build spec, "Commands".
COMMANDS = [
    "init", "check", "score", "status", "graph-setting", "add", "process", "link",
    "track", "fix", "find", "pack", "brief", "tick", "install",
]
NOT_BUILT = 3

# Build spec, S1.2.
RULEBOOK_MAX_WORDS = 1200
SKILLS = ["context", "correct", "track", "status"]
DESCRIPTION_MAX_WORDS = 40
IMPORT_LINE = "@AGENTS.md"

# The contract's Budgets table: words loaded into a session.
SESSION_LOAD_LIMIT = 3000
RUNTIMES = (("claude-code", "Claude Code"), ("codex", "Codex"))

# Build spec, stage 0 and S1.R2: the two checks that moved to stage 1.
MOVED_CHECKS = ("a", "e")

DEFAULT_NEW_VAULT = "~/Workdesk"

HAS_LETTER_OR_DIGIT = re.compile(r"[^\W_]")
KEY = re.compile(r"^([A-Za-z0-9_-]+):(.*)$")
LINK = re.compile(r"\[\[([^\[\]\n]+)\]\]")
MARKER = " ^p%04d"


# ---- reading ----

def body(text):
    """A page without the header block at the top."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for number, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return "\n".join(lines[number + 1:])
    return text


def words(text):
    """Counted as the budget test counts the contract: a word has a letter or a digit."""
    return [word for word in body(text).split() if HAS_LETTER_OR_DIGIT.search(word)]


def front(text):
    """The keys of a note's opening block. Each value is one string."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}
    keys, current = {}, None
    for line in lines[1:]:
        if line.strip() == "---":
            return keys
        found = KEY.match(line)
        if found:
            current = found.group(1)
            keys[current] = found.group(2).strip()
        elif current is not None and line.strip():
            keys[current] = (keys[current] + " " + line.strip()).strip()
    return {}


def unquoted(value):
    """A value without its quotes, or without the mark that starts a folded value."""
    value = re.sub(r"^[>|][+-]?\s*", "", value.strip())
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1]
    return value.strip()


def link_targets(text):
    """What each link in the text points at, without its shown words or its passage."""
    targets = []
    for inner in LINK.findall(text):
        target = inner.replace("\\|", "|").split("|", 1)[0].split("#", 1)[0].strip()
        if target:
            targets.append(target)
    return targets


def tree(root):
    """Every file and every folder under root, as paths from root."""
    root = Path(root)
    files, folders = [], []
    for here, names, file_names in os.walk(str(root)):
        names.sort()
        for name in names:
            folders.append((Path(here) / name).relative_to(root).as_posix())
        for name in sorted(file_names):
            files.append((Path(here) / name).relative_to(root).as_posix())
    return files, folders


def read_json(path):
    """The values in a JSON file, or None when it is missing or not valid."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def read_declarations(folder):
    """The declarations on disk: (object types, source kinds), each by name."""
    found = []
    for part in ("objects", "sources"):
        here = Path(folder) / part
        found.append({
            path.stem: read_json(path)
            for path in (sorted(here.glob("*.json")) if here.is_dir() else [])
        })
    return found[0], found[1]


# ---- S1.1 ----

def same_folder(value, folder):
    return isinstance(value, str) and value.strip("/") == folder


def list_of_names(value):
    return isinstance(value, list) and all(
        isinstance(entry, str) and entry.strip() for entry in value
    )


def declaration_problems(objects, sources):
    """Everything wrong with the declarations, given by type and by kind."""
    problems = []
    for kind, home, linkable in OBJECT_TYPES:
        where = "objects/%s" % kind
        found = objects.get(kind)
        if not isinstance(found, dict):
            problems.append("%s: no declaration" % where)
            continue
        allowed = [set(OBJECT_KEYS)]
        if not linkable:
            allowed.append(set(OBJECT_KEYS) - {"name-from"})
        if set(found) not in allowed:
            problems.append(
                "%s: its keys are %s, not %s"
                % (where, ", ".join(sorted(found)), ", ".join(sorted(OBJECT_KEYS)))
            )
        if not same_folder(found.get("home"), home):
            problems.append("%s: home is %r, not %s" % (where, found.get("home"), home))
        if found.get("linkable") is not linkable:
            problems.append("%s: linkable is not %s" % (where, str(linkable).lower()))
        if linkable and found.get("name-from") != "first-heading":
            problems.append("%s: name-from is not first-heading" % where)
        if not linkable and found.get("name-from") is not None:
            problems.append("%s: has a name-from, and is not linked by name" % where)
        required = found.get("required-keys")
        if not list_of_names(required):
            problems.append("%s: required-keys is not a list of keys" % where)
        else:
            for key in ("type", "private"):
                if key not in required:
                    problems.append("%s: required-keys leaves out %s" % (where, key))
            for key in ("name", "aliases"):
                if linkable and key not in required:
                    problems.append("%s: required-keys leaves out %s" % (where, key))
                if not linkable and key in required:
                    problems.append(
                        "%s: required-keys has %s, and is not linked by name" % (where, key)
                    )
        sections = found.get("sections")
        if not list_of_names(sections):
            problems.append("%s: sections is not a list of headings" % where)
        elif ("Currently" in sections) != (kind in WITH_CURRENTLY):
            problems.append(
                "%s: Currently is for people, companies and projects only" % where
            )
        limit = found.get("summary-max-words")
        if isinstance(limit, bool) or limit != SUMMARY_MAX_WORDS:
            problems.append("%s: summary-max-words is not %d" % (where, SUMMARY_MAX_WORDS))
    known = {kind for kind, _, _ in OBJECT_TYPES}
    for extra in sorted(set(objects) - known):
        problems.append("objects/%s: not one of the eight object types" % extra)

    for kind, home in SOURCE_KINDS:
        where = "sources/%s" % kind
        found = sources.get(kind)
        if not isinstance(found, dict):
            problems.append("%s: no declaration" % where)
            continue
        if found.get("kind") != kind:
            problems.append("%s: kind is %r" % (where, found.get("kind")))
        if home is None:
            if "home" not in found or found["home"] is not None:
                problems.append("%s: has no files, so its home is null" % where)
        elif not same_folder(found.get("home"), home):
            problems.append("%s: home is %r, not %s" % (where, found.get("home"), home))
        required = found.get("required-keys")
        if not list_of_names(required):
            problems.append("%s: required-keys is not a list of keys" % where)
        elif home is not None:
            for key in SOURCE_KEYS:
                if key not in required:
                    problems.append("%s: required-keys leaves out %s" % (where, key))
    known = {kind for kind, _ in SOURCE_KINDS}
    for extra in sorted(set(sources) - known):
        problems.append("sources/%s: not one of the nine source kinds" % extra)
    return problems


def allowed_folders():
    """Every folder the new layout names, and the folders above them."""
    allowed = set()
    for folder in list(FOLDERS) + list(HIDDEN):
        parts = folder.split("/")
        for end in range(1, len(parts) + 1):
            allowed.add("/".join(parts[:end]))
    return allowed


def layout_problems(files, folders=()):
    """Every file and folder that is outside the new vault's layout."""
    problems = []
    for path in sorted(files):
        if "/" not in path:
            if path not in ROOT_FILES:
                problems.append("%s: not one of the root files" % path)
        elif not any(path.startswith(folder + "/") for folder in list(FOLDERS) + list(HIDDEN)):
            problems.append("%s: not in a folder of the new layout" % path)
    allowed = allowed_folders()
    for folder in sorted(folders):
        if folder in allowed or any(folder.startswith(hidden + "/") for hidden in HIDDEN):
            continue
        problems.append("%s/: not a folder of the new layout" % folder)
    return problems


def home_problems(files):
    """The object homes with no notes, and no recording to point at."""
    notes = [path for path in files if path.endswith(".md")]
    problems = []
    for _, home, _ in OBJECT_TYPES:
        if not any(path.startswith(home + "/") for path in notes):
            problems.append("%s: no notes" % home)
    if not any(path.startswith(RECORDINGS + "/") for path in notes):
        problems.append("%s: no notes" % RECORDINGS)
    return problems


OLD_PATH = re.compile(r"(?<![\w/.-])(%s)/[\w.-]" % "|".join(OLD_FOLDERS))


def old_path_problems(name, text):
    """Paths left over from the current vault's layout."""
    found = sorted({match.group(0)[:-1] for match in OLD_PATH.finditer(text)})
    return ["%s: still names %s" % (name, old) for old in found]


def listed_commands(help_text):
    """The commands `wd --help` lists, in its order."""
    found, inside = [], False
    for line in help_text.splitlines():
        if line.strip().lower() == "commands:":
            inside = True
            continue
        match = re.match(r"^\s+([a-z][a-z-]*)(\s|$)", line) if inside else None
        if match:
            found.append(match.group(1))
    return found


def command_problems(help_text):
    """How the listed commands differ from the build spec's list."""
    found = listed_commands(help_text)
    problems = ["%s: not listed" % name for name in COMMANDS if name not in found]
    problems += ["%s: listed, and not in the build spec" % name
                 for name in found if name not in COMMANDS]
    problems += ["%s: listed twice" % name
                 for name in sorted(set(found)) if found.count(name) > 1]
    return problems


# ---- S1.2 ----

def rulebook_problems(text):
    count = len(words(text))
    if not count:
        return ["the rulebook says nothing"]
    if count > RULEBOOK_MAX_WORDS:
        return ["the rulebook has %d words. The limit is %d." % (count, RULEBOOK_MAX_WORDS)]
    return []


def import_problems(text):
    """CLAUDE.md holds one line, and it imports the rulebook."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines != [IMPORT_LINE]:
        return ["CLAUDE.md is not the one line %s" % IMPORT_LINE]
    return []


def skill_problems(skills):
    """Everything wrong with the skills, given as the text of each SKILL.md by name."""
    problems = []
    for name in SKILLS:
        text = skills.get(name)
        if not isinstance(text, str):
            problems.append("%s: no SKILL.md" % name)
            continue
        described = len(words(unquoted(front(text).get("description", ""))))
        if not described:
            problems.append("%s: no description" % name)
        elif described > DESCRIPTION_MAX_WORDS:
            problems.append(
                "%s: its description has %d words. The limit is %d."
                % (name, described, DESCRIPTION_MAX_WORDS)
            )
    for extra in sorted(set(skills) - set(SKILLS)):
        problems.append("%s: not one of the four skills" % extra)
    return problems


# ---- S1.3 ----

def names_path(query, folder):
    """Does a graph query pick out this folder, and not hide it?"""
    return isinstance(query, str) and re.search(
        r'(?<![\w/"-])path:"?%s/?"?(?![\w/-])' % re.escape(folder), query
    ) is not None


def hides_path(search, folder):
    return isinstance(search, str) and re.search(
        r'(?<!\S)-path:"?%s/?"?(?![\w/-])' % re.escape(folder), search
    ) is not None


def hides_file(search, name):
    stem = name[:-3] if name.endswith(".md") else name
    return isinstance(search, str) and re.search(
        r'(?<!\S)-(?:file|path):"?%s(?:\.md)?"?(?![\w/.-])' % re.escape(stem), search
    ) is not None


def graph_problems(graph, app):
    """Everything wrong with the graph setting and the link setting."""
    problems = []
    if not isinstance(app, dict) or app.get("alwaysUpdateLinks") is not True:
        problems.append("app.json: alwaysUpdateLinks is not true, so a rename leaves links behind")
    if not isinstance(graph, dict):
        return problems + ["graph.json: missing, or not a group of values"]
    groups = graph.get("colorGroups")
    groups = [group for group in groups if isinstance(group, dict)] if isinstance(groups, list) else []
    if len(groups) != len(OBJECT_TYPES):
        problems.append(
            "graph.json: %d color groups. There is one for each of the %d object types."
            % (len(groups), len(OBJECT_TYPES))
        )
    for kind, home, _ in OBJECT_TYPES:
        matching = [group for group in groups if names_path(group.get("query"), home)]
        if len(matching) != 1:
            problems.append("graph.json: %d color groups for %s" % (len(matching), home))
    colors = [json.dumps(group.get("color"), sort_keys=True) for group in groups]
    if "null" in colors:
        problems.append("graph.json: a color group has no color")
    elif len(set(colors)) != len(colors):
        problems.append("graph.json: two object types share a color")
    search = graph.get("search")
    for folder in ("sources", "signals/briefs"):
        if not hides_path(search, folder):
            problems.append("graph.json: %s/ is not hidden" % folder)
    for name in ROOT_FILES:
        if not hides_file(search, name):
            problems.append("graph.json: %s is not hidden" % name)
    return problems


# Settings that are wrong in every way the graph setting must repair,
# each with one key of the owner's that must be kept.
WRONG_GRAPH = {"colorGroups": [], "search": "path:sources", "scale": 1.5}
WRONG_APP = {"alwaysUpdateLinks": False, "showLineNumber": True}


def kept_key_problems(name, before, after):
    """The keys in a settings file that the graph setting must leave as they were."""
    if not isinstance(after, dict):
        return ["%s: missing, or not a group of values" % name]
    return [
        "%s: %s was %s and is now %s" % (
            name, key, json.dumps(before[key]), json.dumps(after.get(key, "not there")))
        for key in sorted(before)
        if key not in ("colorGroups", "search", "alwaysUpdateLinks")
        and (key not in after or after[key] != before[key])
    ]


def marker_problems(text):
    """A source's blocks, each of which must end with its passage marker, in order."""
    blocks = [block for block in body(text).strip().split("\n\n") if block.strip()]
    if not blocks:
        return ["has no passages"]
    return [
        "block %d does not end with%s" % (number, MARKER % number)
        for number, block in enumerate(blocks, 1)
        if not block.rstrip().endswith(MARKER % number)
    ]


def link_problems(notes):
    """Links that go nowhere, and objects no other note links to. Notes are given by path."""
    by_name = {}
    for path in sorted(notes):
        parts = path[:-3].lower().split("/")
        for start in range(len(parts)):
            by_name.setdefault("/".join(parts[start:]), path)
    problems, linked = [], set()
    for path in sorted(notes):
        for target in link_targets(notes[path]):
            wanted = target.lower().strip("/")
            wanted = wanted[:-3] if wanted.endswith(".md") else wanted
            found = by_name.get(wanted)
            if found is None:
                problems.append("%s: its link to %s goes nowhere" % (path, target))
            elif found != path:
                linked.add(found)
    for _, home, _ in OBJECT_TYPES:
        for path in sorted(notes):
            if path.startswith(home + "/") and path not in linked:
                problems.append("%s: no other note links to it" % path)
    return problems


def notes_in(root, folders):
    """The text of every note in these folders, by path."""
    root = Path(root)
    files, _ = tree(root)
    return {
        path: (root / path).read_text(encoding="utf-8", errors="replace")
        for path in files
        if path.endswith(".md") and any(path.startswith(folder + "/") for folder in folders)
    }


def sample_problems(root):
    """With samples: one in each object home, one recording, all marked and linked."""
    notes = notes_in(root, FOLDERS)
    problems, wanted = [], set()
    for _, home, _ in OBJECT_TYPES:
        here = [path for path in notes if path.startswith(home + "/")]
        wanted |= set(here)
        if len(here) != 1:
            problems.append("%s: %d notes. There is one sample." % (home, len(here)))
    recordings = [path for path in notes if path.startswith(RECORDINGS + "/")]
    wanted |= set(recordings)
    if len(recordings) != 1:
        problems.append("%s: %d notes. There is one sample." % (RECORDINGS, len(recordings)))
    for path in sorted(recordings):
        problems += ["%s: %s" % (path, problem) for problem in marker_problems(notes[path])]
    for path in sorted(notes):
        if path not in wanted:
            problems.append("%s: not one of the nine samples" % path)
        if unquoted(front(notes[path]).get("sample", "")) != "true":
            problems.append("%s: does not carry sample: true" % path)
    return problems + link_problems(notes)


def one_sample_in_each_home(root):
    """The object homes that do not hold exactly one sample."""
    notes = notes_in(root, [home for _, home, _ in OBJECT_TYPES])
    problems = []
    for _, home, _ in OBJECT_TYPES:
        samples = [
            path for path in notes
            if path.startswith(home + "/")
            and unquoted(front(notes[path]).get("sample", "")) == "true"
        ]
        if len(samples) != 1:
            problems.append("%s: %d samples. There is one." % (home, len(samples)))
    return problems


def init_problems(root, samples=False):
    """Everything wrong with a vault that `wd init` has just made."""
    root = Path(root)
    if not root.is_dir():
        return ["there is no vault at %s" % root]
    files, folders = tree(root)
    problems = layout_problems(files, folders)
    for folder in FOLDERS:
        if not (root / folder).is_dir():
            problems.append("%s/: missing" % folder)
    for name in FILES_FROM_INIT:
        if not (root / name).is_file():
            problems.append("%s: missing" % name)
    if (root / "AGENTS.md").is_file() and not words(
        (root / "AGENTS.md").read_text(encoding="utf-8", errors="replace")
    ):
        problems.append("AGENTS.md: says nothing")
    if (root / "CLAUDE.md").is_file():
        problems += import_problems((root / "CLAUDE.md").read_text(encoding="utf-8"))
    for place in SKILL_FOLDERS:
        for name in SKILLS:
            if not (root / place / name / "SKILL.md").is_file():
                problems.append("%s/%s/SKILL.md: missing" % (place, name))
    problems += graph_problems(
        read_json(root / SETTINGS / "graph.json"), read_json(root / SETTINGS / "app.json")
    )
    for path in files:
        if path.startswith(WRITING + "/"):
            problems.append("%s: a program wrote under %s/" % (path, WRITING))
    if samples:
        problems += sample_problems(root)
    else:
        for path in sorted(notes_in(root, FOLDERS)):
            problems.append("%s: a note in a vault made without samples" % path)
    return problems


# ---- S1.4 ----

def said(value):
    return isinstance(value, str) and bool(value.strip())


def check_report_problems(report):
    """Everything wrong with the shape of `check.json`."""
    if not isinstance(report, dict):
        return ["the report is not a group of values"]
    found = report.get("problems")
    if not isinstance(found, list):
        return ["problems: expected a list with one entry for each problem"]
    return [
        "problems: an entry does not name its note and its kind"
        for entry in found
        if not (isinstance(entry, dict) and said(entry.get("note")) and said(entry.get("kind")))
    ]


TWICE = "name-not-unique"
PERSON = (
    "---\ntype: person\nname: %(name)s\naliases: []\nprivate: false\n---\n"
    "# %(name)s\n\n%(says)s\n"
)


def person(name, says):
    return PERSON % {"name": name, "says": says}


def faulty_notes(person_path, person_name, recording):
    """One invalid note for each thing the check must find, and one note that is right.

    Each is a made-up person, and each but the last has one thing
    wrong. `person_path` and `person_name` are a person already in the
    vault, and `recording` is a source there, both without `.md`.
    Returns (path, text, the kind of problem it must be given or None).
    """
    link = "[[%s|%s]]" % (person_path, person_name)
    first = person_name.split()[0]
    home = "objects/people"
    return [
        # No `private` key.
        ("%s/ada-quill.md" % home,
         person("Ada Quill", "Works with %s." % link).replace("private: false\n", ""),
         "missing-key"),
        # Four lines, and the limit is three.
        ("%s/ben-osei.md" % home,
         person("Ben Osei", "Works with %s.\nA second line.\nA third line.\nA fourth line." % link),
         "summary-too-long"),
        # Sixty-one words on one line, and the limit is sixty.
        ("%s/cy-ward.md" % home,
         person("Cy Ward", "Works with %s. %s" % (link, " ".join(["word"] * 57))),
         "summary-too-long"),
        # A link to a note that is not there.
        ("%s/di-novak.md" % home,
         person("Di Novak", "Works with %s at [[objects/companies/no-such-company|No Such Company]]."
                % link),
         "link-goes-nowhere"),
        # A link to a passage the recording does not have.
        ("%s/eli-stone.md" % home,
         person("Eli Stone", "Works with %s. [[%s#^p9999]]" % (link, recording)),
         "link-goes-nowhere"),
        # A link to a person that shows a first name alone.
        ("%s/fay-lund.md" % home,
         person("Fay Lund", "Works with [[%s|%s]]." % (person_path, first)),
         "first-name-link"),
        # No link in or out. A link to a source is not one.
        ("%s/gus-pine.md" % home,
         person("Gus Pine", "Keeps to himself. [[%s]]" % recording),
         "unlinked"),
        # The name of a person already in the vault.
        ("%s/the-other-one.md" % home,
         person(person_name, "A second note with a name in use. Works with %s." % link),
         "name-not-unique"),
        # Nothing wrong: every key, a short summary, a full name, a real passage.
        ("%s/hal-reed.md" % home,
         person("Hal Reed", "Works with %s. [[%s#^p0001]]" % (link, recording)),
         None),
    ]


def fault_problems(report, faults):
    """The faults the check did not find, and the right notes it found fault with.

    A name used twice may be reported on either of the two notes.
    """
    found = {}
    for entry in report.get("problems", []) if isinstance(report, dict) else []:
        if isinstance(entry, dict):
            found.setdefault(entry.get("note"), set()).add(entry.get("kind"))
    everywhere = set().union(*found.values()) if found else set()
    problems = []
    for path, _, kind in faults:
        kinds = found.get(path, set())
        if kind == TWICE and kind in everywhere:
            continue
        if kind is None and kinds:
            problems.append(
                "%s: nothing is wrong with it, and the check reported %s"
                % (path, ", ".join(sorted(str(name) for name in kinds)))
            )
        elif kind is not None and kind not in kinds:
            problems.append("%s: no %s problem was reported" % (path, kind))
    return problems


def mentions(line, folder):
    return re.search(r"(?<![\w/-])%s(?![\w-])" % re.escape(folder), line) is not None


def status_problems(text, notes, found, load):
    """Everything the status page leaves out.

    `notes` is the count for each home. `found` is the number of
    problems the check reported. `load` gives, for each runtime, the
    words that come from the `vault` and from `outside` it.
    """
    lines = text.splitlines()
    problems = []
    for home, count in sorted(notes.items()):
        if not any(mentions(line, home) and stage0.has_number(line, count) for line in lines):
            problems.append("notes in %s (%d)" % (home, count))
    if not any(
        re.search(r"\bcheck", line, re.IGNORECASE) and stage0.has_number(line, found)
        for line in lines
    ):
        problems.append("the check's result (%d)" % found)
    for phrase in ("from the vault", "from outside it"):
        if phrase not in text.lower():
            problems.append("the words \"%s\"" % phrase)
    for runtime, label in RUNTIMES:
        for part, shown in (("vault", "from the vault"), ("outside", "from outside it")):
            number = load[runtime][part]
            if not any(label in line and stage0.has_number(line, number) for line in lines):
                problems.append("session load, %s, %s (%d)" % (label, shown, number))
    return problems


def load_problems(session_load, limit=SESSION_LOAD_LIMIT):
    """The runtimes whose session load is unknown or over the limit."""
    problems = []
    for runtime, label in RUNTIMES:
        loaded = session_load.get(runtime) if isinstance(session_load, dict) else None
        if not stage0.whole(loaded):
            problems.append("%s: the session load is not known" % label)
        elif loaded > limit:
            problems.append(
                "%s: a session loads %d words. The limit is %d." % (label, loaded, limit)
            )
    return problems


# ---- You will see ----

def moved_check_problems(text):
    """Everything missing from the build log's record of checks (a) and (e)."""
    latest = {}
    for match in stage0.S05_LINE.finditer(text):
        letter, runtime, outcome, rest = match.groups()
        if runtime is None:
            latest[letter] = (outcome, rest)
    problems = []
    for letter in MOVED_CHECKS:
        label = "S0.5 (%s)" % letter
        if letter not in latest:
            problems.append("%s: no outcome logged" % label)
            continue
        outcome, rest = latest[letter]
        if not stage0.said_enough(rest, "Evidence", until="Consequence"):
            problems.append("%s: no evidence given" % label)
        if outcome != "verified" and not stage0.said_enough(rest, "Consequence"):
            problems.append("%s: %s, with no consequence given" % (label, outcome))
    return problems


def new_vault():
    """Where the real new vault is: WD_NEW_VAULT, or ~/Workdesk."""
    given = os.environ.get("WD_NEW_VAULT", "").strip()
    return Path(given or DEFAULT_NEW_VAULT).expanduser()


class FinishCase(stage0.FinishCase):
    def text(self, path, built_by):
        if not Path(path).is_file():
            self.fail("%s is missing. It is built by %s." % (path, built_by))
        return Path(path).read_text(encoding="utf-8")

    def wd(self, arguments, state, built_by, made_up_home=True):
        """Run one command. A command that is not built yet fails the check."""
        shown = "wd %s" % " ".join(str(argument) for argument in arguments)
        result = subprocess.run(
            [sys.executable, str(WD)] + [str(argument) for argument in arguments],
            env=self.environment(state, made_up_home),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=stage0.LONG_RUN_SECONDS,
        )
        missing = ("not built yet", "there is no command called")
        if result.returncode == NOT_BUILT or any(words in result.stderr for words in missing):
            self.fail("`%s` is not built yet. It is built by %s." % (shown, built_by))
        return result

    def fresh_vault(self, folder, samples):
        """Make a new vault in a scratch folder. Returns the vault and its state folder."""
        vault, state = Path(folder) / "vault", Path(folder) / "state"
        state.mkdir()
        arguments = ["init", vault] + (["--samples"] if samples else [])
        result = self.wd(arguments, state, "S1.3")
        self.assertEqual(
            result.returncode, 0, "`wd init` failed:\n%s%s" % (result.stdout, result.stderr)
        )
        return vault, state

    def the_new_vault(self):
        vault = new_vault()
        if not vault.is_dir():
            self.fail("NOT RUN: there is no vault at %s. It is made by S1.R1." % vault)
        return vault


class S11Layout(FinishCase):
    """S1.1: the declarations, the new homes, and the command list."""

    def test_a_declaration_for_every_object_type_and_source_kind(self):
        if not DECLARATIONS.is_dir():
            self.fail("%s is missing. It is built by S1.1." % DECLARATIONS)
        objects, sources = read_declarations(DECLARATIONS)
        self.assertEqual(declaration_problems(objects, sources), [])

    def test_the_test_vault_is_in_the_new_layout(self):
        if not TEST_VAULT.is_dir():
            self.fail("The test vault is missing.")
        files, folders = tree(TEST_VAULT)
        self.assertEqual(layout_problems(files, folders) + home_problems(files), [])

    def test_nothing_in_the_test_data_names_an_old_folder(self):
        problems = []
        for path in sorted(FIXTURES.rglob("*")):
            relative = path.relative_to(FIXTURES).as_posix()
            if path.is_file() and not relative.startswith("home/"):
                problems += old_path_problems(
                    relative, path.read_text(encoding="utf-8", errors="replace")
                )
        self.assertEqual(problems, [])

    def test_the_command_list_is_the_build_specs(self):
        result = subprocess.run(
            [sys.executable, str(WD), "--help"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(command_problems(result.stdout), [])


class S12Rulebook(FinishCase):
    """S1.2: the rulebook, the file that imports it, and four skills."""

    def test_the_rulebook_is_within_its_limit(self):
        self.assertEqual(rulebook_problems(self.text(PRODUCT / "AGENTS.md", "S1.2")), [])

    def test_claude_md_imports_the_rulebook(self):
        self.assertEqual(import_problems(self.text(PRODUCT / "CLAUDE.md", "S1.2")), [])

    def test_four_skills_with_short_descriptions(self):
        home = PRODUCT / "skills"
        if not home.is_dir():
            self.fail("%s is missing. It is built by S1.2." % home)
        skills = {}
        for folder in sorted(path for path in home.iterdir() if path.is_dir()):
            page = folder / "SKILL.md"
            skills[folder.name] = page.read_text(encoding="utf-8") if page.is_file() else None
        self.assertEqual(skill_problems(skills), [])


class S13Init(FinishCase):
    """S1.3: `wd init` makes the vault, and refuses a folder that is in use."""

    def test_init_makes_the_empty_vault(self):
        with tempfile.TemporaryDirectory() as folder:
            vault, _ = self.fresh_vault(folder, samples=False)
            self.assertEqual(init_problems(vault, samples=False), [])

    def test_init_with_samples(self):
        with tempfile.TemporaryDirectory() as folder:
            vault, _ = self.fresh_vault(folder, samples=True)
            self.assertEqual(init_problems(vault, samples=True), [])

    def test_init_refuses_a_folder_that_is_not_empty(self):
        with tempfile.TemporaryDirectory() as folder:
            vault, state = Path(folder) / "vault", Path(folder) / "state"
            vault.mkdir()
            state.mkdir()
            (vault / "kept.md").write_text("Already here.\n", encoding="utf-8")
            before = self.snapshot(vault)
            result = self.wd(["init", vault], state, "S1.3")
            after = self.snapshot(vault)
        self.assertNotEqual(result.returncode, 0, "`wd init` took a folder that is in use.")
        self.assertEqual(stage0.changed_files(before, after), [])


class S13GraphSetting(FinishCase):
    """S1.3: `wd graph-setting`, run as a command on settings that are wrong."""

    def settings(self, vault):
        return {name: (vault / SETTINGS / name).read_bytes() for name in ("graph.json", "app.json")}

    def test_graph_setting_repairs_the_settings_and_keeps_other_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            vault, state = self.fresh_vault(folder, samples=False)
            (vault / SETTINGS / "graph.json").write_text(json.dumps(WRONG_GRAPH), encoding="utf-8")
            (vault / SETTINGS / "app.json").write_text(json.dumps(WRONG_APP), encoding="utf-8")
            self.assertTrue(
                graph_problems(WRONG_GRAPH, WRONG_APP), "The wrong settings are not wrong.")

            wrong = self.settings(vault)
            before = self.snapshot(vault)
            tried = self.wd(["graph-setting", vault, "--dry-run"], state, "S1.3")
            self.assertEqual(tried.returncode, 0, tried.stdout + tried.stderr)
            self.assertEqual(
                stage0.changed_files(before, self.snapshot(vault)), [],
                "`wd graph-setting --dry-run` changed files in the vault.",
            )
            self.assertEqual(self.settings(vault), wrong)

            done = self.wd(["graph-setting", vault, "--apply"], state, "S1.3")
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertEqual(
                stage0.changed_files(before, self.snapshot(vault)),
                [SETTINGS + "/app.json", SETTINGS + "/graph.json"],
                "`wd graph-setting --apply` writes the two settings files and nothing else.",
            )
            graph = read_json(vault / SETTINGS / "graph.json")
            app = read_json(vault / SETTINGS / "app.json")
        self.assertEqual(graph_problems(graph, app), [])
        self.assertEqual(
            kept_key_problems("graph.json", WRONG_GRAPH, graph)
            + kept_key_problems("app.json", WRONG_APP, app),
            [], "`wd graph-setting --apply` changed a key that is not its own.",
        )


class S14CheckAndStatus(FinishCase):
    """S1.4: `wd check` and the status page."""

    def check(self, vault, state, made_up_home=True):
        """Run the check and prove it changed nothing. Returns its result and report."""
        before = self.snapshot(vault)
        result = self.wd(["check", vault], state, "S1.4", made_up_home)
        after = self.snapshot(vault)
        self.assertEqual(
            stage0.changed_files(before, after), [], "`wd check` changed files in the vault."
        )
        report = self.read_json(Path(state) / "check.json", "S1.4")
        self.assertEqual(check_report_problems(report), [], "check.json is not right.")
        self.assertEqual(stage0.stamp_problems(report, vault), [], "check.json is not right.")
        return result, report

    def test_check_passes_on_a_fresh_vault_with_samples(self):
        with tempfile.TemporaryDirectory() as folder:
            vault, state = self.fresh_vault(folder, samples=True)
            result, report = self.check(vault, state)
        self.assertEqual(report["problems"], [])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def a_sample_person_and_the_recording(self, vault):
        """A person and the recording `wd init --samples` made: (path, name, recording)."""
        people = sorted((vault / "objects" / "people").glob("*.md"))
        recordings = sorted((vault / RECORDINGS).glob("*.md"))
        if not people or not recordings:
            self.fail("`wd init --samples` left no sample person or no sample recording.")
        name = unquoted(front(people[0].read_text(encoding="utf-8")).get("name", ""))
        self.assertGreaterEqual(len(name.split()), 2, "The sample person has no full name.")
        return (
            "objects/people/" + people[0].stem, name, RECORDINGS + "/" + recordings[0].stem,
        )

    def test_check_finds_each_kind_of_wrong_note(self):
        # One invalid note for each requirement, and the matching kind for each.
        with tempfile.TemporaryDirectory() as folder:
            vault, state = self.fresh_vault(folder, samples=True)
            faults = faulty_notes(*self.a_sample_person_and_the_recording(vault))
            for path, text, _ in faults:
                (vault / path).write_text(text, encoding="utf-8")
            result, report = self.check(vault, state)
        self.assertNotEqual(result.returncode, 0, "`wd check` passed a vault with wrong notes.")
        self.assertEqual(
            fault_problems(report, faults), [], "`wd check` did not find each wrong note.")

    def measured(self, vault, state):
        report = self.check_measure(vault, state, made_up_home=True)
        return report["notes"], report["session_load"]

    def test_status_writes_the_page(self):
        with tempfile.TemporaryDirectory() as folder:
            vault, state = self.fresh_vault(folder, samples=True)
            _, report = self.check(vault, state)
            # Start from a page that is out of date, so that a real
            # update is needed. A page that was already right would
            # leave nothing to see.
            stale = "# Status\n\nAn old page. Nothing here is true any more.\n"
            (vault / STATUS_PAGE).write_text(stale, encoding="utf-8")

            before = self.snapshot(vault)
            tried = self.wd(["status", vault, "--dry-run"], state, "S1.4")
            self.assertEqual(tried.returncode, 0, tried.stdout + tried.stderr)
            self.assertEqual(
                stage0.changed_files(before, self.snapshot(vault)), [],
                "`wd status --dry-run` changed files in the vault.",
            )
            written = self.wd(["status", vault, "--apply"], state, "S1.4")
            self.assertEqual(written.returncode, 0, written.stdout + written.stderr)
            self.assertEqual(
                stage0.changed_files(before, self.snapshot(vault)), [STATUS_PAGE],
                "`wd status --apply` writes status.md and nothing else.",
            )
            page = (vault / STATUS_PAGE).read_text(encoding="utf-8")
            self.assertNotIn("An old page", page, "`wd status --apply` kept the old page.")

            notes, total = self.measured(vault, state)
            empty = Path(folder) / "empty"
            empty.mkdir()
            _, outside = self.measured(empty, state)
        load = {
            runtime: {"vault": total[runtime] - outside[runtime], "outside": outside[runtime]}
            for runtime, _ in RUNTIMES
        }
        self.assertEqual(
            status_problems(page, notes, len(report["problems"]), load), [],
            "The status page leaves these out.",
        )


class YouWillSee(FinishCase):
    """Stage 1, "You will see": the new vault with its samples, and what a session loads.

    These run on the real new vault. Both commands only read. Each is
    first proven to change nothing on a scratch vault, and its machine
    state goes to a scratch folder, never into the vault.
    """

    def test_the_new_vault_passes_the_check(self):
        vault = self.the_new_vault()
        with tempfile.TemporaryDirectory() as folder:
            practice, state = self.fresh_vault(folder, samples=True)
            before = self.snapshot(practice)
            self.wd(["check", practice], state, "S1.4")
            self.assertEqual(stage0.changed_files(before, self.snapshot(practice)), [])
        with tempfile.TemporaryDirectory() as state:
            self.run_read_only(["check"], vault, state, made_up_home=False)
            report = self.read_json(Path(state) / "check.json", "S1.4")
        self.assertEqual(check_report_problems(report), [])
        self.assertEqual(report["problems"], [])

    def test_the_status_page_is_there(self):
        vault = self.the_new_vault()
        self.assertTrue(
            (vault / "status.md").is_file(),
            "There is no status.md in %s. It is written by S1.R1." % vault,
        )

    def test_one_sample_in_each_object_home(self):
        self.assertEqual(one_sample_in_each_home(self.the_new_vault()), [])

    def test_the_session_load_is_within_the_limit(self):
        vault = self.the_new_vault()
        with tempfile.TemporaryDirectory() as practice:
            self.check_measure(TEST_VAULT, practice, made_up_home=True)
        with tempfile.TemporaryDirectory() as state:
            report = self.check_measure(vault, state, made_up_home=False)
        for runtime, label in RUNTIMES:
            print("\n    words a session loads in %s: %s of %d"
                  % (label, report["session_load"].get(runtime), SESSION_LOAD_LIMIT))
        self.assertEqual(load_problems(report["session_load"]), [])

    def test_checks_a_and_e_are_in_the_build_log(self):
        log = self.setting("WD_FINISH_BUILD_LOG", "The build log (--build-log)")
        if not log.is_file():
            self.fail("NOT RUN: the build log is not at %s." % log)
        self.assertEqual(moved_check_problems(log.read_text(encoding="utf-8")), [])


if __name__ == "__main__":
    unittest.main()
