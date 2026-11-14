"""The made-up test vault and the twelve cases are what they claim to be."""

import json
import re
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
CORE = TESTS.parent
FIXTURES = TESTS / "fixtures"
VAULT = FIXTURES / "vault"
HOME = FIXTURES / "home"
for folder in (CORE, TESTS):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import stage0_finish as finish  # noqa: E402
from wd import measure, notes, places  # noqa: E402

TYPE_HOMES = dict(places.OBJECT_HOMES)
BASES = ("stated", "reported", "inferred", "correction")
HISTORY = re.compile(
    r"^- \d{4}-\d\d-\d\d \| [^|]+ \| (%s) \| [^|]+ \| run-\d{8}-\d{4}$" % "|".join(BASES)
)
# The links that are left dead on purpose. See fixtures/README.md.
DEAD_ON_PURPOSE = {
    "system/transcripts/2026-11-09-bluepeak-sync",
    "intel/concepts/handoff-tax",
}


def project_name(heading):
    """Build spec, "Names": the heading without a trailing Brief and its dash or colon."""
    return re.sub(r"\s*[-:]?\s*Brief$", "", heading).strip()


def in_right_home(path, kind):
    if kind == "project":
        return places.is_project_brief(path)
    return kind in TYPE_HOMES and places.in_home(path, TYPE_HOMES[kind])


