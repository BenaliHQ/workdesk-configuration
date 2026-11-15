"""`wd check`: each kind of problem, on a tiny vault built for the test."""

import io
import json
import os
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
HOME = FIXTURES / "home"
for folder in (CORE, TESTS):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import sample_vault as sample  # noqa: E402
import stage0_finish as stage0  # noqa: E402
import stage1_finish as stage1  # noqa: E402
from wd import check, cli, graph, measure, notes  # noqa: E402

PERSON = (
    "---\ntype: person\nname: %(name)s\naliases: []\nprivate: false\n---\n"
    "# %(name)s\n\n%(says)s\n"
)
LEE = "objects/people/lee-castillo.md"


def person(name, says):
    return PERSON % {"name": name, "says": says}


def found_in(files):
    """Check a vault made of these files. Returns each problem as (note, kind)."""
    with tempfile.TemporaryDirectory() as folder:
        report = check.check(sample.build(folder, files))
    return [(found["note"], found["kind"]) for found in report["problems"]]


def after(changes):
    """The problems in the clean vault once these notes are changed."""
    return found_in(sample.with_files(changes))


def swap(note, old, new):
    """One note of the clean vault with some of its words replaced."""
    text = sample.CLEAN[note]
    assert old in text, (note, old)
    return {note: text.replace(old, new)}


class ACleanVault(unittest.TestCase):
    def test_nothing_is_wrong_with_it(self):
        self.assertEqual(found_in(sample.CLEAN), [])

    def test_the_report_names_the_vault_the_time_and_every_kind(self):
        with tempfile.TemporaryDirectory() as folder:
            report = check.check(sample.build(folder, sample.CLEAN))
            self.assertEqual(stage0.stamp_problems(report, folder), [])
        self.assertEqual(stage1.check_report_problems(report), [])
        self.assertEqual(report["checked"], {"objects": 8, "syntheses": 1})
        self.assertEqual(report["by_kind"], {kind: 0 for kind, _ in check.KINDS})
        self.assertEqual(report["unreadable"], [])

    def test_every_kind_is_a_short_fixed_word_with_plain_words_beside_it(self):
        for kind, label in check.KINDS:
            self.assertRegex(kind, r"^[a-z]+(-[a-z]+)*$")
            self.assertGreater(len(label.split()), 3, kind)


