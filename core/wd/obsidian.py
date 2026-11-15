"""`wd graph-setting <vault>`: the Obsidian settings Workdesk owns.

Two files under `.obsidian/`:

    graph.json   colorGroups   one color for each object type, by its home
                 search        hides sources, briefs and the root files,
                               and nothing else
    app.json     alwaysUpdateLinks   a rename carries every link with it
                 newLinkFormat       new links are written with the full path
                 useMarkdownLinks    links are written in double brackets

Only those keys are ever changed. Every other key in the two files is
kept as it is. `wd init` writes the same settings through `apply`.

The colors and the three link settings are in `core/product/obsidian.json`.
The homes come from the declarations.
"""

import json
import os
import re
import stat
import tempfile
from pathlib import Path

from wd import declarations, places

SETTINGS = ".obsidian"
GRAPH = "graph.json"
APP = "app.json"
PRODUCT = Path(__file__).resolve().parents[1] / "product"
PRODUCT_FILE = PRODUCT / "obsidian.json"

COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
SHOWN_MAX = 100

OK = 0
FAILED = 1
USAGE = 2


class SettingError(ValueError):
    """The settings cannot be read or cannot be written safely."""


# ---- writing ----

def _mode_for(path):
    """The permissions the file has now, or the ones a new file would get."""
    try:
        return stat.S_IMODE(os.stat(str(path)).st_mode)
    except FileNotFoundError:
        mask = os.umask(0)
        os.umask(mask)
        return 0o666 & ~mask


