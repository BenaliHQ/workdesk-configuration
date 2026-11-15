"""`wd init <vault>`: make a new, empty vault.

It makes the folders of the new layout, copies the rulebook and the
skills from `core/product/`, and writes the Obsidian settings. With
`--samples` it also copies the nine made-up sample notes.

It refuses a path that exists and is not empty, and changes nothing
there. It never writes outside the folder it is given. It does not
write `status.md` (that is `wd status`), and it writes nothing under
`writing/`.
"""

import os
from pathlib import Path

from wd import obsidian, places

PRODUCT = Path(__file__).resolve().parents[1] / "product"
SKILLS = PRODUCT / "skills"
SAMPLES = PRODUCT / "samples"

# The root files that are copied. `status.md` is written by `wd status`.
RULEBOOK_FILES = ("AGENTS.md", "CLAUDE.md")
# Where each runtime looks for skills: Claude Code, then Codex.
SKILL_FOLDERS = (".claude/skills", ".agents/skills")
SKILL_PAGE = "SKILL.md"

OK = 0
FAILED = 1
USAGE = 2


class InitError(ValueError):
    """The vault cannot be made."""


def folders():
    """Every folder of the new layout, in the build spec's order.

    The source homes and the object homes come from the declarations.
    """
    return (
        list(places.SOURCE_HOMES)
        + [home for _, home in places.OBJECT_HOMES]
        + [places.WRITING]
        + list(places.SIGNAL_HOMES)
    )


def _files_in(folder):
    """Every file under a folder, as paths from it. Hidden files are left out."""
    found = []
    for here, names, file_names in os.walk(str(folder)):
        names[:] = sorted(name for name in names if not name.startswith((".", "__")))
        for name in sorted(file_names):
            if not name.startswith("."):
                found.append((Path(here) / name).relative_to(folder).as_posix())
    return found


def rulebook():
    """(path in the vault, file to copy) for each root file."""
    copies = []
    for name in RULEBOOK_FILES:
        if not (PRODUCT / name).is_file():
            raise InitError("%s is missing from the product folder." % name)
        copies.append((name, PRODUCT / name))
    return copies


def skill_names():
    """The skills in the product folder, by name."""
    names = sorted(
        path.name for path in (SKILLS.iterdir() if SKILLS.is_dir() else [])
        if path.is_dir() and (path / SKILL_PAGE).is_file()
    )
    if not names:
        raise InitError("There are no skills in the product folder.")
    return names


def skills():
    """(path in the vault, file to copy) for each skill file, in both skill folders."""
    copies = []
    for place in SKILL_FOLDERS:
        for name in skill_names():
            for relative in _files_in(SKILLS / name):
                copies.append(
                    ("%s/%s/%s" % (place, name, relative), SKILLS / name / relative)
                )
    return copies


def samples():
    """(path in the vault, file to copy) for each sample note.

    The samples are kept in the vault's own layout. One that is not in
    an object home or a source home is refused, so that no folder
    outside the layout is ever made.
    """
    homes = [home for _, home in places.OBJECT_HOMES] + list(places.SOURCE_HOMES)
    copies = []
    for relative in _files_in(SAMPLES) if SAMPLES.is_dir() else []:
        if not relative.endswith(".md"):
            continue
        if relative.rsplit("/", 1)[0] not in homes:
            raise InitError(
                "The sample %s is not in an object home or a source home." % relative
            )
        copies.append((relative, SAMPLES / relative))
    if not copies:
        raise InitError("There are no samples in the product folder.")
    return copies


def why_not(root):
    """One plain sentence on why this path cannot be a new vault, or None."""
    if not os.path.lexists(str(root)):
        return None
    if not root.is_dir():
        return "%s is there already and is not a folder, so nothing was made." % root
    try:
        holds = os.listdir(str(root))
    except OSError as problem:
        return "%s cannot be opened (%s), so nothing was made." % (root, problem)
    if holds:
        return "%s is there already and is not empty, so nothing was made." % root
    return None


def make(root, with_samples=False):
    """Make the vault. Returns what was made, for the report.

    Everything to copy is found first, so a product folder with a piece
    missing stops this before the vault folder is made.
    """
    root = Path(root)
    copies = rulebook() + skills()
    sample_copies = samples() if with_samples else []
    settings = obsidian.wanted()  # Read now, so a bad colors file stops this early.

    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    for folder in folders():
        (root / folder).mkdir(parents=True)
    for relative, source in copies + sample_copies:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        obsidian.write_safely(target, source.read_bytes(), None)
    (root / obsidian.SETTINGS).mkdir()
    obsidian.apply(root)
    return {
        "root": root,
        "folders": folders(),
        "rulebook": [relative for relative, _ in rulebook()],
        "skills": skill_names(),
        "settings": [name for name, _ in settings],
        "samples": [relative for relative, _ in sample_copies],
    }


def report(made):
    """Plain lines on what was made."""
    lines = ["Made a new vault at %s." % made["root"], ""]
    lines.append("Folders (%d):" % len(made["folders"]))
    lines += ["  %s/" % folder for folder in made["folders"]]
    lines += ["", "The rulebook:"]
    lines += ["  %s" % name for name in made["rulebook"]]
    lines += ["", "Skills (%d), each in %s:" % (
        len(made["skills"]), " and ".join("%s/" % place for place in SKILL_FOLDERS))]
    lines += ["  %s" % name for name in made["skills"]]
    lines += ["", "Obsidian settings:"]
    lines.append(
        "  %s/%s  one color for each object type. Sources, briefs and the root "
        "files are hidden from the graph." % (obsidian.SETTINGS, obsidian.GRAPH)
    )
    lines.append(
        "  %s/%s  links follow a rename, and new links are written with the full path."
        % (obsidian.SETTINGS, obsidian.APP)
    )
    if made["samples"]:
        lines += ["", "Samples (%d), made up and marked `sample: true`:" % len(made["samples"])]
        lines += ["  %s" % relative for relative in made["samples"]]
    lines += [
        "",
        "Not made: status.md. `wd status %s --apply` writes it." % made["root"],
        "Next: open the folder in Obsidian as a vault.",
    ]
    return lines


def run(arguments, out, err):
    """`wd init <vault>` and `wd init <vault> --samples`. Returns a code."""
    flags = [argument for argument in arguments if argument.startswith("--")]
    given = [argument for argument in arguments if not argument.startswith("--")]
    if len(given) != 1 or any(flag != "--samples" for flag in flags):
        print("usage: wd init <vault> [--samples]", file=err)
        return USAGE
    root = Path(given[0]).expanduser()
    refused = why_not(root)
    if refused:
        print("wd init: %s" % refused, file=err)
        return FAILED
    try:
        made = make(root, with_samples="--samples" in flags)
    except (InitError, obsidian.SettingError) as problem:
        print("wd init: %s" % problem, file=err)
        return FAILED
    except OSError as problem:
        print(
            "wd init: stopped part way (%s). What was made so far is still in %s."
            % (problem, root),
            file=err,
        )
        return FAILED
    print("\n".join(report(made)), file=out)
    return OK