class AgainstTheDeclaration(unittest.TestCase):
    def test_a_missing_key(self):
        self.assertEqual(
            after(swap(sample.SAM, "private: false\n", "")), [(sample.SAM, "missing-key")])
        # One problem for the note, however many keys are missing.
        self.assertEqual(
            after(swap(sample.QUOTE, "by: Sam Rivera\n", "")), [(sample.QUOTE, "missing-key")])
        with tempfile.TemporaryDirectory() as folder:
            report = check.check(sample.build(folder, sample.with_files(
                swap(sample.MEETING, "date: 2026-11-12\n", ""))))
        self.assertEqual(report["problems"][0]["sentence"], "It is missing the key date.")

    def test_a_quote_is_dated(self):
        # Contract rule 6.
        self.assertEqual(
            after(swap(sample.QUOTE, "date: 2026-11-12\n", "")), [(sample.QUOTE, "missing-key")])

    def test_a_key_with_nothing_after_it_is_there(self):
        # A private meeting keeps no recording, so its `source` is empty.
        files = sample.with_files(swap(sample.MEETING, "source: \"[[%s]]\"" % sample.RECORDING,
                                       "source:"))
        self.assertEqual(found_in(files), [])

    def test_a_note_with_no_opening_block(self):
        found = after({LEE: "# Lee Castillo\n\nWorks with %s.\n" % sample.SAM_LINK})
        self.assertEqual(found, [(LEE, "missing-key")])

    def test_the_home_decides_the_type(self):
        self.assertEqual(
            after(swap(sample.TERM, "type: term", "type: concept")), [(sample.TERM, "wrong-type")])

    def test_the_order_of_the_opening_keys(self):
        moved = swap(sample.SAM, "aliases: [Samuel Rivera]\nprivate: false\n",
                     "private: false\naliases: [Samuel Rivera]\n")
        self.assertEqual(after(moved), [(sample.SAM, "key-order")])
        # A type's own keys come after `private`, in its declaration's order.
        moved = swap(sample.MEETING, "private: false\ndate: 2026-11-12\n",
                     "date: 2026-11-12\nprivate: false\n")
        self.assertEqual(after(moved), [(sample.MEETING, "key-order")])

    def test_a_key_the_declaration_does_not_name_may_sit_anywhere(self):
        moved = swap(sample.SAM, "type: person\n", "type: person\nsample: true\nemail: s@x.example\n")
        self.assertEqual(after(moved), [])

    def test_the_name_is_the_first_heading(self):
        self.assertEqual(
            after(swap(sample.SAM, "# Sam Rivera", "# Samuel Rivera")),
            [(sample.SAM, "name-not-heading")],
        )
        self.assertEqual(
            after(swap(sample.TERM, "# bespoke systems", "# Bespoke systems")),
            [(sample.TERM, "name-not-heading")],
        )

    def test_a_name_is_used_once(self):
        # The second note with the name is the one reported, in any linkable home.
        twin = "objects/terms/acme.md"
        found = after({twin: (
            "---\ntype: term\nname: Acme\naliases: []\nprivate: false\n---\n# Acme\n\n"
            "A word %s uses.\n" % sample.SAM_LINK
        )})
        self.assertEqual(found, [(twin, "name-not-unique")])
        # A meeting has no name, so two meetings may share a heading.
        second = sample.MEETING.replace("12-acme", "13-acme")
        self.assertEqual(after({second: sample.CLEAN[sample.MEETING]}), [])

    def test_a_meeting_always_has_its_three_sections(self):
        self.assertEqual(
            after(swap(sample.MEETING, "## Promises\n\n", "")), [(sample.MEETING, "missing-section")])
        gone = swap(sample.MEETING, "## Decisions", "## Decided")
        self.assertEqual(
            after(gone), [(sample.MEETING, "missing-section"), (sample.MEETING, "unknown-section")])

    def test_history_and_currently_may_be_left_out_while_empty(self):
        text = sample.CLEAN[sample.SAM].split("## Currently")[0]
        self.assertEqual(after({sample.SAM: text}), [])
        # A meeting and a quote may carry a History section.
        files = {
            sample.MEETING: sample.CLEAN[sample.MEETING] + "\n## History\n",
            sample.QUOTE: sample.CLEAN[sample.QUOTE] + "\n## History\n",
        }
        self.assertEqual(after(files), [])

    def test_a_section_the_type_does_not_have(self):
        self.assertEqual(
            after({sample.SAM: sample.CLEAN[sample.SAM] + "\n## Notes\n\nA line.\n"}),
            [(sample.SAM, "unknown-section")],
        )
        # A term has no Currently section.
        self.assertEqual(
            after({sample.TERM: sample.CLEAN[sample.TERM] + "\n## Currently\n"}),
            [(sample.TERM, "unknown-section")],
        )
        # A heading inside code is not a section, and neither is a smaller heading.
        inside = sample.CLEAN[sample.SAM] + "\n```\n## Notes\n```\n\n### Smaller\n"
        self.assertEqual(after({sample.SAM: inside}), [])


class TheSummary(unittest.TestCase):
    def note(self, summary):
        return {LEE: person("Lee Castillo", summary + "\n\n## History\n\n- With %s.\n"
                            % sample.SAM_LINK)}

    def test_three_lines_and_sixty_words_are_within_the_limit(self):
        self.assertEqual(after(self.note("\n".join([" ".join(["word"] * 20)] * 3))), [])

    def test_four_lines_are_too_many(self):
        self.assertEqual(after(self.note("One.\nTwo.\nThree.\nFour.")), [(LEE, "summary-too-long")])

    def test_sixty_one_words_are_too_many(self):
        self.assertEqual(
            after(self.note(" ".join(["word"] * 61))), [(LEE, "summary-too-long")])

    def test_only_the_first_paragraph_is_the_summary(self):
        self.assertEqual(after(self.note("Short.\n\n" + " ".join(["word"] * 200))), [])

    def test_a_note_with_no_summary_is_within_the_limit(self):
        text = "---\ntype: person\nname: Lee Castillo\naliases: []\nprivate: false\n---\n" \
               "# Lee Castillo\n\n## History\n\n- With %s.\n" % sample.SAM_LINK
        self.assertEqual(after({LEE: text}), [])

    def test_what_counts_as_the_summary(self):
        self.assertEqual(check.summary("# Title\n\nOne\ntwo\n\nThree\n"), ["One", "two"])
        self.assertEqual(check.summary("# Title\n## Section\n\nBody\n"), [])


