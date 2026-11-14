"""Where things live on the machine and in a vault."""

import os
import re
from pathlib import Path

DEFAULT_STATE = Path(".local") / "state" / "workdesk" / "core"

# Build spec, "Object homes". An object's type is decided by its home.
OBJECT_HOMES = [
    ("person", "atlas/people"),
    ("company", "atlas/companies"),
    ("term", "atlas/terms"),
    ("concept", "intel/concepts"),
    ("meeting", "atlas/meetings"),
    ("decision", "atlas/decisions"),
    ("quote", "gtd/reference/quotes"),
]

# A project object is the brief file in each project folder.
PROJECTS = "projects"
PROJECT_BRIEFS = [
    re.compile(r"^gtd/projects/[^/]+/brief\.md$"),
    re.compile(r"^atlas/clients/[^/]+/projects/[^/]+/brief\.md$"),
    re.compile(r"^atlas/businesses/[^/]+/projects/[^/]+/brief\.md$"),
    re.compile(r"^atlas/businesses/[^/]+/initiatives/[^/]+/projects/[^/]+/brief\.md$"),
]

# Build spec, "Signal homes" and "Source homes". Intake is the door only.
SIGNAL_HOMES = ["intel/briefings/daily", "intel/syntheses"]
SYNTHESES = "intel/syntheses"
SOURCE_HOMES = ["system/transcripts", "system/bookmarks", "system/session-log"]
INTAKE = "system/intake"

ARCHIVES = ("archive", "_archive")
# Files that sit in a home for navigation or agents. They are not notes.
NOT_NOTES = ("index.md", "AGENTS.md", "CLAUDE.md")


def home():
    """The user's home folder. Tests point HOME at a made-up one."""
    return Path(os.environ.get("HOME") or Path.home())


def state_dir():
    """Machine state. WD_STATE_DIR moves it, so a test can use a scratch folder."""
    given = os.environ.get("WD_STATE_DIR", "").strip()
    return Path(given).expanduser() if given else home() / DEFAULT_STATE


def in_archive(relative):
    return any(part in ARCHIVES for part in relative.split("/")[:-1])


def is_project_brief(relative):
    return not in_archive(relative) and any(
        pattern.match(relative) for pattern in PROJECT_BRIEFS
    )


def in_home(relative, folder):
    """Is this note in this home? Navigation files and archives are not."""
    return (
        relative.startswith(folder + "/")
        and relative.rsplit("/", 1)[-1] not in NOT_NOTES
        and not in_archive(relative)
    )
