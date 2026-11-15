"""`wd check --measure <vault>`: count what is in a vault today.

It reads the vault and writes one file, `measure.json`, into machine
state. It never writes inside the vault.
"""

import datetime
import json
import os
import re
from pathlib import Path

from wd import graph, notes, places

REPORT = "measure.json"
EXAMPLES = 5
IMPORT = re.compile(r"(?<![\w`@/])@([\w~.][\w~./-]*)")
WEB_ADDRESS = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)
NO_VALUE = ("", "null", "~", "[]", "none")
MAX_IMPORT_DEPTH = 5

LABELS = [
    ("broken_links", "Links in objects and syntheses with a missing target"),
    ("unlinked_objects", "Objects with no link in or out"),
    ("people_without_full_name", "People whose first heading has fewer than two words"),
    ("meetings_with_missing_source", "Meetings with a missing source"),
    ("sources_unprocessed", "Sources that produced nothing"),
]
RUNTIME_NAMES = [("claude-code", "Claude Code"), ("codex", "Codex")]


def homes(vault):
    """Each home and the notes in it."""
    folders = [folder for _, folder in places.OBJECT_HOMES]
    folders += places.SIGNAL_HOMES + places.SOURCE_HOMES
    return {
        folder: [name for name in vault.notes if places.in_home(name, folder)]
        for folder in folders
    }


def objects(by_home):
    found = []
    for _, folder in places.OBJECT_HOMES:
        found += by_home[folder]
    return found


def broken_links(vault, by_home):
    """Links in the object homes and syntheses whose target is missing."""
    found = []
    for name in objects(by_home) + by_home[places.SYNTHESES]:
        for target in notes.link_targets(vault.text(name)):
            if vault.resolve(target, name) is None:
                found.append("%s -> %s" % (name, target))
    return found


def people_without_full_name(vault, by_home):
    found = []
    for name in by_home[places.home_of("person")]:
        _, body = notes.front(vault.text(name))
        if len(notes.words(notes.first_heading(body))) < 2:
            found.append(name)
    return found


def missing_source(vault, value, name):
    """Does a meeting's `source` value name a file that is missing?

    A link or a path names a file. A web address does not, and neither
    does a plain label such as the name of the recorder.
    """
    if value.lower() in NO_VALUE:
        return False
    targets = notes.link_targets(value)
    if not targets:
        if WEB_ADDRESS.match(value) or not ("/" in value or value.endswith(".md")):
            return False
        targets = [value]
    return any(vault.resolve(target, name) is None for target in targets)


def meetings_with_missing_source(vault, by_home):
    found = []
    for name in by_home[places.home_of("meeting")]:
        keys, _ = notes.front(vault.text(name))
        if missing_source(vault, keys.get("source", ""), name):
            found.append(name)
    return found


def sources_unprocessed(vault, by_home):
    """Sources whose `produced` list is empty: nothing has been made from them.

    A source with no `produced` key counts as well. Unknown is never
    healthy.
    """
    found = []
    for folder in places.SOURCE_HOMES:
        for name in by_home[folder]:
            keys, _ = notes.front(vault.text(name))
            if keys.get("produced", "").lower() in NO_VALUE:
                found.append(name)
    return found


def read(path):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def with_imports(path, seen, depth=0):
    """A file's words, plus the words of every file it imports with `@path`."""
    path = Path(path)
    if not path.is_file():
        return 0
    real = os.path.realpath(str(path))
    if real in seen:
        return 0
    seen.add(real)
    _, body = notes.front(read(path))
    total = len(notes.words(body))
    for named in IMPORT.findall(notes.without_code(body)) if depth < MAX_IMPORT_DEPTH else []:
        named = named.rstrip(".")
        target = Path(named).expanduser() if named.startswith("~") else path.parent / named
        total += with_imports(target, seen, depth + 1)
    return total


def rule_words(folder, seen):
    """Every rule file with no path limit."""
    total = 0
    for here, folders, names in os.walk(str(folder), followlinks=True):
        folders.sort()
        for name in sorted(names):
            if not name.endswith(".md"):
                continue
            path = Path(here) / name
            real = os.path.realpath(str(path))
            if real in seen:
                continue
            seen.add(real)
            keys, body = notes.front(read(path))
            if "paths" not in keys:
                total += len(notes.words(body))
    return total


def skill_files(folder):
    """Each skill's SKILL.md, one or two folders down."""
    folder = Path(folder)
    if not folder.is_dir():
        return []
    found = []
    for child in sorted(folder.iterdir()):
        if (child / "SKILL.md").is_file():
            found.append(child / "SKILL.md")
        elif child.is_dir():
            found += [
                grandchild / "SKILL.md"
                for grandchild in sorted(child.iterdir())
                if (grandchild / "SKILL.md").is_file()
            ]
    return found


def plugin_skill_folders(home, root):
    """The skills folder of every Claude Code plugin that is installed and switched on.

    The settings are layered: the user's file, then the vault's, then
    the vault's local file. Each later file wins, plugin by plugin. So
    a plugin the user switched on and the vault switched off is off,
    and one the user switched off and the vault switched on is on.
    """
    claude = Path(home) / ".claude"
    chosen = {}
    for settings in (
        claude / "settings.json",
        Path(root) / ".claude" / "settings.json",
        Path(root) / ".claude" / "settings.local.json",
    ):
        try:
            said = json.loads(read(settings) or "{}").get("enabledPlugins", {})
        except (ValueError, AttributeError):
            continue
        if isinstance(said, dict):
            chosen.update(said)
    switched_on = {name for name, on in chosen.items() if on is True}
    try:
        installed = json.loads(read(claude / "plugins" / "installed_plugins.json") or "{}")
    except ValueError:
        return []
    plugins = installed.get("plugins", {}) if isinstance(installed, dict) else {}
    folders = []
    for name in sorted(plugins if isinstance(plugins, dict) else {}):
        entries = plugins[name] if isinstance(plugins[name], list) else [plugins[name]]
        for entry in entries:
            where = entry.get("installPath") if isinstance(entry, dict) else None
            if name in switched_on and isinstance(where, str) and where:
                # A path that does not start at the top is under the .claude folder.
                folders.append((claude / where) / "skills")
    return folders