class Links(unittest.TestCase):
    def test_a_link_to_a_note_that_is_not_there(self):
        gone = swap(sample.SAM, sample.ACME_LINK, "[[objects/companies/no-such|No Such]]")
        self.assertEqual(after(gone), [(sample.SAM, "link-goes-nowhere")])

    def test_a_link_in_the_opening_block(self):
        gone = swap(sample.MEETING, "source: \"[[%s]]\"" % sample.RECORDING,
                    "source: \"[[sources/recordings/never-saved]]\"")
        self.assertEqual(after(gone), [(sample.MEETING, "link-goes-nowhere")])

    def test_a_link_in_a_synthesis(self):
        gone = swap(sample.SYNTHESIS, "- [[%s]]" % sample.RECORDING, "- [[sources/links/gone]]")
        self.assertEqual(after(gone), [(sample.SYNTHESIS, "link-goes-nowhere")])

    def test_a_passage_that_is_not_marked(self):
        files = sample.with_files(swap(sample.QUOTE, "#^p0001]]\n", "#^p0004]]\n"))
        self.assertEqual(found_in(files), [(sample.QUOTE, "link-goes-nowhere")])
        with tempfile.TemporaryDirectory() as folder:
            report = check.check(sample.build(folder, files))
        self.assertEqual(
            report["problems"][0]["sentence"],
            "Its link to %s#^p0004 goes nowhere: %s.md has no passage ^p0004."
            % (sample.RECORDING, sample.RECORDING),
        )

    def test_a_marker_counts_only_at_the_end_of_a_block(self):
        self.assertEqual(
            check.markers("One. ^p0001\n\nTwo ^p0002 goes on.\n\nThree.\n^p0003\n"),
            {"p0001", "p0003"},
        )

    def test_a_link_to_a_passage_of_the_note_itself(self):
        text = sample.CLEAN[sample.SAM] + "\nA marked line. ^note1\n\nSee [[#^note1]] and [[#^note2]].\n"
        self.assertEqual(after({sample.SAM: text}), [(sample.SAM, "link-goes-nowhere")])

    def test_the_same_dead_link_twice_is_one_problem(self):
        text = sample.CLEAN[sample.SAM] + "\n[[gone]] and again [[gone|Gone]].\n"
        self.assertEqual(after({sample.SAM: text}), [(sample.SAM, "link-goes-nowhere")])

    def test_links_in_code_are_not_links(self):
        text = sample.CLEAN[sample.SAM] + "\n`[[gone]]`\n\n```\n[[also-gone]]\n```\n"
        self.assertEqual(after({sample.SAM: text}), [])

    def test_only_objects_and_syntheses_are_checked(self):
        files = {
            "signals/briefs/2026-11-13.md": "# Brief\n\n- [[gone]]\n",
            "writing/2026-11-13.md": "Today [[gone]].\n",
            "status.md": "# Status\n\n[[gone]]\n",
            sample.RECORDING + ".md": sample.CLEAN[sample.RECORDING + ".md"].replace(
                "one plan before", "one [[gone]] plan before"),
        }
        self.assertEqual(after(files), [])

    def test_the_parts_of_a_link(self):
        self.assertEqual(
            notes.links("[[a]] [[b/c|C D]] [[d#^p0001]] [[e#Part|E]] [[#^p2]] [[f\\|F]] `[[g]]`"),
            [("a", "", ""), ("b/c", "", "C D"), ("d", "^p0001", ""), ("e", "Part", "E"),
             ("", "^p2", ""), ("f", "", "F")],
        )


