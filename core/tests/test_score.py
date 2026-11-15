"""`wd score`: the throwaway scorer, on the test vault and on hard spots."""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
CORE = TESTS.parent
WD = CORE / "bin" / "wd"
FIXTURES = TESTS / "fixtures"
VAULT = FIXTURES / "vault"
for folder in (CORE, TESTS):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import score  # noqa: E402
import stage0_finish as finish  # noqa: E402
from wd import cli, notes, places  # noqa: E402

PERSON = "---\ntype: person\n---\n# %s\n\n%s\n"


def build(folder, files):
    for name, text in files.items():
        path = Path(folder) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return Path(folder)


def scored(files):
    """Score a small vault made for one test. Returns the report and the scratch copy."""
    with tempfile.TemporaryDirectory() as folder:
        vault = build(Path(folder) / "vault", files)
        scratch = Path(folder) / "scratch"
        report = score.score(vault, scratch)
        copies = {
            path.relative_to(scratch).as_posix(): path.read_text(encoding="utf-8")
            for path in scratch.rglob("*.md")
        }
    return report, copies


def counts(report, kind="person"):
    return tuple(report["by_type"][kind][name] for name in ("correct", "wrong", "missed"))


SAM = {"objects/people/sam-rivera.md": PERSON % ("Sam Rivera", "Leads operations.")}
SAM_LINK = "[[objects/people/sam-rivera|Sam Rivera]]"


class TheTestVault(unittest.TestCase):
    def test_the_known_answers(self):
        answers = json.loads((FIXTURES / "answers.json").read_text(encoding="utf-8"))["score"]
        with tempfile.TemporaryDirectory() as scratch:
            report = score.score(VAULT, scratch)
        self.assertEqual(report["by_type"], answers["by_type"])
        self.assertEqual(finish.score_problems(report), [])
        self.assertEqual((report["right_rate"], report["miss_rate"]), (1.0, 0.0))

    def test_every_link_that_shows_a_full_name_was_scored(self):
        # Counted a second way: a plain search for `|Full Name]]` in each
        # note the linker may write in, below the opening block.
        vault = notes.Vault(VAULT)
        known, _ = score.names(vault)
        found = {kind: 0 for kind in score.TYPES}
        for note in score.workplace(vault):
            _, body = notes.front(vault.text(note))
            for name, (_, kind) in known.items():
                if len(name.split()) >= 2:
                    found[kind] += len(re.findall(r"\|%s\]\]" % re.escape(name), body))
        with tempfile.TemporaryDirectory() as scratch:
            report = score.score(VAULT, scratch)
        self.assertEqual(
            found, {kind: sum(report["by_type"][kind].values()) for kind in score.TYPES}
        )
        self.assertEqual(sum(found.values()), 68)


class Names(unittest.TestCase):
    def test_a_name_is_the_first_heading_for_every_type(self):
        # A project is named as it is headed. Nothing is cut from the end.
        report, _ = scored({
            "objects/projects/rollout.md": "# Acme Rollout Brief\n\nA project.\n",
            "objects/terms/standing-order.md": "# standing order\n\nA term.\n",
            "objects/meetings/m.md":
                "# M\n\nThe [[objects/projects/rollout|Acme Rollout Brief]] runs on a "
                "[[objects/terms/standing-order|standing order]].\n",
        })
        self.assertEqual(report["names"], 2)
        self.assertEqual(counts(report, "project"), (1, 0, 0))
        self.assertEqual(counts(report, "term"), (1, 0, 0))

    def test_the_types_are_the_ones_linked_by_name(self):
        self.assertEqual(score.TYPES, ("person", "company", "project", "term", "concept"))
        self.assertEqual(set(score.LABELS), set(score.TYPES))

    def test_a_shared_name_and_a_first_name_are_not_linked(self):
        vault_files = dict(SAM)
        vault_files.update({
            "objects/people/nick.md": PERSON % ("Nick", "First name only."),
            "objects/people/lee-one.md": PERSON % ("Lee Castillo", "One."),
            "objects/people/lee-two.md": PERSON % ("Lee Castillo", "Two."),
            "objects/companies/acme.md": "# Acme\n\nWith [[objects/people/lee-one|Lee Castillo]] and Nick.\n",
        })
        report, copies = scored(vault_files)
        self.assertEqual(report["names_shared_by_two_objects"], ["Lee Castillo"])
        self.assertEqual(report["names"], 2)
        # The link was not taken, because its words are not a name any more.
        self.assertIn("[[objects/people/lee-one|Lee Castillo]]", copies["objects/companies/acme.md"])
        self.assertEqual(counts(report), (0, 0, 0))