def skill_words(folders, seen):
    """Every skill description."""
    total = 0
    for folder in folders:
        for path in skill_files(folder):
            real = os.path.realpath(str(path))
            if real in seen:
                continue
            seen.add(real)
            keys, _ = notes.front(read(path))
            total += len(notes.words(keys.get("description", "")))
    return total


def session_load(root, home):
    """The words each runtime loads at the start of a session.

    Build spec, stage 1, "Session load". Claude Code: the user and vault
    CLAUDE.md files and what they import, every rule file with no path
    limit, and every skill description, including the skills of plugins
    that are switched on. Codex: the user and vault
    AGENTS.md files and every skill description.
    """
    root, home = Path(root), Path(home)
    seen = set()
    claude = {
        "instructions": sum(
            with_imports(path, seen)
            for path in (
                home / ".claude" / "CLAUDE.md",
                root / "CLAUDE.md",
                root / ".claude" / "CLAUDE.md",
            )
        ),
        "rules": sum(
            rule_words(folder, seen)
            for folder in (home / ".claude" / "rules", root / ".claude" / "rules")
        ),
        "skills": skill_words(
            [home / ".claude" / "skills", root / ".claude" / "skills"]
            + plugin_skill_folders(home, root),
            seen,
        ),
    }
    seen = set()
    codex = {
        # Codex does not follow `@path` imports.
        "instructions": sum(
            with_imports(path, seen, depth=MAX_IMPORT_DEPTH)
            for path in (home / ".codex" / "AGENTS.md", root / "AGENTS.md")
        ),
        "rules": 0,
        "skills": skill_words(
            (
                home / ".codex" / "skills",
                home / ".agents" / "skills",
                root / ".codex" / "skills",
                root / ".agents" / "skills",
            ),
            seen,
        ),
    }
    return {"claude-code": claude, "codex": codex}


def measure(root, home):
    """Measure one vault. Returns the report."""
    vault = notes.Vault(root)
    by_home = homes(vault)
    lists = {
        "broken_links": broken_links(vault, by_home),
        # The same rule as `wd check`: see `wd.graph`.
        "unlinked_objects": graph.unlinked_objects(vault),
        "people_without_full_name": people_without_full_name(vault, by_home),
        "meetings_with_missing_source": meetings_with_missing_source(vault, by_home),
        "sources_unprocessed": sources_unprocessed(vault, by_home),
    }
    parts = session_load(vault.root, home)
    report = {
        "vault": str(vault.root),
        "run_at": datetime.datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "notes": {folder: len(names) for folder, names in by_home.items()},
    }
    for name, _ in LABELS:
        report[name] = len(lists[name])
    report["session_load"] = {
        runtime: sum(counts.values()) for runtime, counts in parts.items()
    }
    report["session_load_parts"] = parts
    report["examples"] = {name: found[:EXAMPLES] for name, found in lists.items()}
    report["unreadable"] = sorted(set(vault.unreadable))
    return report


def table(report):
    rows = [("Notes", "")]
    rows += [("  " + folder, count) for folder, count in report["notes"].items()]
    rows.append(("", ""))
    rows += [(label, report[name]) for name, label in LABELS]
    rows += [
        ("Session load, %s (words)" % label, report["session_load"][runtime])
        for runtime, label in RUNTIME_NAMES
    ]
    width = max(len(label) for label, _ in rows)
    lines = ["Measured %s at %s" % (report["vault"], report["run_at"]), ""]
    for label, value in rows:
        if value == "":
            lines.append(label)
        else:
            lines.append("%s  %s" % (label.ljust(width), format(value, ",").rjust(7)))
    return "\n".join(lines)


def save(report, state, name=REPORT):
    """Write a report into machine state, whole or not at all."""
    state = Path(state)
    state.mkdir(parents=True, exist_ok=True)
    scratch = state / (".%s.%d" % (name, os.getpid()))
    scratch.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    os.replace(str(scratch), str(state / name))
    return state / name


def run(arguments, out, err):
    """`wd check --measure <vault>`. Returns a code."""
    if len(arguments) != 1:
        print("usage: wd check --measure <vault>", file=err)
        return 2
    root = Path(arguments[0]).expanduser()
    if not root.is_dir():
        print("wd check --measure: there is no vault at %s." % root, file=err)
        return 1
    root, state = root.resolve(), places.state_dir().resolve()
    if state == root or root in state.parents:
        print(
            "wd check --measure: machine state is inside the vault (%s). "
            "Nothing was measured, because this command never writes there." % state,
            file=err,
        )
        return 1
    report = measure(root, places.home())
    saved = save(report, state)
    print(table(report), file=out)
    print("\nSaved to %s" % saved, file=out)
    if report["unreadable"]:
        print(
            "wd check --measure: %d files or folders could not be read, so the "
            "numbers are not complete. They are listed in the saved report."
            % len(report["unreadable"]),
            file=err,
        )
        return 1
    return 0