class FirstNames(unittest.TestCase):
    def test_a_link_to_a_person_that_shows_one_word(self):
        short = swap(sample.ACME, sample.SAM_LINK, "[[objects/people/sam-rivera|Sam]]")
        self.assertEqual(after(short), [(sample.ACME, "first-name-link")])

    def test_in_a_meetings_attendees(self):
        short = swap(sample.MEETING, "attendees: [\"%s\"]" % sample.SAM_LINK,
                     "attendees: [\"[[objects/people/sam-rivera|Sam]]\"]")
        self.assertEqual(after(short), [(sample.MEETING, "first-name-link")])

    def test_in_a_table_and_in_a_synthesis(self):
        short = swap(sample.MEETING, "sam-rivera\\|Sam Rivera]]", "sam-rivera\\|Sam]]")
        self.assertEqual(after(short), [(sample.MEETING, "first-name-link")])
        short = swap(sample.SYNTHESIS, sample.SAM_LINK, "[[objects/people/sam-rivera|Sam]]")
        self.assertEqual(after(short), [(sample.SYNTHESIS, "first-name-link")])

    def test_a_link_with_no_shown_words(self):
        # It shows its target. A path is not a name. A bare file name of one word is.
        bare = swap(sample.ACME, sample.SAM_LINK, "[[objects/people/sam-rivera]]")
        self.assertEqual(after(bare), [])
        files = sample.with_files(swap(sample.ACME, sample.SAM_LINK, "[[sam]]"))
        files["objects/people/sam.md"] = person("Sam Okafor", "Works at %s." % sample.ACME_LINK)
        self.assertEqual(found_in(files), [(sample.ACME, "first-name-link")])

    def test_one_word_for_something_that_is_not_a_person_is_fine(self):
        # Acme is one word, and every clean note links to it that way.
        self.assertIn(sample.ACME_LINK, sample.CLEAN[sample.SAM])
        self.assertEqual(found_in(sample.CLEAN), [])


class Unlinked(unittest.TestCase):
    ALONE = person("Lee Castillo", "Founder of a small lab.")

    def test_an_object_with_no_link_in_or_out(self):
        self.assertEqual(after({LEE: self.ALONE}), [(LEE, "unlinked")])

    def test_a_link_to_a_source_does_not_save_it(self):
        text = person("Lee Castillo", "Founder of a small lab. [[%s#^p0001]]" % sample.RECORDING)
        self.assertEqual(after({LEE: text}), [(LEE, "unlinked")])

    def test_a_link_from_a_source_does_not_save_it(self):
        source = sample.RECORDING + ".md"
        produced = sample.CLEAN[source].replace(
            "produced: [", "produced: [\"[[objects/people/lee-castillo]]\", "
        ).replace("one plan before", "one plan, said [[objects/people/lee-castillo|Lee Castillo]], before")
        self.assertEqual(after({LEE: self.ALONE, source: produced}), [(LEE, "unlinked")])

    def test_a_brief_or_a_root_file_does_not_save_it(self):
        link = "[[objects/people/lee-castillo|Lee Castillo]]"
        files = {
            LEE: self.ALONE,
            "signals/briefs/2026-11-13.md": "# Brief\n\n- 10:00 %s.\n" % link,
            "status.md": "# Status\n\n%s\n" % link,
            "AGENTS.md": "# Rules\n\nAsk %s.\n" % link,
        }
        self.assertEqual(after(files), [(LEE, "unlinked")])

    def test_a_link_out_saves_it(self):
        text = person("Lee Castillo", "Founder of a small lab. Knows %s." % sample.SAM_LINK)
        self.assertEqual(after({LEE: text}), [])

    def test_an_attendee_link_saves_the_person_and_the_meeting(self):
        meeting = "objects/meetings/2026-11-13-lab-visit.md"
        text = (
            "---\ntype: meeting\nprivate: false\ndate: 2026-11-13\n"
            "attendees: [\"[[objects/people/lee-castillo|Lee Castillo]]\"]\nsource:\n---\n"
            "# Lab visit\n\nA walk round the lab.\n\n## Decisions\n\n## Promises\n\n## Detail\n"
        )
        self.assertEqual(after({LEE: self.ALONE, meeting: text}), [])

    def test_a_link_from_the_owners_writing_saves_it(self):
        files = {LEE: self.ALONE,
                 "writing/2026-11-13.md": "Met [[objects/people/lee-castillo|Lee Castillo]].\n"}
        self.assertEqual(after(files), [])

    def test_a_link_from_a_synthesis_saves_it(self):
        files = {LEE: self.ALONE}
        files.update(swap(sample.SYNTHESIS, "## Sources",
                          "See [[objects/people/lee-castillo|Lee Castillo]].\n\n## Sources"))
        self.assertEqual(after(files), [])

    def test_a_link_to_itself_does_not_save_it(self):
        text = person("Lee Castillo", "See [[objects/people/lee-castillo|Lee Castillo]].")
        self.assertEqual(after({LEE: text}), [(LEE, "unlinked")])

    def test_the_measure_uses_the_same_rule(self):
        # One function, in `wd.graph`, behind the check and the measure.
        files = sample.with_files({LEE: self.ALONE})
        with tempfile.TemporaryDirectory() as folder:
            vault = sample.build(folder, files)
            report = measure.measure(vault, HOME)
            self.assertEqual(graph.unlinked_objects(notes.Vault(vault)), [LEE])
        self.assertEqual(report["unlinked_objects"], 1)
        self.assertEqual(report["examples"]["unlinked_objects"], [LEE])
        self.assertIn(("unlinked_objects", "Objects with no link in or out"), measure.LABELS)


