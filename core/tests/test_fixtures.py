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
import stage1_finish  # noqa: E402
from wd import declarations, measure, notes, places  # noqa: E402

TYPE_HOMES = dict(places.OBJECT_HOMES)
PEOPLE = TYPE_HOMES["person"]
BASES = ("stated", "reported", "inferred", "correction")
HISTORY = re.compile(
    r"^- \d{4}-\d\d-\d\d \| [^|]+ \| (%s) \| [^|]+ \| run-\d{8}-\d{4}$" % "|".join(BASES)
)
# The links that are left dead on purpose. See fixtures/README.md.
DEAD_ON_PURPOSE = {
    "sources/recordings/2026-11-09-bluepeak-sync",
    "objects/concepts/handoff-tax",
}
# An older note, left without its keys on purpose. See fixtures/README.md.
NOT_IN_FORMAT = {"objects/people/marcus.md"}
# Build spec, "Object frontmatter": the keys every object opens with, in order.
OPENING_KEYS = ["type", "name", "aliases", "private"]
MAX_SUMMARY_LINES = 3


def in_right_home(path, kind):
    return kind in TYPE_HOMES and places.in_home(path, TYPE_HOMES[kind])


def key_order(text):
    """The keys of a note's opening block, in the order they are written."""
    order = []
    for line in text.split("\n")[1:]:
        if line.strip() == "---":
            break
        found = notes.KEY.match(line)
        if found:
            order.append(found.group(1))
    return order


def headings(body):
    return [line[3:].strip() for line in body.split("\n") if line.startswith("## ")]


def summary(body):
    """The first paragraph under the title."""
    lines = body.split("\n")
    start = next(number for number, line in enumerate(lines) if line.startswith("# ")) + 1
    while not lines[start].strip():
        start += 1
    end = start
    while end < len(lines) and lines[end].strip():
        end += 1
    return lines[start:end]


