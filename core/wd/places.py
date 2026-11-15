"""Where things live on the machine and in a vault."""

import os
from pathlib import Path

from wd import declarations

DEFAULT_STATE = Path(".local") / "state" / "workdesk" / "core"

# Build spec, "Object homes". An object's type is decided by its home.
# The homes are written down once, in the declarations.
OBJECT_HOMES = declarations.object_homes()
# The types that are linked by name.
LINKABLE = declarations.linkable()

# Build spec, "Signal homes".
BRIEFS = "signals/briefs"
SYNTHESES = "signals/syntheses"
SIGNAL_HOMES = [BRIEFS, SYNTHESES]

# Build spec, "Source homes, permanent from arrival".
SOURCE_HOMES = declarations.source_homes()

# The operator's own writing. Agents read it. No program writes there
# before stage 8.
WRITING = "writing"
# The files at the top of a vault. They are for agents and for the
# status page, so a link from one is not a connection between notes.
ROOT_FILES = ("AGENTS.md", "CLAUDE.md", "status.md")


def home():
    """The user's home folder. Tests point HOME at a made-up one."""
    return Path(os.environ.get("HOME") or Path.home())


def state_dir():
    """Machine state. WD_STATE_DIR moves it, so a test can use a scratch folder."""
    given = os.environ.get("WD_STATE_DIR", "").strip()
    return Path(given).expanduser() if given else home() / DEFAULT_STATE


def home_of(kind):
    """The home folder of one object type."""
    return dict(OBJECT_HOMES)[kind]


def in_home(relative, folder):
    """Is this note in this home?"""
    return relative.startswith(folder + "/")
