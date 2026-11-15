"""A tiny made-up vault with nothing wrong in it, for tests to build and then break.

One note in each object home, one recording with its passages marked,
one synthesis and the root files. Every name is made up. Each test
copies `CLEAN`, changes one note, and builds the result in a scratch
folder.
"""

from pathlib import Path

RECORDING = "sources/recordings/2026-11-12-acme-intro"
SAM = "objects/people/sam-rivera.md"
ACME = "objects/companies/acme.md"
ROLLOUT = "objects/projects/acme-rollout.md"
TERM = "objects/terms/bespoke-systems.md"
CONCEPT = "objects/concepts/two-way-door.md"
MEETING = "objects/meetings/2026-11-12-acme-intro.md"
DECISION = "objects/decisions/2026-11-12-rollout-date.md"
QUOTE = "objects/quotes/sam-rivera-on-plans.md"
SYNTHESIS = "signals/syntheses/2026-11-13-plans-before-december.md"

SAM_LINK = "[[objects/people/sam-rivera|Sam Rivera]]"
ACME_LINK = "[[objects/companies/acme|Acme]]"

CLEAN = {
    "AGENTS.md": "# Rules\n\nWrite full names. Point every statement at its passage.\n",
    "CLAUDE.md": "@AGENTS.md\n",
    ".claude/skills/context/SKILL.md":
        "---\nname: context\ndescription: Gather what is known about one object.\n---\n# Context\n",
    ".agents/skills/context/SKILL.md":
        "---\nname: context\ndescription: Gather what is known about one object.\n---\n# Context\n",
    SAM: (
        "---\ntype: person\nname: Sam Rivera\naliases: [Samuel Rivera]\nprivate: false\n"
        "email: sam@acme.example\nsample: true\n---\n"
        "# Sam Rivera\n\n"
        "Leads operations at %s. Runs the [[objects/projects/acme-rollout|Acme Rollout]].\n\n"
        "## Currently\n\n"
        "- Leads operations at Acme. 2026-11-12, [[%s#^p0002]]\n\n"
        "## History\n\n"
        "- 2026-11-12 | Leads operations at Acme | stated | [[%s#^p0002]] | run-20261112-1215\n"
    ) % (ACME_LINK, RECORDING, RECORDING),
    ACME: (
        "---\ntype: company\nname: Acme\naliases: []\nprivate: false\nweb: acme.example\n"
        "sample: true\n---\n"
        "# Acme\n\n"
        "A maker of shop fittings. %s leads operations.\n\n"
        "## Currently\n\n"
        "- Wants one plan before December. 2026-11-12, [[%s#^p0001]]\n\n"
        "## History\n\n"
        "- 2026-11-12 | Wants one plan before December | stated | [[%s#^p0001]] | run-20261112-1215\n"
    ) % (SAM_LINK, RECORDING, RECORDING),
    ROLLOUT: (
        "---\ntype: project\nname: Acme Rollout\naliases: []\nprivate: false\nsample: true\n---\n"
        "# Acme Rollout\n\n"
        "Putting scanners on the floor at %s. Led by %s.\n\n"
        "## Currently\n\n"
        "- Starts in December. 2026-11-12, [[%s#^p0003]]\n\n"
        "## History\n\n"
        "- 2026-11-12 | Starts in December | stated | [[%s#^p0003]] | run-20261112-1215\n"
    ) % (ACME_LINK, SAM_LINK, RECORDING, RECORDING),
    TERM: (
        "---\ntype: term\nname: bespoke systems\naliases: []\nprivate: false\nsample: true\n---\n"
        "# bespoke systems\n\n"
        "Systems built for one company and kept up by nobody else. %s raised it first.\n\n"
        "## History\n\n"
        "- 2026-11-12 | Tried twice at Acme | stated | [[%s#^p0002]] | run-20261112-1215\n"
    ) % (SAM_LINK, RECORDING),
    # A concept with no history yet leaves the heading out.
    CONCEPT: (
        "---\ntype: concept\nname: Two-Way Door\naliases: []\nprivate: false\n"
        "from: Robin Hale\nsample: true\n---\n"
        "# Two-Way Door\n\n"
        "A choice you can walk back through. It fits the "
        "[[objects/projects/acme-rollout|Acme Rollout]].\n"
    ),
    MEETING: (
        "---\ntype: meeting\nprivate: false\ndate: 2026-11-12\n"
        "attendees: [\"%s\"]\n"
        "source: \"[[%s]]\"\nsample: true\n---\n"
        "# Acme intro\n\n"
        "First meeting with %s of %s.\nThey want one plan before December.\n\n"
        "## Decisions\n\n"
        "- [[objects/decisions/2026-11-12-rollout-date]]\n\n"
        "## Promises\n\n"
        "## Detail\n\n"
        "| Who | Said |\n|---|---|\n"
        "| [[objects/people/sam-rivera\\|Sam Rivera]] | They tried "
        "[[objects/terms/bespoke-systems\\|bespoke systems]] twice. [[%s#^p0002]] |\n"
    ) % (SAM_LINK, RECORDING, SAM_LINK, ACME_LINK, RECORDING),
    DECISION: (
        "---\ntype: decision\nprivate: false\ndate: 2026-11-12\n"
        "source: \"[[%s#^p0003]]\"\nsample: true\n---\n"
        "# Rollout date\n\n"
        "The [[objects/projects/acme-rollout|Acme Rollout]] starts in December. Decided by %s.\n\n"
        "## History\n\n"
        "- 2026-11-12 | Decided that the rollout starts in December | stated | "
        "[[%s#^p0003]] | run-20261112-1215\n"
    ) % (RECORDING, SAM_LINK, RECORDING),
    QUOTE: (
        "---\ntype: quote\nprivate: false\nby: Sam Rivera\n"
        "source: \"[[%s#^p0001]]\"\ndate: 2026-11-12\nsample: true\n---\n"
        "# One plan\n\n"
        "> We want one plan before December.\n\n"
        "Said by %s. [[%s#^p0001]]\n"
    ) % (RECORDING, SAM_LINK, RECORDING),
    SYNTHESIS: (
        "---\ntype: synthesis\ndate: 2026-11-13\n---\n"
        "# Plans before December\n\n"
        "%s wants one plan for %s. [[%s#^p0001]]\n\n"
        "## Sources\n\n- [[%s]]\n"
    ) % (SAM_LINK, ACME_LINK, RECORDING, RECORDING),
    RECORDING + ".md": (
        "---\ntype: source\nkind: meeting-recording\ntitle: Acme intro\ndate: 2026-11-12\n"
        "author: Robin Hale\nsent-by: Robin Hale\nstatus: read\nstarred: false\nprivate: false\n"
        "take: They want one plan.\n"
        "produced: [\"[[objects/meetings/2026-11-12-acme-intro]]\"]\n"
        "sha256-original: 0000000000000000000000000000000000000000000000000000000000000000\n"
        "sample: true\n---\n"
        "Sam Rivera: We want one plan before December. ^p0001\n\n"
        "Sam Rivera: I lead operations. We tried bespoke systems twice. ^p0002\n\n"
        "Robin Hale: Then the rollout starts in December. ^p0003\n"
    ),
}


def build(folder, files):
    """Write these files under a folder. Returns the folder."""
    for name, text in files.items():
        path = Path(folder) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return Path(folder)


def with_files(changes):
    """A copy of the clean vault with some notes replaced, added, or taken out (None)."""
    files = dict(CLEAN)
    for name, text in changes.items():
        if text is None:
            files.pop(name, None)
        else:
            files[name] = text
    return files
