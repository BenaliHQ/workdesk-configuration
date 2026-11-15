"""The stage 1 finish test's own checks, tried on right and wrong inputs.

The finish test cannot pass until stage 1 is built. These tests make
sure that when it does pass, it means something: each one feeds a check
an input that must not get through.
"""

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

import stage1_finish as finish  # noqa: E402
import test_budget  # noqa: E402

CORE = TESTS.parent


def good_objects():
    found = {}
    for kind, home, linkable in finish.OBJECT_TYPES:
        required = ["type", "name", "aliases", "private"] if linkable else ["type", "date", "private"]
        sections = (["Currently"] if kind in finish.WITH_CURRENTLY else []) + ["History"]
        found[kind] = {
            "home": home,
            "linkable": linkable,
            "name-from": "first-heading" if linkable else None,
            "required-keys": required,
            "sections": sections,
            "summary-max-words": 60,
        }
    return found


def good_sources():
    return {
        kind: {
            "kind": kind,
            "home": home,
            "required-keys": list(finish.SOURCE_KEYS) if home else [],
        }
        for kind, home in finish.SOURCE_KINDS
    }


def changed(document, name, **changes):
    document = copy.deepcopy(document)
    document[name].update(changes)
    return document


GOOD_HELP = "usage: wd <command> [arguments]\n\ncommands:\n" + "".join(
    "  %s  What it does.\n" % name.ljust(14) for name in finish.COMMANDS
)

SKILL = "---\nname: %s\ndescription: %s\n---\n# %s\n\nWhat to do.\n"

GOOD_GRAPH = {
    "search": "-path:sources -path:signals/briefs -file:AGENTS.md -file:CLAUDE.md -file:status.md",
    "colorGroups": [
        {"query": "path:%s" % home, "color": {"a": 1, "rgb": 1000 + number}}
        for number, (_, home, _) in enumerate(finish.OBJECT_TYPES)
    ],
}
GOOD_APP = {"alwaysUpdateLinks": True}

RECORDING = (
    "---\ntype: source\nkind: meeting-recording\nsample: true\n---\n"
    "Robin Hale: Who runs the floor? ^p0001\n\n"
    "Sam Rivera: I do. ^p0002\n"
)


def sample(kind, title, text):
    return "---\ntype: %s\nsample: true\n---\n# %s\n\n%s\n" % (kind, title, text)


# One made-up sample in each object home, each linked from another.
SAMPLES = {
    "objects/people/sam-rivera.md": sample(
        "person", "Sam Rivera", "Leads operations at [[objects/companies/acme|Acme]]."),
    "objects/companies/acme.md": sample(
        "company", "Acme", "Runs the [[objects/projects/acme-rollout|Acme Rollout]]."),
    "objects/projects/acme-rollout.md": sample(
        "project", "Acme Rollout", "Led by [[objects/people/sam-rivera|Sam Rivera]]. "
        "Avoids [[objects/terms/bespoke-systems|bespoke systems]]."),
    "objects/terms/bespoke-systems.md": sample(
        "term", "bespoke systems", "See [[objects/concepts/two-way-door|Two-Way Door]]."),
    "objects/concepts/two-way-door.md": sample(
        "concept", "Two-Way Door", "Kept in [[objects/quotes/sam-rivera-on-doors]]."),
    "objects/meetings/2026-11-12-acme-intro.md": sample(
        "meeting", "Acme intro", "Decided [[objects/decisions/2026-11-12-start-date]]. "
        "[[sources/recordings/2026-11-12-acme-intro#^p0002]]"),
    "objects/decisions/2026-11-12-start-date.md": sample(
        "decision", "Start date", "From [[objects/meetings/2026-11-12-acme-intro]]."),
    "objects/quotes/sam-rivera-on-doors.md": sample(
        "quote", "On doors", "Said in [[objects/meetings/2026-11-12-acme-intro]]."),
    "sources/recordings/2026-11-12-acme-intro.md": RECORDING,
}