class Matching(unittest.TestCase):
    def one_note(self, body, extra=None):
        files = dict(SAM)
        files["objects/meetings/m.md"] = "---\ntype: meeting\n---\n# Meeting\n\n%s\n" % body
        files.update(extra or {})
        return scored(files)

    def test_a_plain_link_comes_back(self):
        report, copies = self.one_note("Met %s today." % SAM_LINK)
        self.assertEqual(counts(report), (1, 0, 0))
        self.assertIn("Met Sam Rivera today.", copies["objects/meetings/m.md"])

    def test_a_possessive_and_a_table_cell(self):
        report, _ = self.one_note(
            "%s's plan.\n\n| who |\n|---|\n| [[objects/people/sam-rivera\\|Sam Rivera]] |" % SAM_LINK
        )
        self.assertEqual(counts(report), (2, 0, 0))

    def test_the_longest_name_wins(self):
        extra = {"objects/projects/rollout.md": "# Sam Rivera Rollout\n\nA project.\n"}
        report, _ = self.one_note(
            "The [[objects/projects/rollout|Sam Rivera Rollout]] and %s." % SAM_LINK, extra
        )
        self.assertEqual(counts(report, "project"), (1, 0, 0))
        self.assertEqual(counts(report), (1, 0, 0))

    def test_a_link_that_showed_a_name_but_pointed_elsewhere_is_wrong(self):
        extra = {"objects/people/dana-whitfield.md": PERSON % ("Dana Whitfield", "Finance.")}
        report, _ = self.one_note("With [[objects/people/dana-whitfield|Sam Rivera]].", extra)
        self.assertEqual(counts(report), (0, 1, 0))
        self.assertEqual(report["examples"]["wrong"], ["objects/meetings/m.md line 6: Sam Rivera"])

    def test_part_of_a_longer_word_is_missed_not_matched(self):
        # The words run into a digit, so they are not a whole name there.
        report, _ = self.one_note("Team %s2 met." % SAM_LINK)
        self.assertEqual(counts(report), (0, 0, 1))

    def test_a_notes_own_name_is_not_linked(self):
        files = {"objects/people/sam-rivera.md": PERSON % ("Sam Rivera", "About %s." % SAM_LINK)}
        report, _ = scored(files)
        self.assertEqual(counts(report), (0, 0, 1))

    def test_headings_code_and_callout_titles_are_left_alone(self):
        report, copies = self.one_note(
            "## With %s\n\n`%s`\n\n```\n%s\n```\n\n> [!note] %s\n> Body with %s."
            % (SAM_LINK, SAM_LINK, SAM_LINK, SAM_LINK, SAM_LINK)
        )
        # Only the link in the callout's body is the linker's to make.
        self.assertEqual(counts(report), (1, 0, 0))
        self.assertEqual(copies["objects/meetings/m.md"].count(SAM_LINK), 4)

    def test_a_link_inside_a_comment_is_left_alone(self):
        report, copies = self.one_note(
            "%%%% hidden %s %%%% and <!-- also %s -->\n\n%%%%\nseveral lines\n%s\n%%%%\n\n"
            "<!--\n%s\n-->\n\nBut %s counts."
            % (SAM_LINK, SAM_LINK, SAM_LINK, SAM_LINK, SAM_LINK)
        )
        self.assertEqual(counts(report), (1, 0, 0))
        self.assertEqual(copies["objects/meetings/m.md"].count(SAM_LINK), 4)

    def test_a_dead_link_cannot_be_judged(self):
        report, _ = self.one_note("With [[objects/people/gone|Sam Rivera]].")
        self.assertEqual(counts(report), (0, 0, 0))
        self.assertEqual(report["links_with_a_missing_target"], 1)

    def test_a_one_word_name_and_a_link_outside_the_object_homes_are_not_taken(self):
        extra = {"objects/companies/acme.md": "# Acme\n\nA company.\n",
                 "notes/today.md": "Saw %s." % SAM_LINK}
        report, copies = self.one_note("At [[objects/companies/acme|Acme]].", extra)
        self.assertEqual(sum(sum(c.values()) for c in report["by_type"].values()), 0)
        self.assertNotIn("notes/today.md", copies)

    def test_nothing_scored_gives_no_rates(self):
        report, _ = scored(SAM)
        self.assertIsNone(report["right_rate"])
        self.assertIsNone(report["miss_rate"])
        self.assertTrue(finish.score_problems(report))