class TheTestVault(unittest.TestCase):
    """The made-up test vault's known answers. See fixtures/README.md."""

    # Worked out by reading the notes, not by running the command.
    KNOWN = [
        ("objects/people/marcus.md", "missing-key"),
        ("objects/people/marcus.md", "unlinked"),
        ("objects/terms/reading-room.md", "wrong-type"),
        ("objects/terms/reading-room.md", "key-order"),
        ("objects/terms/reading-room.md", "name-not-heading"),
        ("objects/terms/reading-room.md", "name-not-unique"),
        ("objects/terms/reading-room.md", "unknown-section"),
        ("objects/terms/reading-room.md", "summary-too-long"),
        ("objects/terms/reading-room.md", "link-goes-nowhere"),
        ("objects/terms/reading-room.md", "first-name-link"),
        ("objects/meetings/2026-11-09-bluepeak-sync.md", "missing-section"),
        ("objects/meetings/2026-11-09-bluepeak-sync.md", "link-goes-nowhere"),
        ("signals/syntheses/2026-11-10-rollouts-go-wrong-at-handoffs.md", "link-goes-nowhere"),
    ]

    @classmethod
    def setUpClass(cls):
        cls.report = check.check(VAULT)
        cls.answers = json.loads((FIXTURES / "answers.json").read_text(encoding="utf-8"))["check"]

    def test_the_known_answers(self):
        self.assertEqual(self.report["by_kind"], self.answers["by_kind"])
        self.assertEqual(len(self.report["problems"]), self.answers["problems"])

    def test_the_answers_cover_every_kind_and_add_up(self):
        self.assertEqual(list(self.answers["by_kind"]), [kind for kind, _ in check.KINDS])
        self.assertEqual(sum(self.answers["by_kind"].values()), self.answers["problems"])
        # The test vault has an example of every kind.
        self.assertTrue(all(count > 0 for count in self.answers["by_kind"].values()))

    def test_each_flaw_is_found_on_the_note_that_carries_it(self):
        self.assertEqual(
            [(found["note"], found["kind"]) for found in self.report["problems"]], self.KNOWN)

    def test_every_problem_is_one_plain_sentence(self):
        for found in self.report["problems"]:
            self.assertEqual(sorted(found), ["kind", "note", "sentence"])
            self.assertTrue(found["sentence"].endswith("."), found)
            self.assertNotIn("\n", found["sentence"])