def make_vault(root, samples=False):
    """A vault as `wd init` should leave it."""
    root = Path(root)
    for folder in finish.FOLDERS:
        (root / folder).mkdir(parents=True)
    (root / "AGENTS.md").write_text("# The rulebook\n\nWrite full names.\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("@AGENTS.md\n", encoding="utf-8")
    (root / "status.md").write_text("# Status\n\nWritten by a program.\n", encoding="utf-8")
    for place in finish.SKILL_FOLDERS:
        for name in finish.SKILLS:
            (root / place / name).mkdir(parents=True)
            (root / place / name / "SKILL.md").write_text(
                SKILL % (name, "Use it.", name), encoding="utf-8")
    (root / ".obsidian").mkdir()
    (root / ".obsidian" / "graph.json").write_text(json.dumps(GOOD_GRAPH), encoding="utf-8")
    (root / ".obsidian" / "app.json").write_text(json.dumps(GOOD_APP), encoding="utf-8")
    if samples:
        for name, text in SAMPLES.items():
            (root / name).write_text(text, encoding="utf-8")
    return root


class Counting(unittest.TestCase):
    def test_words_are_counted_as_the_budget_test_counts_them(self):
        self.assertEqual(len(finish.words(test_budget.SAMPLE)), len(test_budget.words(test_budget.SAMPLE)))
        self.assertEqual(finish.words("---\nkey: not counted\n---\n| a | b |\n- one"), ["a", "b", "one"])

    def test_the_session_limit_is_the_budget_files(self):
        limits = json.loads((CORE / "budgets.json").read_text(encoding="utf-8"))
        self.assertEqual(
            finish.SESSION_LOAD_LIMIT, limits["Words loaded into a session, everything counted"])
        self.assertEqual(len(finish.OBJECT_TYPES), limits["Object types"])
        self.assertEqual(len(finish.SOURCE_KINDS), limits["Source kinds"])
        self.assertEqual(len(finish.SKILLS), limits["Skills"])

    def test_the_opening_block(self):
        keys = finish.front("---\nname: track\ndescription: >\n  Track a\n  phrase.\n---\nBody\n")
        self.assertEqual(finish.unquoted(keys["description"]), "Track a phrase.")
        self.assertEqual(finish.unquoted('"Find it."'), "Find it.")
        self.assertEqual(finish.front("No block\n"), {})
        self.assertEqual(finish.front("---\nnever: closed\n"), {})


class Declarations(unittest.TestCase):
    def test_a_full_set_gets_through(self):
        self.assertEqual(finish.declaration_problems(good_objects(), good_sources()), [])

    def test_name_from_may_be_left_out_where_nothing_is_linked_by_name(self):
        objects = good_objects()
        del objects["meeting"]["name-from"]
        self.assertEqual(finish.declaration_problems(objects, good_sources()), [])
        del objects["person"]["name-from"]
        self.assertEqual(len(finish.declaration_problems(objects, good_sources())), 2)

    def test_nothing_on_disk_does_not_get_through(self):
        self.assertEqual(len(finish.declaration_problems({}, {})), 17)
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(finish.read_declarations(folder), ({}, {}))

    def test_a_missing_or_broken_declaration_is_named(self):
        objects = good_objects()
        del objects["quote"]
        objects["term"] = None
        self.assertEqual(
            finish.declaration_problems(objects, good_sources()),
            ["objects/term: no declaration", "objects/quote: no declaration"],
        )

    def test_an_old_home_does_not_get_through(self):
        objects = changed(good_objects(), "person", home="atlas/people")
        self.assertEqual(
            finish.declaration_problems(objects, good_sources()),
            ["objects/person: home is 'atlas/people', not objects/people"],
        )
        sources = changed(good_sources(), "article", home="system/bookmarks")
        self.assertEqual(len(finish.declaration_problems(good_objects(), sources)), 1)
        # A slash at the end is the same folder.
        objects = changed(good_objects(), "person", home="objects/people/")
        self.assertEqual(finish.declaration_problems(objects, good_sources()), [])

    def test_the_six_keys_exactly(self):
        objects = changed(good_objects(), "company", color="blue")
        self.assertEqual(len(finish.declaration_problems(objects, good_sources())), 1)
        objects = good_objects()
        del objects["company"]["sections"]
        self.assertEqual(len(finish.declaration_problems(objects, good_sources())), 2)

    def test_what_is_linked_by_name(self):
        objects = changed(good_objects(), "meeting", linkable=True)
        self.assertTrue(finish.declaration_problems(objects, good_sources()))
        objects = changed(good_objects(), "meeting",
                          **{"required-keys": ["type", "name", "aliases", "private"]})
        self.assertEqual(len(finish.declaration_problems(objects, good_sources())), 2)
        objects = changed(good_objects(), "term", **{"required-keys": ["type", "private"]})
        self.assertEqual(len(finish.declaration_problems(objects, good_sources())), 2)
        objects = changed(good_objects(), "term", **{"name-from": "file-name"})
        self.assertEqual(len(finish.declaration_problems(objects, good_sources())), 1)

    def test_currently_and_the_summary_limit(self):
        objects = changed(good_objects(), "term", sections=["Currently", "History"])
        self.assertEqual(len(finish.declaration_problems(objects, good_sources())), 1)
        objects = changed(good_objects(), "person", sections=["History"])
        self.assertEqual(len(finish.declaration_problems(objects, good_sources())), 1)
        for limit in (61, True, "60", None):
            objects = changed(good_objects(), "person", **{"summary-max-words": limit})
            self.assertEqual(len(finish.declaration_problems(objects, good_sources())), 1, limit)

    def test_a_ninth_type_and_a_tenth_kind_do_not_get_through(self):
        objects = good_objects()
        objects["task"] = dict(objects["term"])
        sources = good_sources()
        sources["email"] = dict(sources["article"])
        self.assertEqual(
            finish.declaration_problems(objects, sources),
            ["objects/task: not one of the eight object types",
             "sources/email: not one of the nine source kinds"],
        )

    def test_a_source_kind(self):
        sources = changed(good_sources(), "calendar", home="sources/calendar")
        self.assertEqual(len(finish.declaration_problems(good_objects(), sources)), 1)
        sources = good_sources()
        del sources["calendar"]["home"]
        self.assertEqual(len(finish.declaration_problems(good_objects(), sources)), 1)
        sources = changed(good_sources(), "video", kind="clip")
        self.assertEqual(len(finish.declaration_problems(good_objects(), sources)), 1)
        sources = changed(good_sources(), "video", **{"required-keys": ["type", "kind"]})
        self.assertEqual(len(finish.declaration_problems(good_objects(), sources)), 10)

    def test_declarations_are_read_from_disk(self):
        with tempfile.TemporaryDirectory() as folder:
            for part, found in (("objects", good_objects()), ("sources", good_sources())):
                (Path(folder) / part).mkdir()
                for name, declaration in found.items():
                    (Path(folder) / part / (name + ".json")).write_text(
                        json.dumps(declaration), encoding="utf-8")
            (Path(folder) / "objects" / "term.json").write_text("{not json", encoding="utf-8")
            objects, sources = finish.read_declarations(folder)
        self.assertEqual(
            finish.declaration_problems(objects, sources), ["objects/term: no declaration"])


class Layout(unittest.TestCase):
    GOOD = [
        "AGENTS.md", "CLAUDE.md", "status.md", ".obsidian/app.json",
        ".claude/skills/track/SKILL.md", "writing/2026-11-12.md",
        "sources/recordings/2026-11-12-acme.md", "signals/briefs/2026-11-12.md",
    ] + ["%s/one.md" % home for _, home, _ in finish.OBJECT_TYPES]

    def test_the_new_layout_gets_through(self):
        self.assertEqual(finish.layout_problems(self.GOOD), [])
        self.assertEqual(finish.home_problems(self.GOOD), [])
        folders = ["objects", "objects/people", "sources", "sources/links", "writing",
                   ".obsidian", ".obsidian/plugins", ".claude", ".claude/skills",
                   ".claude/skills/track", ".agents", ".agents/skills"]
        self.assertEqual(finish.layout_problems(self.GOOD, folders), [])

    def test_the_old_layout_does_not_get_through(self):
        old = ["atlas/people/sam-rivera.md", "gtd/projects/acme-rollout/brief.md",
               "system/transcripts/2026-11-03-acme-intro.md", "intel/concepts/two-way-door.md"]
        self.assertEqual(len(finish.layout_problems(old)), 4)
        self.assertEqual(len(finish.home_problems(old)), 9)

    def test_a_stray_file_or_folder_is_named(self):
        self.assertEqual(
            finish.layout_problems(self.GOOD + ["notes.md", "objects/loose.md", "tasks/one.md"]),
            ["notes.md: not one of the root files",
             "objects/loose.md: not in a folder of the new layout",
             "tasks/one.md: not in a folder of the new layout"],
        )
        self.assertEqual(
            finish.layout_problems([], ["tasks", "objects/tasks", "objects/people/old",
                                        ".claude/rules", "state"]),
            [".claude/rules/: not a folder of the new layout",
             "objects/people/old/: not a folder of the new layout",
             "objects/tasks/: not a folder of the new layout",
             "state/: not a folder of the new layout",
             "tasks/: not a folder of the new layout"],
        )

    def test_an_empty_home_is_named(self):
        files = [name for name in self.GOOD if not name.startswith("objects/quotes/")]
        self.assertEqual(finish.home_problems(files), ["objects/quotes: no notes"])

    def test_a_path_from_the_old_layout_is_found(self):
        self.assertEqual(
            finish.old_path_problems("a.md", "See [[atlas/people/sam-rivera|Sam Rivera]] and "
                                             "system/transcripts/x.md, twice: atlas/people/x."),
            ["a.md: still names atlas/", "a.md: still names system/"],
        )
        self.assertEqual(finish.old_path_problems("a.md", "A system. An atlas/ of maps."), [])
        self.assertEqual(finish.old_path_problems("a.md", "[[objects/people/sam-rivera]]"), [])
        self.assertEqual(finish.old_path_problems("a.md", "solar-system/planets"), [])


class Commands(unittest.TestCase):
    def test_the_build_specs_list_gets_through(self):
        self.assertEqual(finish.listed_commands(GOOD_HELP), finish.COMMANDS)
        self.assertEqual(finish.command_problems(GOOD_HELP), [])

    def test_a_dropped_command_that_is_still_listed_does_not_get_through(self):
        text = GOOD_HELP + "  names           Give every object its name.\n"
        self.assertEqual(
            finish.command_problems(text), ["names: listed, and not in the build spec"])

    def test_a_missing_command_is_named(self):
        text = GOOD_HELP.replace("  init ", "  begin")
        self.assertEqual(
            finish.command_problems(text),
            ["init: not listed", "begin: listed, and not in the build spec"],
        )

    def test_no_list_at_all_does_not_get_through(self):
        self.assertEqual(len(finish.command_problems("usage: wd")), len(finish.COMMANDS))
        # A command named in a sentence is not a listed command.
        self.assertEqual(finish.listed_commands("Run init first.\n  init  here\n"), [])


class Rulebook(unittest.TestCase):
    def test_the_limit(self):
        self.assertEqual(finish.rulebook_problems("word " * 1200), [])
        self.assertEqual(len(finish.rulebook_problems("word " * 1201)), 1)
        self.assertEqual(len(finish.rulebook_problems("---\ntitle: nothing else\n---\n")), 1)

    def test_claude_md_is_one_line_that_imports_the_rulebook(self):
        self.assertEqual(finish.import_problems("@AGENTS.md\n"), [])
        self.assertEqual(len(finish.import_problems("")), 1)
        self.assertEqual(len(finish.import_problems("See AGENTS.md\n")), 1)
        self.assertEqual(len(finish.import_problems("@AGENTS.md\n\nAnd more rules here.\n")), 1)

    def test_four_skills_get_through(self):
        skills = {name: SKILL % (name, "Use it when asked.", name) for name in finish.SKILLS}
        self.assertEqual(finish.skill_problems(skills), [])

    def test_a_long_or_missing_description_does_not_get_through(self):
        skills = {name: SKILL % (name, "Use it when asked.", name) for name in finish.SKILLS}
        skills["track"] = SKILL % ("track", "word " * 41, "track")
        skills["status"] = "# Status\n\nNo opening block.\n"
        skills["correct"] = None
        self.assertEqual(
            finish.skill_problems(skills),
            ["correct: no SKILL.md",
             "track: its description has 41 words. The limit is 40.",
             "status: no description"],
        )
        skills["track"] = SKILL % ("track", "\"%s\"" % ("word " * 40).strip(), "track")
        self.assertNotIn("track", " ".join(finish.skill_problems(skills)))

    def test_a_fifth_skill_does_not_get_through(self):
        skills = {name: SKILL % (name, "Use it.", name) for name in finish.SKILLS + ["tasks"]}
        self.assertEqual(finish.skill_problems(skills), ["tasks: not one of the four skills"])


class Graph(unittest.TestCase):
    def test_a_full_setting_gets_through(self):
        self.assertEqual(finish.graph_problems(GOOD_GRAPH, GOOD_APP), [])
        quoted = dict(GOOD_GRAPH, search='-path:"sources/" -path:"signals/briefs/" '
                                         '-file:"AGENTS" -file:CLAUDE -path:status.md')
        self.assertEqual(finish.graph_problems(quoted, GOOD_APP), [])

    def test_nothing_does_not_get_through(self):
        self.assertEqual(len(finish.graph_problems(None, None)), 2)
        self.assertEqual(len(finish.graph_problems({}, {})), 15)

    def test_link_updating_must_be_on(self):
        for app in ({}, {"alwaysUpdateLinks": False}, {"alwaysUpdateLinks": "true"}):
            self.assertEqual(len(finish.graph_problems(GOOD_GRAPH, app)), 1, app)

    def test_one_color_group_for_each_object_type(self):
        graph = copy.deepcopy(GOOD_GRAPH)
        graph["colorGroups"].pop()
        self.assertEqual(len(finish.graph_problems(graph, GOOD_APP)), 2)
        graph = copy.deepcopy(GOOD_GRAPH)
        graph["colorGroups"][0]["query"] = "path:objects"
        self.assertEqual(
            finish.graph_problems(graph, GOOD_APP), ["graph.json: 0 color groups for objects/people"])
        graph = copy.deepcopy(GOOD_GRAPH)
        graph["colorGroups"][1]["color"] = graph["colorGroups"][0]["color"]
        self.assertEqual(
            finish.graph_problems(graph, GOOD_APP), ["graph.json: two object types share a color"])
        graph = copy.deepcopy(GOOD_GRAPH)
        del graph["colorGroups"][2]["color"]
        self.assertEqual(len(finish.graph_problems(graph, GOOD_APP)), 1)

    def test_what_must_be_hidden(self):
        graph = dict(GOOD_GRAPH, search="-path:sources/recordings -file:AGENTS.md -file:CLAUDE.md")
        self.assertEqual(
            finish.graph_problems(graph, GOOD_APP),
            ["graph.json: sources/ is not hidden", "graph.json: signals/briefs/ is not hidden",
             "graph.json: status.md is not hidden"],
        )
        # Naming a folder is not hiding it.
        graph = dict(GOOD_GRAPH, search=GOOD_GRAPH["search"].replace("-path:sources", "path:sources"))
        self.assertEqual(finish.graph_problems(graph, GOOD_APP), ["graph.json: sources/ is not hidden"])
        # A group that hides a home does not color it.
        self.assertFalse(finish.names_path("-path:objects/people", "objects/people"))


class Init(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name) / "vault"

    def test_an_empty_vault_gets_through(self):
        make_vault(self.root)
        self.assertEqual(finish.init_problems(self.root), [])

    def test_init_makes_all_three_root_files(self):
        # The status page is one of them. A vault without it does not get through.
        self.assertEqual(finish.FILES_FROM_INIT, finish.ROOT_FILES)
        make_vault(self.root)
        (self.root / "status.md").unlink()
        self.assertEqual(finish.init_problems(self.root), ["status.md: missing"])

    def test_a_vault_with_samples_gets_through(self):
        make_vault(self.root, samples=True)
        self.assertEqual(finish.init_problems(self.root, samples=True), [])
        self.assertEqual(finish.one_sample_in_each_home(self.root), [])

    def test_no_vault_and_an_empty_folder_do_not_get_through(self):
        self.assertEqual(len(finish.init_problems(self.root)), 1)
        self.root.mkdir()
        # 15 folders, 3 root files, 8 skill pages and 2 settings.
        self.assertEqual(len(finish.init_problems(self.root)), 28)

    def test_a_missing_folder_file_or_skill_is_named(self):
        make_vault(self.root)
        (self.root / "writing").rmdir()
        (self.root / "CLAUDE.md").unlink()
        (self.root / ".agents" / "skills" / "track" / "SKILL.md").unlink()
        self.assertEqual(
            finish.init_problems(self.root),
            ["writing/: missing", "CLAUDE.md: missing", ".agents/skills/track/SKILL.md: missing"],
        )

    def test_a_folder_outside_the_layout_is_named(self):
        make_vault(self.root)
        (self.root / "tasks").mkdir()
        (self.root / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
        self.assertEqual(
            finish.init_problems(self.root),
            [".claude/settings.json: not in a folder of the new layout",
             "tasks/: not a folder of the new layout"],
        )

    def test_nothing_is_written_under_writing(self):
        make_vault(self.root)
        (self.root / "writing" / "welcome.md").write_text("Hello.\n", encoding="utf-8")
        problems = finish.init_problems(self.root)
        self.assertIn("writing/welcome.md: a program wrote under writing/", problems)

    def test_the_settings_are_checked(self):
        make_vault(self.root)
        (self.root / ".obsidian" / "app.json").write_text("{}", encoding="utf-8")
        (self.root / ".obsidian" / "graph.json").unlink()
        self.assertEqual(len(finish.init_problems(self.root)), 2)

    def test_a_rulebook_that_says_nothing_and_a_bad_import(self):
        make_vault(self.root)
        (self.root / "AGENTS.md").write_text("\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("Read AGENTS.md.\n", encoding="utf-8")
        self.assertEqual(len(finish.init_problems(self.root)), 2)

    def test_samples_without_being_asked_for(self):
        make_vault(self.root, samples=True)
        self.assertEqual(len(finish.init_problems(self.root, samples=False)), 9)

    def test_no_samples_when_they_were_asked_for(self):
        make_vault(self.root)
        self.assertEqual(len(finish.init_problems(self.root, samples=True)), 9)
        self.assertEqual(len(finish.one_sample_in_each_home(self.root)), 8)

    def test_two_samples_in_one_home(self):
        make_vault(self.root, samples=True)
        (self.root / "objects/people/dana-whitfield.md").write_text(
            sample("person", "Dana Whitfield", "Runs finance."), encoding="utf-8")
        problems = finish.init_problems(self.root, samples=True)
        self.assertIn("objects/people: 2 notes. There is one sample.", problems)
        self.assertIn("objects/people/dana-whitfield.md: no other note links to it", problems)
        self.assertEqual(
            finish.one_sample_in_each_home(self.root), ["objects/people: 2 samples. There is one."])

    def test_a_sample_must_say_it_is_one(self):
        make_vault(self.root, samples=True)
        path = self.root / "objects/terms/bespoke-systems.md"
        path.write_text(path.read_text(encoding="utf-8").replace("sample: true\n", ""), encoding="utf-8")
        self.assertEqual(
            finish.init_problems(self.root, samples=True),
            ["objects/terms/bespoke-systems.md: does not carry sample: true"],
        )
        self.assertEqual(
            finish.one_sample_in_each_home(self.root), ["objects/terms: 0 samples. There is one."])

    def test_the_sample_recording_needs_its_markers(self):
        make_vault(self.root, samples=True)
        path = self.root / "sources/recordings/2026-11-12-acme-intro.md"
        path.write_text(RECORDING.replace(" ^p0002", ""), encoding="utf-8")
        self.assertEqual(
            finish.init_problems(self.root, samples=True),
            ["sources/recordings/2026-11-12-acme-intro.md: block 2 does not end with ^p0002"],
        )
        self.assertEqual(finish.marker_problems("---\ntype: source\n---\n"), ["has no passages"])
        self.assertEqual(len(finish.marker_problems("One. ^p0002\n\nTwo. ^p0001\n")), 2)

    def test_a_sample_link_that_goes_nowhere_and_a_sample_nothing_links_to(self):
        make_vault(self.root, samples=True)
        path = self.root / "objects/concepts/two-way-door.md"
        path.write_text(sample("concept", "Two-Way Door", "See [[objects/quotes/gone]]."),
                        encoding="utf-8")
        self.assertEqual(
            finish.init_problems(self.root, samples=True),
            ["objects/concepts/two-way-door.md: its link to objects/quotes/gone goes nowhere",
             "objects/quotes/sam-rivera-on-doors.md: no other note links to it"],
        )

    def test_a_note_that_is_not_a_sample(self):
        make_vault(self.root, samples=True)
        (self.root / "signals/briefs/2026-11-12.md").write_text(
            "---\nsample: true\n---\nA brief.\n", encoding="utf-8")
        self.assertEqual(
            finish.init_problems(self.root, samples=True),
            ["signals/briefs/2026-11-12.md: not one of the nine samples"],
        )

    def test_a_link_to_its_own_note_is_not_a_connection(self):
        notes = {"objects/people/sam-rivera.md": "About [[objects/people/sam-rivera|Sam Rivera]]."}
        self.assertEqual(
            finish.link_problems(notes), ["objects/people/sam-rivera.md: no other note links to it"])


class CheckAndStatus(unittest.TestCase):
    NOTES = {"objects/people": 1, "objects/companies": 1, "sources/recordings": 1, "writing": 0}
    LOAD = {"claude-code": {"vault": 512, "outside": 4375}, "codex": {"vault": 498, "outside": 1692}}
    PAGE = """# Status

Written by a program on 2026-11-15.

| Home | Notes |
|---|---|
| objects/people | 1 |
| objects/companies | 1 |
| sources/recordings | 1 |
| writing | 0 |

The check found 0 problems.

| Runtime | From the vault | From outside it | All |
|---|---|---|---|
| Claude Code | 512 | 4,375 | 4,887 |
| Codex | 498 | 1,692 | 2,190 |
"""

    def test_a_check_report(self):
        self.assertEqual(finish.check_report_problems({"problems": []}), [])
        entry = {"note": "objects/people/a.md", "kind": "link-goes-nowhere", "sentence": "It is."}
        self.assertEqual(finish.check_report_problems({"problems": [entry]}), [])
        self.assertEqual(len(finish.check_report_problems({})), 1)
        self.assertEqual(len(finish.check_report_problems({"problems": 0})), 1)
        self.assertEqual(len(finish.check_report_problems({"problems": ["", {}, 3]})), 3)
        self.assertEqual(len(finish.check_report_problems([])), 1)
        # An entry names its note and its kind. A line of words alone does not get through.
        self.assertEqual(
            len(finish.check_report_problems({"problems": [
                "a.md: a link goes nowhere", {"note": "a.md"}, {"kind": "unlinked"},
                {"note": "a.md", "kind": " "}, {"note": 3, "kind": "unlinked"},
            ]})), 5)

    FAULTS = finish.faulty_notes(
        "objects/people/sam-rivera", "Sam Rivera", "sources/recordings/2026-11-12-acme-intro")

    def found(self, leave_out=(), add=()):
        """A report that finds every fault, but for the ones left out."""
        entries = [
            {"note": path, "kind": kind} for path, _, kind in self.FAULTS
            if kind is not None and path not in leave_out
        ]
        return {"problems": entries + [{"note": note, "kind": kind} for note, kind in add]}

    def test_each_requirement_has_its_own_wrong_note(self):
        kinds = [kind for _, _, kind in self.FAULTS]
        for kind in ("missing-key", "summary-too-long", "link-goes-nowhere",
                     "first-name-link", "unlinked", "name-not-unique"):
            self.assertIn(kind, kinds)
        # Two for the summary (lines, words) and two for links (a note, a passage).
        self.assertEqual(kinds.count("summary-too-long"), 2)
        self.assertEqual(kinds.count("link-goes-nowhere"), 2)
        self.assertEqual(kinds.count(None), 1)
        paths = [path for path, _, _ in self.FAULTS]
        self.assertEqual(len(set(paths)), len(paths))
        for path, text, _ in self.FAULTS:
            self.assertTrue(path.startswith("objects/people/") and path.endswith(".md"), path)
            self.assertTrue(text.startswith("---\ntype: person\n"), path)
        texts = {path.rsplit("/", 1)[-1]: text for path, text, _ in self.FAULTS}
        self.assertNotIn("private:", texts["ada-quill.md"])
        self.assertEqual(len(texts["ben-osei.md"].split("\n\n")[1].strip().split("\n")), 4)
        self.assertEqual(len(finish.words(texts["cy-ward.md"].split("\n\n")[1])), 61)
        self.assertIn("#^p9999]]", texts["eli-stone.md"])
        self.assertIn("|Sam]]", texts["fay-lund.md"])
        self.assertNotIn("[[objects/", texts["gus-pine.md"])
        self.assertIn("name: Sam Rivera\n", texts["the-other-one.md"])

    def test_a_check_that_finds_every_fault_gets_through(self):
        self.assertEqual(finish.fault_problems(self.found(), self.FAULTS), [])

    def test_one_reported_problem_is_not_enough(self):
        # The old test passed on any one problem. Each fault now needs its own kind.
        one = {"problems": [{"note": "objects/people/ada-quill.md", "kind": "missing-key"}]}
        self.assertEqual(len(finish.fault_problems(one, self.FAULTS)), 7)
        self.assertEqual(len(finish.fault_problems({"problems": []}, self.FAULTS)), 8)
        self.assertEqual(len(finish.fault_problems(None, self.FAULTS)), 8)

    def test_a_missed_fault_is_named(self):
        self.assertEqual(
            finish.fault_problems(self.found(leave_out=["objects/people/eli-stone.md"]), self.FAULTS),
            ["objects/people/eli-stone.md: no link-goes-nowhere problem was reported"],
        )

    def test_the_wrong_kind_on_the_right_note_is_not_enough(self):
        report = self.found(
            leave_out=["objects/people/fay-lund.md"],
            add=[("objects/people/fay-lund.md", "unlinked")],
        )
        self.assertEqual(
            finish.fault_problems(report, self.FAULTS),
            ["objects/people/fay-lund.md: no first-name-link problem was reported"],
        )

    def test_a_right_note_must_not_be_given_a_problem(self):
        report = self.found(add=[("objects/people/hal-reed.md", "unlinked")])
        self.assertEqual(
            finish.fault_problems(report, self.FAULTS),
            ["objects/people/hal-reed.md: nothing is wrong with it, and the check reported unlinked"],
        )

    def test_a_name_used_twice_may_be_reported_on_either_note(self):
        report = self.found(
            leave_out=["objects/people/the-other-one.md"],
            add=[("objects/people/sam-rivera.md", "name-not-unique")],
        )
        self.assertEqual(finish.fault_problems(report, self.FAULTS), [])
        report = self.found(leave_out=["objects/people/the-other-one.md"])
        self.assertEqual(
            finish.fault_problems(report, self.FAULTS),
            ["objects/people/the-other-one.md: no name-not-unique problem was reported"],
        )

    def test_the_graph_setting_keeps_keys_that_are_not_its_own(self):
        self.assertTrue(finish.graph_problems(finish.WRONG_GRAPH, finish.WRONG_APP))
        graph = dict(GOOD_GRAPH, scale=1.5)
        app = dict(GOOD_APP, showLineNumber=True)
        self.assertEqual(finish.kept_key_problems("graph.json", finish.WRONG_GRAPH, graph), [])
        self.assertEqual(finish.kept_key_problems("app.json", finish.WRONG_APP, app), [])
        self.assertEqual(
            finish.kept_key_problems("graph.json", finish.WRONG_GRAPH, GOOD_GRAPH),
            ["graph.json: scale was 1.5 and is now \"not there\""],
        )
        self.assertEqual(
            finish.kept_key_problems("app.json", finish.WRONG_APP, dict(app, showLineNumber=False)),
            ["app.json: showLineNumber was true and is now false"],
        )
        self.assertEqual(len(finish.kept_key_problems("app.json", finish.WRONG_APP, None)), 1)

    def test_a_full_status_page_gets_through(self):
        self.assertEqual(finish.status_problems(self.PAGE, self.NOTES, 0, self.LOAD), [])

    def test_a_placeholder_does_not_get_through(self):
        self.assertEqual(len(finish.status_problems("# Status\n\nTODO\n", self.NOTES, 0, self.LOAD)), 11)

    def test_a_missing_number_is_named(self):
        page = self.PAGE.replace("| objects/companies | 1 |", "| objects/companies | some |")
        self.assertEqual(
            finish.status_problems(page, self.NOTES, 0, self.LOAD), ["notes in objects/companies (1)"])
        page = self.PAGE.replace("4,375", "about four thousand")
        self.assertEqual(
            finish.status_problems(page, self.NOTES, 0, self.LOAD),
            ["session load, Claude Code, from outside it (4375)"],
        )
        self.assertEqual(
            finish.status_problems(self.PAGE, self.NOTES, 3, self.LOAD), ["the check's result (3)"])

    def test_the_split_must_be_named(self):
        page = self.PAGE.replace("From the vault", "Vault").replace("From outside it", "Elsewhere")
        self.assertEqual(
            finish.status_problems(page, self.NOTES, 0, self.LOAD),
            ["the words \"from the vault\"", "the words \"from outside it\""],
        )

    def test_a_home_inside_a_longer_path_does_not_count(self):
        self.assertTrue(finish.mentions("| objects/people | 1 |", "objects/people"))
        self.assertFalse(finish.mentions("| old/objects/people | 1 |", "objects/people"))
        self.assertFalse(finish.mentions("| objects/people-old | 1 |", "objects/people"))

    def test_the_session_load_limit(self):
        self.assertEqual(finish.load_problems({"claude-code": 3000, "codex": 0}), [])
        self.assertEqual(
            finish.load_problems({"claude-code": 4375, "codex": 1692}),
            ["Claude Code: a session loads 4375 words. The limit is 3000."],
        )
        self.assertEqual(len(finish.load_problems({"claude-code": 10})), 1)
        self.assertEqual(len(finish.load_problems({"claude-code": True, "codex": -1})), 2)
        self.assertEqual(len(finish.load_problems(None)), 2)


class MovedChecks(unittest.TestCase):
    GOOD = """
- S0.5 (a): verified. Evidence: the link opened its exact passage.
- S0.5 (b) Codex: verified. Evidence: ran it unattended three times.
- S0.5 (e): worked around. Evidence: both devices kept their own copy. Consequence: one machine writes by program at a time.
"""

    def test_both_lines_get_through(self):
        self.assertEqual(finish.moved_check_problems(self.GOOD), [])

    def test_the_stage_0_record_alone_does_not_get_through(self):
        log = "- S0.5 (b) Codex: verified. Evidence: ran it unattended three times.\n"
        self.assertEqual(
            finish.moved_check_problems(log),
            ["S0.5 (a): no outcome logged", "S0.5 (e): no outcome logged"],
        )

    def test_a_mention_in_a_sentence_is_not_a_record(self):
        prose = "Next is S0.5 (a): verified. Evidence: one two three.\n" + self.GOOD.replace(
            "- S0.5 (a): verified. Evidence: the link opened its exact passage.\n", "")
        self.assertEqual(finish.moved_check_problems(prose), ["S0.5 (a): no outcome logged"])

    def test_an_outcome_needs_evidence_and_a_failure_its_consequence(self):
        log = self.GOOD.replace("Evidence: the link opened its exact passage.", "Evidence: yes.")
        self.assertEqual(finish.moved_check_problems(log), ["S0.5 (a): no evidence given"])
        log = self.GOOD.replace(" Consequence: one machine writes by program at a time.", "")
        self.assertEqual(
            finish.moved_check_problems(log), ["S0.5 (e): worked around, with no consequence given"])

    def test_a_check_run_again_counts_by_its_last_line(self):
        log = self.GOOD + "- S0.5 (a): failed. Evidence: the link opened the top of the note.\n"
        self.assertEqual(
            finish.moved_check_problems(log), ["S0.5 (a): failed, with no consequence given"])


class TheNewVault(unittest.TestCase):
    def test_where_it_is_looked_for(self):
        with mock.patch.dict(os.environ, {"WD_NEW_VAULT": "/made-up/Workdesk"}):
            self.assertEqual(finish.new_vault(), Path("/made-up/Workdesk"))
        with mock.patch.dict(os.environ, {"WD_NEW_VAULT": " ", "HOME": "/made-up/home"}):
            self.assertEqual(finish.new_vault(), Path("/made-up/home/Workdesk"))


if __name__ == "__main__":
    unittest.main()