class TheVault(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vault = notes.Vault(VAULT)

    def linkable(self):
        found = []
        for kind in ("person", "company", "term", "concept"):
            found += [n for n in self.vault.notes if places.in_home(n, TYPE_HOMES[kind])]
        return found + [n for n in self.vault.notes if places.is_project_brief(n)]

    def test_about_forty_notes(self):
        self.assertEqual(finish.note_count(VAULT), 44)

    def test_the_measure_answers_are_what_the_command_counts(self):
        answers = json.loads((FIXTURES / "answers.json").read_text(encoding="utf-8"))["measure"]
        self.assertEqual(finish.measure_problems(answers), [])
        report = measure.measure(VAULT, HOME)
        self.assertEqual({name: report[name] for name in finish.MEASURES}, answers)

    def test_only_the_links_left_dead_on_purpose_are_dead(self):
        dead = set()
        for name in self.vault.notes:
            for target in notes.link_targets(self.vault.text(name)):
                if self.vault.resolve(target, name) is None:
                    dead.add(target)
        self.assertEqual(dead, DEAD_ON_PURPOSE)

    def test_each_name_is_the_first_heading_and_no_two_are_the_same(self):
        names = {}
        for note in self.linkable():
            keys, body = notes.front(self.vault.text(note))
            if "name" not in keys:
                continue
            heading = notes.first_heading(body)
            wanted = project_name(heading) if places.is_project_brief(note) else heading
            self.assertEqual(keys["name"], wanted, note)
            self.assertIn(keys.get("private"), ("true", "false"), note)
            self.assertTrue(keys.get("aliases", "").startswith("["), note)
            names.setdefault(keys["name"], []).append(note)
        self.assertEqual({name: where for name, where in names.items() if len(where) > 1}, {})
        self.assertEqual(len(names), 20)

    def test_every_history_line_has_its_five_fields(self):
        lines = 0
        for name in self.vault.notes:
            inside = False
            for line in self.vault.text(name).split("\n"):
                if line.startswith("## "):
                    inside = line.strip() == "## History"
                elif inside and line.strip():
                    self.assertRegex(line, HISTORY, name)
                    lines += 1
        self.assertGreater(lines, 15)

    def test_every_turn_in_a_new_source_has_its_marker_in_order(self):
        marked = 0
        for name in self.vault.notes:
            keys, body = notes.front(self.vault.text(name))
            if keys.get("type") != "source" or "kind" not in keys:
                continue
            self.assertRegex(keys.get("sha256-original", ""), r"^[0-9a-f]{64}$", name)
            blocks = [block for block in body.strip().split("\n\n") if block.strip()]
            for number, block in enumerate(blocks, 1):
                self.assertTrue(block.endswith(" ^p%04d" % number), "%s block %d" % (name, number))
            marked += 1
        self.assertEqual(marked, 6)

    def test_two_people_share_a_first_name_and_one_person_is_private(self):
        people = [n.rsplit("/", 1)[-1] for n in self.vault.notes if places.in_home(n, "atlas/people")]
        self.assertEqual(len([name for name in people if name.startswith("nick-")]), 2)
        keys, _ = notes.front(self.vault.text("atlas/people/maya-brandt.md"))
        self.assertEqual(keys["private"], "true")


class TheCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vault = notes.Vault(VAULT)
        cls.cases = {}
        for folder in sorted((FIXTURES / "cases").iterdir()):
            if folder.is_dir():
                cls.cases[folder.name] = (
                    folder,
                    json.loads((folder / "expected.json").read_text(encoding="utf-8")),
                )

    def test_there_are_the_twelve_cases_in_order(self):
        wanted = ["%02d-%s" % (number, name) for number, name in enumerate(finish.CASES, 1)]
        self.assertEqual(sorted(self.cases), wanted)

    def test_each_case_has_something_arriving_and_a_reason(self):
        for name, (folder, expected) in self.cases.items():
            self.assertEqual(finish.case_problems(expected), [], name)
            self.assertGreater(len(expected.get("why", "").split()), 8, name)
            arrived = [path for path in (folder / "input").iterdir() if path.is_file()]
            self.assertTrue(arrived, name)
            for path in arrived:
                self.assertTrue(path.read_text(encoding="utf-8").strip(), path)
                if path.suffix == ".json":
                    json.loads(path.read_text(encoding="utf-8"))

    def test_every_entry_has_its_fields(self):
        for name, (_, expected) in self.cases.items():
            made = {entry["path"] for entry in expected["exists"]["objects"]}
            for part in finish.CASE_PARTS:
                for entry in expected[part]["objects"]:
                    where = "%s %s objects %r" % (name, part, entry)
                    self.assertIsInstance(entry, dict, where)
                    self.assertTrue(set(entry) <= {"path", "type", "private"}, where)
                    self.assertTrue(in_right_home(entry["path"], entry["type"]), where)
                    self.assertIsInstance(entry.get("private", False), bool, where)
                for entry in expected[part]["links"]:
                    where = "%s %s links %r" % (name, part, entry)
                    self.assertIsInstance(entry, dict, where)
                    self.assertTrue({"from", "to"} <= set(entry) <= {"from", "to", "shown"}, where)
                    for end in ("from", "to"):
                        self.assertTrue(entry[end].endswith(".md"), where)
                    self.assertTrue(entry.get("shown", "x").strip(), where)
                    # Whatever is linked to must be in the vault or made by this case.
                    self.assertTrue(entry["to"] in self.vault.notes or entry["to"] in made, where)
                for entry in expected[part]["history"]:
                    where = "%s %s history %r" % (name, part, entry)
                    self.assertIsInstance(entry, dict, where)
                    self.assertTrue(
                        {"on", "text"} <= set(entry) <= {"on", "text", "basis", "source"}, where)
                    self.assertTrue(entry["on"] in self.vault.notes or entry["on"] in made, where)
                    self.assertTrue(entry["text"].strip() and "|" not in entry["text"], where)
                    self.assertIn(entry.get("basis", "stated"), BASES, where)
                    self.assertIn(".md", entry.get("source", ".md"), where)

    def test_the_people_in_the_cases_are_the_people_in_the_vault(self):
        emails = {}
        for note in self.vault.notes:
            if places.in_home(note, "atlas/people"):
                keys, _ = notes.front(self.vault.text(note))
                if "email" in keys:
                    emails[keys["email"]] = keys.get("name")
        seen = 0
        for name, (folder, _) in self.cases.items():
            for path in (folder / "input").glob("*.json"):
                arrived = json.loads(path.read_text(encoding="utf-8"))
                people = list(arrived.get("attendees", []))
                for event in arrived.get("events", []):
                    people += event["attendees"]
                for someone in people:
                    self.assertIn(someone["email"], emails, name)
                    self.assertTrue(someone["email"].endswith(".example"), name)
                    seen += 1
        self.assertGreater(seen, 15)


if __name__ == "__main__":
    unittest.main()
