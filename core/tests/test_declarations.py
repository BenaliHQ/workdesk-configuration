"""The declarations: the files that ship, and what the loader refuses."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
CORE = TESTS.parent
for folder in (CORE, TESTS):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import stage1_finish  # noqa: E402
from wd import declarations, places  # noqa: E402

LIMITS = json.loads((CORE / "budgets.json").read_text(encoding="utf-8"))
NAMED = ["type", "name", "aliases", "private"]

# What each object type holds. `home` and `linkable` are the build
# spec's "Object homes" table. The keys and sections were set for S1.1.
OBJECTS = {
    "person": ("objects/people", True, NAMED, ["Currently", "History"]),
    "company": ("objects/companies", True, NAMED, ["Currently", "History"]),
    "project": ("objects/projects", True, NAMED, ["Currently", "History"]),
    "term": ("objects/terms", True, NAMED, ["History"]),
    "concept": ("objects/concepts", True, NAMED + ["from"], ["History"]),
    "meeting": ("objects/meetings", False, ["type", "date", "attendees", "source", "private"],
                ["Decisions", "Promises", "Detail"]),
    "decision": ("objects/decisions", False, ["type", "date", "source", "private"], ["History"]),
    "quote": ("objects/quotes", False, ["type", "by", "source", "private"], []),
}
# Build spec, "Source frontmatter", in its order.
SOURCE_KEYS = [
    "type", "kind", "title", "date", "author", "sent-by", "status", "starred",
    "private", "take", "produced", "sha256-original",
]
SOURCES = {
    "meeting-recording": "sources/recordings",
    "article": "sources/links",
    "post": "sources/links",
    "video": "sources/links",
    "podcast": "sources/links",
    "book": "sources/links",
    "agent-session": "sources/sessions",
    "capture": "sources/captures",
    "calendar": None,
}


class Shipped(unittest.TestCase):
    def test_the_eight_object_types(self):
        found = declarations.objects()
        self.assertEqual(list(found), list(OBJECTS))
        self.assertEqual(len(found), LIMITS["Object types"])
        for kind, (home, linkable, required, sections) in OBJECTS.items():
            self.assertEqual(found[kind], {
                "home": home,
                "linkable": linkable,
                "name-from": "first-heading" if linkable else None,
                "required-keys": required,
                "sections": sections,
                "summary-max-words": 60,
            }, kind)

    def test_the_nine_source_kinds(self):
        found = declarations.sources()
        self.assertEqual(list(found), list(SOURCES))
        self.assertEqual(len(found), LIMITS["Source kinds"])
        for kind, home in SOURCES.items():
            self.assertEqual(found[kind], {
                "kind": kind,
                "home": home,
                "required-keys": SOURCE_KEYS if home else [],
            }, kind)

    def test_the_files_meet_the_stage_1_finish_test(self):
        objects, sources = stage1_finish.read_declarations(declarations.FOLDER)
        self.assertEqual(stage1_finish.declaration_problems(objects, sources), [])

    def test_each_file_holds_its_keys_in_the_build_specs_order(self):
        for kind in declarations.OBJECT_TYPES:
            text = (declarations.FOLDER / "objects" / (kind + ".json")).read_text(encoding="utf-8")
            self.assertEqual(list(json.loads(text)), list(declarations.OBJECT_KEYS), kind)

    def test_the_homes_come_from_the_declarations(self):
        self.assertEqual(
            places.OBJECT_HOMES, [(kind, home) for kind, (home, _, _, _) in OBJECTS.items()])
        self.assertEqual(
            places.LINKABLE, tuple(kind for kind, found in OBJECTS.items() if found[1]))
        self.assertEqual(places.LINKABLE, ("person", "company", "project", "term", "concept"))
        self.assertEqual(
            places.SOURCE_HOMES,
            ["sources/recordings", "sources/links", "sources/sessions", "sources/captures"],
        )
        self.assertEqual(places.home_of("quote"), "objects/quotes")

    def test_every_home_is_a_folder_of_the_new_layout(self):
        homes = [home for _, home in places.OBJECT_HOMES] + places.SIGNAL_HOMES
        homes += places.SOURCE_HOMES + [places.WRITING]
        self.assertEqual(sorted(homes), sorted(stage1_finish.FOLDERS))
        self.assertEqual(len(places.SIGNAL_HOMES), LIMITS["Signals"])
        self.assertEqual(places.ROOT_FILES, stage1_finish.ROOT_FILES)


class Loader(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.folder = Path(scratch.name) / "declarations"
        shutil.copytree(str(declarations.FOLDER), str(self.folder))

    def change(self, name, **changes):
        path = self.folder / name
        found = json.loads(path.read_text(encoding="utf-8"))
        for key, value in changes.items():
            if value is KeyError:
                del found[key.replace("_", "-")]
            else:
                found[key.replace("_", "-")] = value
        path.write_text(json.dumps(found), encoding="utf-8")

    def problems(self):
        return declarations.read(self.folder)[2]

    def test_a_copy_of_the_shipped_files_loads(self):
        objects, sources = declarations.load(self.folder)
        self.assertEqual(objects, declarations.objects())
        self.assertEqual(sources, declarations.sources())
        self.assertEqual(self.problems(), [])

    def test_a_missing_file_is_named_and_stops_the_load(self):
        (self.folder / "objects" / "quote.json").unlink()
        self.assertEqual(self.problems(), ["objects/quote.json: there is no file"])
        with self.assertRaises(declarations.DeclarationError) as raised:
            declarations.load(self.folder)
        self.assertIn("objects/quote.json: there is no file", str(raised.exception))

    def test_no_folder_at_all(self):
        self.assertEqual(len(declarations.read(self.folder / "nowhere")[2]), 17)

    def test_a_file_that_is_not_json_or_not_a_group(self):
        (self.folder / "sources" / "book.json").write_text("{not json", encoding="utf-8")
        (self.folder / "objects" / "term.json").write_text("[]", encoding="utf-8")
        problems = self.problems()
        self.assertEqual(len(problems), 2)
        self.assertIn("objects/term.json: not a group of values", problems)
        self.assertTrue(problems[1].startswith("sources/book.json: not valid JSON"))

    def test_a_ninth_type_is_refused(self):
        shutil.copyfile(
            str(self.folder / "objects" / "term.json"), str(self.folder / "objects" / "task.json"))
        shutil.copyfile(
            str(self.folder / "sources" / "post.json"), str(self.folder / "sources" / "email.json"))
        self.assertEqual(self.problems(), [
            "objects/task.json: not one of the 8 that are declared",
            "sources/email.json: not one of the 9 that are declared",
        ])

    def test_an_objects_keys(self):
        self.change("objects/person.json", color="blue")
        self.change("objects/company.json", sections=KeyError)
        self.change("objects/term.json", home="objects/terms/")
        self.change("objects/concept.json", home="../outside")
        self.change("objects/project.json", linkable="yes")
        self.change("objects/decision.json", required_keys=["date"])
        self.change("objects/quote.json", summary_max_words=True)
        self.change("objects/meeting.json", summary_max_words=0)
        self.assertEqual(self.problems(), [
            "objects/person.json: its keys are not exactly home, linkable, name-from, "
            "required-keys, sections, summary-max-words",
            "objects/company.json: its keys are not exactly home, linkable, name-from, "
            "required-keys, sections, summary-max-words",
            "objects/company.json: sections is not a list of headings",
            "objects/project.json: linkable is not true or false",
            "objects/term.json: home is not a folder in the vault",
            "objects/concept.json: home is not a folder in the vault",
            "objects/meeting.json: summary-max-words is not a whole number above zero",
            "objects/decision.json: required-keys is not a list of keys with type among them",
            "objects/quote.json: summary-max-words is not a whole number above zero",
        ])

    def test_how_a_name_is_taken(self):
        self.change("objects/person.json", name_from="file-name")
        self.change("objects/meeting.json", name_from="first-heading")
        # A type that is not linked by name may leave the key out.
        self.change("objects/quote.json", name_from=KeyError)
        self.assertEqual(self.problems(), [
            "objects/person.json: name-from is not first-heading",
            "objects/meeting.json: it is not linked by name, so name-from is null",
        ])
        self.assertIsNone(declarations.read(self.folder)[0]["quote"]["name-from"])

    def test_two_types_cannot_share_a_home(self):
        self.change("objects/term.json", home="objects/concepts")
        self.assertEqual(self.problems(), ["objects/concepts: the home of term and concept"])

    def test_a_sources_keys(self):
        self.change("sources/article.json", kind="link")
        self.change("sources/video.json", home="/sources/links")
        self.change("sources/capture.json", required_keys="type")
        self.change("sources/calendar.json", take="none")
        self.assertEqual(self.problems(), [
            "sources/article.json: kind is not article",
            "sources/video.json: home is not a folder in the vault, and not null",
            "sources/capture.json: required-keys is not a list of keys",
            "sources/calendar.json: its keys are not exactly kind, home, required-keys",
        ])


if __name__ == "__main__":
    unittest.main()