def write_safely(path, data, before):
    """Put `data` at `path` through a hidden temporary file and a rename.

    `before` is what the file held when it was read, or None when it was
    not there. If the file has changed since, nothing is written. A
    link is never written through.

    The temporary file gets a name nothing else has, and is made only
    if nothing is there already, so a file or a link left at a guessed
    name is never opened. Only the file this run made is cleaned up.
    """
    path = Path(path)
    if path.is_symlink():
        raise SettingError("%s is a link, so nothing was written to it." % path)
    try:
        now = path.read_bytes()
    except FileNotFoundError:
        now = None
    if now != before:
        raise SettingError(
            "%s changed while this was running. Nothing was written to it." % path
        )
    mode = _mode_for(path)
    made = None
    try:
        handle, made = tempfile.mkstemp(
            prefix=".%s." % path.name, suffix=".tmp", dir=str(path.parent)
        )
        with os.fdopen(handle, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(made, mode)
        os.replace(made, str(path))
        made = None
    finally:
        if made is not None:
            try:
                os.unlink(made)
            except OSError:
                pass


# ---- what the settings should be ----

def product(path=None):
    """The colors and the link settings kept in the product folder."""
    path = Path(path) if path else PRODUCT_FILE
    try:
        found = json.loads(path.read_text(encoding="utf-8"))
    except OSError:
        raise SettingError("%s is missing." % path)
    except ValueError as problem:
        raise SettingError("%s is not valid JSON: %s" % (path, problem))
    if not isinstance(found, dict):
        raise SettingError("%s is not a group of values." % path)
    colors, app = found.get("graph-colors"), found.get("app")
    if not isinstance(app, dict) or not app:
        raise SettingError("%s: app is not a group of settings." % path)
    kinds = [kind for kind, _ in places.OBJECT_HOMES]
    if not isinstance(colors, dict) or sorted(colors) != sorted(kinds):
        raise SettingError(
            "%s: graph-colors must hold one color for each object type: %s."
            % (path, ", ".join(kinds))
        )
    for kind in kinds:
        if not isinstance(colors[kind], str) or not COLOR.match(colors[kind]):
            raise SettingError(
                "%s: the color of %s is not written like #4C8DF6." % (path, kind)
            )
    if len({color.lower() for color in colors.values()}) != len(colors):
        raise SettingError("%s: two object types share a color." % path)
    return {"app": app, "graph-colors": colors}


def hidden_folders():
    """The folders the graph leaves out: every source, and the briefs."""
    tops = []
    for home in places.SOURCE_HOMES:
        top = home.split("/")[0]
        if top not in tops:
            tops.append(top)
    return tops + [places.BRIEFS]


def _expression(text):
    """A path as a regular expression written between slashes."""
    return re.escape(text).replace("/", "\\/")


def search():
    """The graph's filter: what the graph leaves out, and nothing else.

    Obsidian's `path:` matches its words anywhere in a path, so plain
    `-path:sources` would also hide `writing/resources/note.md`. Each
    term is a regular expression tied to the start of the path instead.
    A folder is everything under it at the top of the vault. A root
    file is that one file at the top of the vault.
    """
    parts = ["-path:/^%s\\//" % _expression(folder) for folder in hidden_folders()]
    parts += ["-path:/^%s$/" % _expression(name) for name in places.ROOT_FILES]
    return " ".join(parts)


def wanted(path=None):
    """The keys Workdesk owns in each settings file, and their values."""
    kept = product(path)
    homes = declarations.objects()
    groups = [
        {
            "query": "path:%s" % homes[kind]["home"],
            "color": {"a": 1, "rgb": int(kept["graph-colors"][kind][1:], 16)},
        }
        for kind, _ in places.OBJECT_HOMES
    ]
    return [
        (GRAPH, {"colorGroups": groups, "search": search()}),
        (APP, dict(kept["app"])),
    ]


# ---- comparing with what is there ----

class Missing:
    """Stands for a key that is not in the file."""


def _read(path):
    """(the bytes on disk or None, the values in the file)."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return None, {}
    except OSError as problem:
        raise SettingError("%s cannot be read: %s" % (path, problem))
    if not raw.strip():
        return raw, {}
    try:
        found = json.loads(raw.decode("utf-8"))
    except ValueError as problem:
        raise SettingError(
            "%s is not valid JSON, so it was left alone: %s" % (path, problem)
        )
    if not isinstance(found, dict):
        raise SettingError("%s is not a group of settings, so it was left alone." % path)
    return raw, found


def plan(vault, path=None):
    """What each settings file holds now and what it would hold.

    Returns one entry for each file: its name, its path, the bytes on
    disk (None when it is not there), the text it would hold, and the
    changes as (key, old value, new value). A missing key's old value is
    the class `Missing`. A settings folder or file that is a link is
    refused.
    """
    vault = Path(vault)
    folder = vault / SETTINGS
    names = wanted(path)
    # A link is never followed and never replaced. Both files are looked
    # at before either is read, so nothing is made on the way to a refusal.
    for place in [folder] + [folder / name for name, _ in names]:
        if place.is_symlink():
            raise SettingError("%s is a link, so nothing was changed." % place)
    if folder.exists() and not folder.is_dir():
        raise SettingError("%s is not a folder, so nothing was changed." % folder)
    entries = []
    for name, keys in names:
        where = folder / name
        raw, found = _read(where)
        changes = [
            (key, found.get(key, Missing), value)
            for key, value in keys.items()
            if key not in found or found[key] != value or type(found[key]) is not type(value)
        ]
        merged = dict(found)
        merged.update(keys)
        text = json.dumps(merged, indent=2, ensure_ascii=False) + "\n"
        entries.append({
            "name": name, "path": where, "raw": raw, "text": text, "changes": changes,
        })
    return entries


def apply(vault, path=None):
    """Write the settings. Returns the plan that was carried out.

    Both files are read and checked before either is written. A file
    that already holds the right values is not touched.
    """
    entries = plan(vault, path)
    for entry in entries:
        if not entry["changes"]:
            continue
        entry["path"].parent.mkdir(exist_ok=True)
        write_safely(entry["path"], entry["text"].encode("utf-8"), entry["raw"])
    return entries


# ---- the command ----

def _shown(value):
    if value is Missing:
        return "not set"
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= SHOWN_MAX else text[:SHOWN_MAX - 3] + "..."


def describe(entries, done):
    """Plain lines on what changed, or what would."""
    lines = []
    for entry in entries:
        where = "%s/%s" % (SETTINGS, entry["name"])
        if not entry["changes"]:
            lines.append("%s: already right. Nothing to change." % where)
            continue
        if entry["raw"] is None:
            lines.append("%s: %s." % (where, "made" if done else "would be made"))
        else:
            lines.append(
                "%s: %s. Every other key is kept."
                % (where, "changed" if done else "would change")
            )
        for key, old, new in entry["changes"]:
            lines.append("  %s" % key)
            lines.append("    from: %s" % _shown(old))
            lines.append("    to:   %s" % _shown(new))
    return lines


def looks_like_a_vault(vault):
    """A Workdesk vault holds at least one object home."""
    return any((Path(vault) / home).is_dir() for _, home in places.OBJECT_HOMES)


def run(arguments, out, err):
    """`wd graph-setting <vault> --dry-run` or `--apply`. Returns a code."""
    flags = [argument for argument in arguments if argument.startswith("--")]
    given = [argument for argument in arguments if not argument.startswith("--")]
    modes = [flag for flag in flags if flag in ("--dry-run", "--apply")]
    if len(given) != 1 or len(modes) != 1 or len(flags) != 1:
        print("usage: wd graph-setting <vault> --dry-run", file=err)
        print("       wd graph-setting <vault> --apply", file=err)
        print("--dry-run shows what would change. --apply changes it.", file=err)
        return USAGE
    vault = Path(given[0]).expanduser()
    if not vault.is_dir():
        print("wd graph-setting: there is no vault at %s." % vault, file=err)
        return FAILED
    if not looks_like_a_vault(vault):
        print(
            "wd graph-setting: %s has none of the object folders, so it is not a "
            "Workdesk vault. Nothing was changed." % vault,
            file=err,
        )
        return FAILED
    doing = modes[0] == "--apply"
    try:
        entries = apply(vault) if doing else plan(vault)
    except (SettingError, OSError) as problem:
        print("wd graph-setting: %s" % problem, file=err)
        return FAILED
    print("\n".join(describe(entries, doing)), file=out)
    if not doing and any(entry["changes"] for entry in entries):
        print("\nNothing was written. Run it again with --apply to make the change.", file=out)
    return OK