class TheVault(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vault = notes.Vault(VAULT)

    def linkable(self):
        return [
            note for kind in places.LINKABLE
            for note in self.vault.notes if places.in_home(note, TYPE_HOMES[kind])
        ]

    def objects(self):
        return [
            (kind, note) for kind, home in places.OBJECT_HOMES
            for note in self.vault.notes if places.in_home(note, home)
        ]

    def test_about_forty_notes(self):
        self.assertEqual(finish.note_count(VAULT), 44)

    def test_the_vault_is_in_the_new_layout(self):
        files, folders = stage1_finish.tree(VAULT)
        self.assertEqual(stage1_finish.layout_problems(files, folders), [])
        self.assertEqual(stage1_finish.home_problems(files), [])

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
                self.assertIn(note, NOT_IN_FORMAT)
                continue
            self.assertEqual(keys["name"], notes.first_heading(body), note)
            self.assertIn(keys.get("private"), ("true", "false"), note)
            self.assertTrue(keys.get("aliases", "").startswith("["), note)
            names.setdefault(keys["name"], []).append(note)
        self.assertEqual({name: where for name, where in names.items() if len(where) > 1}, {})
        self.assertEqual(len(names), 20)

    def test_every_object_follows_its_declaration(self):
        checked = 0
        for kind, note in self.objects():
            if note in NOT_IN_FORMAT:
                continue
            declared = declarations.objects()[kind]
            text = self.vault.text(note)
            keys, body = notes.front(text)
            self.assertEqual(keys.get("type"), kind, note)
            for key in declared["required-keys"]:
                self.assertIn(key, keys, note)
            # type, name, aliases, private, then the type's own keys.
            order = key_order(text)
            opening = [key for key in OPENING_KEYS if key in declared["required-keys"]]
            self.assertEqual(order[:len(opening)], opening, note)
            rest = [key for key in declared["required-keys"] if key not in OPENING_KEYS]
            self.assertEqual(order[len(opening):len(opening) + len(rest)], rest, note)
            self.assertEqual(
                [heading for heading in headings(body) if heading in declared["sections"]],
                declared["sections"], note,
            )
            self.assertEqual(
                [heading for heading in headings(body) if heading not in declared["sections"]],
                [], note,
            )
            opening_lines = summary(body)
            self.assertLessEqual(len(opening_lines), MAX_SUMMARY_LINES, note)
            self.assertLessEqual(
                len(notes.words(" ".join(opening_lines))), declared["summary-max-words"], note)
            checked += 1
        self.assertEqual(checked, 30)

    def test_a_meetings_attendees_are_links_to_people(self):
        for kind, note in self.objects():
            if kind != "meeting":
                continue
            keys, _ = notes.front(self.vault.text(note))
            attendees = notes.link_targets(keys["attendees"])
            self.assertTrue(attendees, note)
            for target in attendees:
                self.assertTrue(
                    places.in_home(self.vault.resolve(target, note) or "", PEOPLE), note)

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

    def test_every_source_has_its_keys_its_home_and_a_marker_on_each_passage(self):
        marked = 0
        for name in self.vault.notes:
            if not any(places.in_home(name, home) for home in places.SOURCE_HOMES):
                continue
            keys, body = notes.front(self.vault.text(name))
            self.assertEqual(keys.get("type"), "source", name)
            declared = declarations.sources()[keys["kind"]]
            self.assertTrue(places.in_home(name, declared["home"]), name)
            self.assertEqual(key_order(self.vault.text(name)), declared["required-keys"], name)
            self.assertIn(keys["status"], ("saved", "read"), name)
            self.assertRegex(keys.get("sha256-original", ""), r"^[0-9a-f]{64}$", name)
            self.assertEqual(stage1_finish.marker_problems(self.vault.text(name)), [], name)
            # Whatever a source produced is in the vault.
            for target in notes.link_targets(keys["produced"]):
                self.assertIsNotNone(self.vault.resolve(target, name), name)
            marked += 1
        self.assertEqual(marked, 8)

    def test_two_people_share_a_first_name_and_one_person_is_private(self):
        people = [n.rsplit("/", 1)[-1] for n in self.vault.notes if places.in_home(n, PEOPLE)]
        self.assertEqual(len([name for name in people if name.startswith("nick-")]), 2)
        keys, _ = notes.front(self.vault.text(PEOPLE + "/maya-brandt.md"))
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

    def test_what_arrives_is_a_declared_kind(self):
        for name, (folder, _) in self.cases.items():
            for path in (folder / "input").glob("*.json"):
                arrived = json.loads(path.read_text(encoding="utf-8"))
                self.assertIn(arrived["kind"], declarations.SOURCE_KINDS, name)

    def test_every_entry_has_its_fields(self):
        homes = [home for _, home in places.OBJECT_HOMES]
        written = homes + places.SIGNAL_HOMES
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
                    self.assertTrue(
                        {"from", "to"} <= set(entry) <= {"from", "to", "shown", "in"}, where)
                    self.assertEqual(entry.get("in", "attendees"), "attendees", where)
                    for end in ("from", "to"):
                        self.assertTrue(entry[end].endswith(".md"), where)
                        # A link starts and ends in an object home or a signal.
                        self.assertTrue(
                            any(places.in_home(entry[end], home) for home in written), where)
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
                    if "source" in entry:
                        # A history line points into a source's permanent home.
                        self.assertTrue(
                            any(places.in_home(entry["source"], home)
                                for home in places.SOURCE_HOMES), where)

    def test_private_words_are_words_that_arrived(self):
        marked = 0
        for name, (folder, expected) in self.cases.items():
            arrived = " ".join(
                path.read_text(encoding="utf-8") for path in (folder / "input").iterdir()
            )
            for words in expected.get("private_words", []):
                self.assertIn(words, arrived, name)
                marked += 1
        self.assertEqual(marked, 1)

    def test_a_quoted_source_has_those_exact_words(self):
        # A history line that cites a file plus words must quote words that are there.
        cited = 0
        quote = re.compile(r'\[\[([^\]|#]+)\]\] "([^"]+)"')
        for name in self.vault.notes:
            for target, words in quote.findall(self.vault.text(name)):
                source = self.vault.resolve(target, name)
                self.assertIsNotNone(source, "%s cites %s" % (name, target))
                self.assertIn(words, self.vault.text(source), "%s cites %s" % (name, target))
                cited += 1
        self.assertGreater(cited, 3)

    def test_the_people_in_the_cases_are_the_people_in_the_vault(self):
        emails = {}
        for note in self.vault.notes:
            if places.in_home(note, PEOPLE):
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