class Command(unittest.TestCase):
    def run_wd(self, arguments, state):
        environment = dict(os.environ, HOME=str(HOME), WD_STATE_DIR=str(state))
        return subprocess.run(
            [sys.executable, str(WD)] + [str(argument) for argument in arguments],
            env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True,
        )

    def test_a_clean_vault_passes_and_nothing_in_it_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = sample.build(Path(folder) / "vault", sample.CLEAN)
            state = Path(folder) / "state"
            before, problems = stage0.snapshot(vault)
            self.assertEqual(problems, [])
            result = self.run_wd(["check", vault], state)
            after_run, _ = stage0.snapshot(vault)
            self.assertEqual(result.returncode, cli.OK, result.stdout + result.stderr)
            self.assertEqual(stage0.changed_files(before, after_run), [])
            self.assertEqual(sorted(path.name for path in state.iterdir()), ["check.json"])
            report = json.loads((state / "check.json").read_text(encoding="utf-8"))
            self.assertEqual(stage0.stamp_problems(report, vault), [])
        self.assertEqual(report["problems"], [])
        self.assertIn("No problems.", result.stdout)
        self.assertIn("Saved to", result.stdout)

    def test_the_test_vault_fails_with_a_table_and_is_left_alone(self):
        with tempfile.TemporaryDirectory() as state:
            before, _ = stage0.snapshot(VAULT)
            result = self.run_wd(["check", VAULT], state)
            after_run, _ = stage0.snapshot(VAULT)
            report = json.loads((Path(state) / "check.json").read_text(encoding="utf-8"))
        self.assertEqual(result.returncode, cli.FAILED)
        self.assertEqual(stage0.changed_files(before, after_run), [])
        self.assertEqual(stage1.check_report_problems(report), [])
        self.assertEqual(len(report["problems"]), 13)
        self.assertRegex(result.stdout, r"(?m)^13 problems$")
        self.assertRegex(result.stdout, r"(?m)^  A link goes nowhere\s+3$")
        self.assertIn("objects/people/marcus.md\n  It is missing the keys name, aliases and private.",
                      result.stdout)

    def test_a_long_list_is_cut_short_on_the_screen_and_whole_in_the_report(self):
        files = dict(sample.CLEAN)
        for number in range(check.PRINTED + 4):
            files["objects/people/person-%02d.md" % number] = person(
                "Person Number%02d" % number, "Nobody links here.")
        with tempfile.TemporaryDirectory() as folder:
            vault = sample.build(Path(folder) / "vault", files)
            result = self.run_wd(["check", vault], Path(folder) / "state")
            report = json.loads((Path(folder) / "state" / "check.json").read_text(encoding="utf-8"))
        self.assertEqual(len(report["problems"]), check.PRINTED + 4)
        self.assertIn("And 4 more.", result.stdout)

    def test_it_refuses_to_keep_its_state_inside_the_vault(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = sample.build(folder, sample.CLEAN)
            before, _ = stage0.snapshot(vault)
            result = self.run_wd(["check", vault], vault / "state")
            after_run, _ = stage0.snapshot(vault)
        self.assertEqual(result.returncode, cli.FAILED)
        self.assertIn("inside the vault", result.stderr)
        self.assertEqual(stage0.changed_files(before, after_run), [])

    def test_no_vault_a_missing_vault_and_too_much_fail(self):
        for arguments, code in (
            (["check"], cli.USAGE),
            (["check", "a", "b"], cli.USAGE),
            (["check", "--apply"], cli.USAGE),
            (["check", "/no/such/vault"], cli.FAILED),
        ):
            out, err = io.StringIO(), io.StringIO()
            self.assertEqual(cli.main(arguments, out=out, err=err), code, arguments)
            self.assertEqual(out.getvalue(), "")
            self.assertTrue(err.getvalue().strip())

    @unittest.skipIf(os.geteuid() == 0, "the administrator can read every file")
    def test_a_note_that_cannot_be_read_is_a_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = sample.build(Path(folder) / "vault", sample.CLEAN)
            locked = vault / sample.CONCEPT
            locked.chmod(0)
            try:
                result = self.run_wd(["check", vault], Path(folder) / "state")
            finally:
                locked.chmod(0o600)
        self.assertEqual(result.returncode, cli.FAILED)
        self.assertIn("could not be read", result.stderr)


if __name__ == "__main__":
    unittest.main()