class Command(unittest.TestCase):
    def run_wd(self, arguments, state):
        environment = dict(os.environ, WD_STATE_DIR=str(state))
        return subprocess.run(
            [sys.executable, str(WD)] + [str(argument) for argument in arguments],
            env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True,
        )

    def test_it_scores_prints_saves_and_changes_nothing(self):
        with tempfile.TemporaryDirectory() as state:
            before, _ = finish.snapshot(VAULT)
            result = self.run_wd(["score", VAULT], state)
            after, _ = finish.snapshot(VAULT)
            self.assertEqual(result.returncode, cli.OK, result.stderr)
            report = json.loads((Path(state) / "score.json").read_text(encoding="utf-8"))
            scratch = Path(report["scratch"])
            self.assertEqual(scratch, (Path(state) / "score-scratch").resolve())
            self.assertTrue((scratch / "objects/people/sam-rivera.md").is_file())
            # A second run starts from a clean scratch folder.
            (scratch / "left-over.md").write_text("old", encoding="utf-8")
            self.assertEqual(self.run_wd(["score", VAULT], state).returncode, cli.OK)
            self.assertFalse((scratch / "left-over.md").exists())
        self.assertEqual(finish.changed_files(before, after), [])
        self.assertEqual(finish.score_problems(report), [])
        self.assertEqual(finish.stamp_problems(report, VAULT), [])
        self.assertIn("Right 100.0 times in 100. Misses 0.0 in 100.", result.stdout)

    def test_the_private_folder_is_the_operators_writing(self):
        self.assertEqual(score.PRIVATE, "writing")

    @unittest.skipIf(os.geteuid() == 0, "the administrator can open every folder")
    def test_the_private_folder_is_never_opened(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = build(Path(folder) / "vault", dict(SAM, **{
                "objects/meetings/m.md": "# M\n\nMet %s.\n" % SAM_LINK,
                "%s/journal.md" % score.PRIVATE: "Wrote about %s. wd-canary-words\n" % SAM_LINK,
            }))
            private = vault / score.PRIVATE
            # Locked shut: opening it at all would be reported as unreadable.
            private.chmod(0)
            try:
                state = Path(folder) / "state"
                result = self.run_wd(["score", vault], state)
                report = json.loads((state / "score.json").read_text(encoding="utf-8"))
                kept = [path.relative_to(state).as_posix() for path in state.rglob("*")]
            finally:
                private.chmod(0o700)
        self.assertEqual(result.returncode, cli.OK, result.stderr)
        self.assertEqual(report["unreadable"], [])
        self.assertEqual(counts(report), (1, 0, 0))
        self.assertFalse([name for name in kept if score.PRIVATE in name])

    def test_a_shortcut_into_the_private_folder_is_not_followed(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = build(Path(folder) / "vault", dict(SAM, **{
                "objects/meetings/m.md": "# M\n\nMet %s.\n" % SAM_LINK,
                "%s/journal.md" % score.PRIVATE: "# Private Page\n\nwd-canary-words %s\n" % SAM_LINK,
            }))
            os.symlink(str(vault / score.PRIVATE / "journal.md"),
                       str(vault / "objects" / "people" / "shortcut.md"))
            state = Path(folder) / "state"
            result = self.run_wd(["score", vault], state)
            kept = "".join(
                path.read_text(encoding="utf-8") for path in state.rglob("*") if path.is_file()
            )
        self.assertEqual(result.returncode, cli.OK, result.stderr)
        self.assertNotIn("wd-canary-words", kept)
        self.assertNotIn("shortcut.md", kept)

    def test_it_will_not_score_its_own_scratch_folder(self):
        with tempfile.TemporaryDirectory() as state:
            self.assertEqual(self.run_wd(["score", VAULT], state).returncode, cli.OK)
            scratch = Path(state) / "score-scratch"
            kept = sorted(path.name for path in scratch.rglob("*.md"))
            result = self.run_wd(["score", scratch], state)
            self.assertEqual(result.returncode, cli.FAILED)
            self.assertIn("own scratch folder", result.stderr)
            self.assertEqual(sorted(path.name for path in scratch.rglob("*.md")), kept)

    def test_it_refuses_to_keep_its_state_inside_the_vault(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = build(folder, SAM)
            result = self.run_wd(["score", vault], vault / "state")
            self.assertFalse((vault / "state").exists())
        self.assertEqual(result.returncode, cli.FAILED)
        self.assertIn("inside the vault", result.stderr)

    def test_no_vault_and_a_missing_vault_fail(self):
        with tempfile.TemporaryDirectory() as state:
            self.assertEqual(self.run_wd(["score"], state).returncode, cli.USAGE)
            self.assertEqual(self.run_wd(["score", "/no/such/vault"], state).returncode, cli.FAILED)


if __name__ == "__main__":
    unittest.main()
