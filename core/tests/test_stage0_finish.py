"""The stage 0 finish test's own checks, tried on right and wrong inputs.

The finish test cannot pass until stage 0 is built. These tests make
sure that when it does pass, it means something: each one feeds a check
an input that must not get through.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

import stage0_finish as finish  # noqa: E402

MEASURE = {
    "vault": "/made-up/vault",
    "run_at": "2026-11-12T07:00:00-06:00",
    "notes": {"objects/people": 1204, "objects/meetings": 31},
    "broken_links": 17,
    "unlinked_objects": 9,
    "people_without_full_name": 4,
    "meetings_with_missing_source": 2,
    "sources_unprocessed": 80,
    "session_load": {"claude-code": 28110, "codex": 6050},
}

SCORE = {
    "vault": "/made-up/vault",
    "run_at": "2026-11-12T07:00:00-06:00",
    "by_type": {
        "person": {"correct": 990, "wrong": 5, "missed": 5},
        "company": {"correct": 198, "wrong": 0, "missed": 2},
    },
    "right_rate": 1188 / 1193.0,
    "miss_rate": 7 / 1200.0,
    "scratch": "/made-up/state/scratch",
}

GOOD_LOG = """
Some words before.

- S0.5 (a): verified. Evidence: opened the link and it showed the turn.
- S0.5 (b) Claude Code: verified. Evidence: ran it unattended three times.
- S0.5 (b) Codex: failed. Evidence: it stopped to ask for a login. Consequence: Codex is not used for scheduled steps.
- S0.5 (c) Claude Code: verified. Evidence: the check fired after a write.
- S0.5 (c) Codex: worked around. Evidence: nothing fires after a write. Consequence: the check relies on session end and the nightly run.
- S0.5 (d): failed. Evidence: a clean account had no Python at all. Consequence: logged for stage 6, which must supply it.
- S0.5 (e): verified. Evidence: both edits were kept in one note.
"""


def changed(document, **changes):
    copy = dict(document)
    copy.update(changes)
    return copy


class Snapshot(unittest.TestCase):
    def test_a_changed_file_is_found(self):
        with tempfile.TemporaryDirectory() as folder:
            note = Path(folder) / "note.md"
            note.write_text("one", encoding="utf-8")
            before, problems = finish.snapshot(folder)
            self.assertEqual(problems, [])
            note.write_text("two", encoding="utf-8")
            (Path(folder) / "new.md").write_text("new", encoding="utf-8")
            after, _ = finish.snapshot(folder)
        self.assertEqual(finish.changed_files(before, after), ["new.md", "note.md"])

    def test_the_git_folder_and_the_window_layout_are_left_out(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in (".git/index", ".obsidian/workspace.json", ".obsidian/app.json"):
                path = Path(folder) / name
                path.parent.mkdir(exist_ok=True)
                path.write_text("x", encoding="utf-8")
            found, _ = finish.snapshot(folder)
        self.assertEqual(sorted(found), [".obsidian/app.json"])

    @unittest.skipIf(os.geteuid() == 0, "the administrator can read every file")
    def test_a_file_that_cannot_be_read_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            locked = Path(folder) / "locked.md"
            locked.write_text("x", encoding="utf-8")
            locked.chmod(0)
            try:
                found, problems = finish.snapshot(folder)
            finally:
                locked.chmod(0o600)
        self.assertNotIn("locked.md", found)
        self.assertEqual(len(problems), 1)
        self.assertIn("locked.md", problems[0])

    @unittest.skipIf(os.geteuid() == 0, "the administrator can open every folder")
    def test_a_folder_that_cannot_be_opened_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            locked = Path(folder) / "locked"
            locked.mkdir()
            locked.chmod(0)
            try:
                _, problems = finish.snapshot(folder)
            finally:
                locked.chmod(0o700)
        self.assertEqual(len(problems), 1)


class Measure(unittest.TestCase):
    def test_a_full_report_gets_through(self):
        self.assertEqual(finish.measure_problems(MEASURE), [])

    def test_empty_groups_do_not_get_through(self):
        empty = {name: {} for name in finish.MEASURES}
        self.assertEqual(len(finish.measure_problems(empty)), 8)

    def test_true_and_negative_numbers_are_not_counts(self):
        self.assertTrue(finish.measure_problems(changed(MEASURE, broken_links=True)))
        self.assertTrue(finish.measure_problems(changed(MEASURE, broken_links=-1)))
        self.assertTrue(finish.measure_problems(changed(MEASURE, notes={"objects/people": "many"})))

    def test_session_load_needs_both_runtimes(self):
        one = changed(MEASURE, session_load={"claude-code": 28110})
        self.assertEqual(finish.measure_problems(one), ["session_load.codex: not a count"])

    def test_the_report_names_its_vault_and_time(self):
        self.assertEqual(finish.stamp_problems(MEASURE, "/made-up/vault"), [])
        self.assertTrue(finish.stamp_problems(MEASURE, "/another/vault"))
        self.assertTrue(finish.stamp_problems(changed(MEASURE, run_at="yesterday"), "/made-up/vault"))
        self.assertEqual(len(finish.stamp_problems({}, "/made-up/vault")), 2)


class Score(unittest.TestCase):
    def test_a_full_report_gets_through(self):
        self.assertEqual(finish.score_problems(SCORE), [])

    def test_rates_that_contradict_the_counts_do_not_get_through(self):
        report = changed(
            SCORE,
            by_type={"person": {"correct": 0, "wrong": 0, "missed": 100}},
            right_rate=1, miss_rate=0,
        )
        self.assertTrue(finish.score_problems(report))
        report = changed(SCORE, right_rate=1.0)
        self.assertEqual(len(finish.score_problems(report)), 1)

    def test_true_and_negative_numbers_are_not_counts(self):
        for value in (True, -1, 1.5, None):
            report = changed(
                SCORE, by_type={"person": {"correct": value, "wrong": 0, "missed": 0}}
            )
            self.assertTrue(finish.score_problems(report), value)

    def test_nothing_scored_cannot_pass_the_gate(self):
        nothing = {"person": {"correct": 0, "wrong": 0, "missed": 0}}
        self.assertIsNotNone(finish.rates(nothing)[2])
        self.assertTrue(finish.score_problems(changed(SCORE, by_type=nothing)))
        self.assertTrue(finish.score_problems(changed(SCORE, by_type={})))

    def test_the_two_rates(self):
        right, miss, why_not = finish.rates(SCORE["by_type"])
        self.assertIsNone(why_not)
        self.assertAlmostEqual(right, 1188 / 1193.0)
        self.assertAlmostEqual(miss, 7 / 1200.0)
        # A wrong link counts against being right, not as a miss.
        right, miss, _ = finish.rates({"person": {"correct": 98, "wrong": 2, "missed": 0}})
        self.assertLess(right, finish.GATE_RIGHT_RATE)
        self.assertEqual(miss, 0)


class Case(unittest.TestCase):
    GOOD = {
        "exists": {
            "objects": ["objects/people/sam-rivera"],
            "links": [{"from": "objects/meetings/2026-11-10-acme", "to": "objects/people/sam-rivera"}],
            "history": [],
        },
        "absent": {"objects": [], "links": [], "history": ["Sam Rivera | COO"]},
    }

    def test_a_full_case_gets_through(self):
        self.assertEqual(finish.case_problems(self.GOOD), [])

    def test_true_and_false_do_not_get_through(self):
        self.assertEqual(len(finish.case_problems({"exists": True, "absent": False})), 2)

    def test_a_case_that_lists_nothing_does_not_get_through(self):
        empty = {part: {kind: [] for kind in finish.CASE_KINDS} for part in finish.CASE_PARTS}
        self.assertEqual(
            finish.case_problems(empty), ["lists nothing that must exist or be absent"]
        )

    def test_every_list_must_be_there_and_say_something(self):
        missing = {"exists": {"objects": ["x"]}, "absent": self.GOOD["absent"]}
        self.assertEqual(len(finish.case_problems(missing)), 2)
        blank = {"exists": {"objects": [" "], "links": [{}], "history": []},
                 "absent": self.GOOD["absent"]}
        self.assertEqual(len(finish.case_problems(blank)), 2)
        extra = {"exists": dict(self.GOOD["exists"], tasks=[]), "absent": self.GOOD["absent"]}
        self.assertEqual(len(finish.case_problems(extra)), 1)


class FiveChecks(unittest.TestCase):
    def test_a_full_record_gets_through(self):
        self.assertEqual(finish.s05_problems(GOOD_LOG), [])

    def test_checks_a_and_e_are_not_asked_for_here(self):
        # They moved to stage 1, with the operator's approval of 2026-11-15.
        self.assertEqual(finish.S05_CHECKS, ["b", "c", "d"])
        log = "\n".join(
            line for line in GOOD_LOG.splitlines()
            if "S0.5 (a)" not in line and "S0.5 (e)" not in line
        )
        self.assertEqual(finish.s05_problems(log), [])
        # A failed (a) or (e) does not fail stage 0 either.
        self.assertEqual(finish.s05_problems(log + "\n- S0.5 (a): failed.\n"), [])

    def test_five_bare_failures_do_not_get_through(self):
        bare = "\n".join("S0.5 (%s) failed" % letter for letter in "abcde")
        self.assertEqual(len(finish.s05_problems(bare)), 5)
        bare = "\n".join("- S0.5 (%s): failed." % letter for letter in "abcde")
        self.assertTrue(finish.s05_problems(bare))

    def test_a_mention_in_a_sentence_is_not_a_record(self):
        prose = "The builder will log S0.5 (d): verified. Evidence: one two three."
        self.assertIn("S0.5 (d): no outcome logged", finish.s05_problems(prose))

    def test_each_runtime_needs_its_own_line(self):
        log = GOOD_LOG.replace("- S0.5 (b) Codex: failed.", "- S0.5 (x) Codex: failed.")
        self.assertEqual(finish.s05_problems(log), ["S0.5 (b) Codex: no outcome logged"])

    def test_a_failure_needs_its_consequence(self):
        log = GOOD_LOG.replace(" Consequence: logged for stage 6, which must supply it.", "")
        self.assertEqual(
            finish.s05_problems(log), ["S0.5 (d): failed, with no consequence given"]
        )

    def test_an_outcome_needs_evidence(self):
        log = GOOD_LOG.replace("Evidence: the check fired after a write.", "Evidence: yes.")
        self.assertEqual(finish.s05_problems(log), ["S0.5 (c) Claude Code: no evidence given"])

    def test_both_runtimes_failing_stops_the_stage(self):
        log = GOOD_LOG.replace(
            "- S0.5 (b) Claude Code: verified. Evidence: ran it unattended three times.",
            "- S0.5 (b) Claude Code: failed. Evidence: it asked for a login. "
            "Consequence: not used for scheduled steps.",
        )
        problems = finish.s05_problems(log)
        self.assertEqual(len(problems), 1)
        self.assertIn("stop and ask the operator", problems[0])

    def test_a_check_run_again_counts_by_its_last_line(self):
        log = GOOD_LOG + "- S0.5 (d): verified. Evidence: a second clean account had it.\n"
        self.assertEqual(finish.s05_problems(log), [])


class Scorecard(unittest.TestCase):
    GOOD = """# Stage 0 scorecard

Measured 2026-11-12.

People notes: 1,204. Meeting notes: 31. Broken links: 17. Objects nothing
links to: 9. People without a full name: 4. Meetings with a missing
source: 2. Sources not processed: 80.

Session load: 28,110 words in Claude Code, 6,050 in Codex.

People: 990 right, 5 wrong, 5 missed. Companies: 198 right, 0 wrong, 2 missed.
"""

    def test_a_full_scorecard_gets_through(self):
        self.assertEqual(finish.scorecard_problems(self.GOOD, MEASURE, SCORE), [])

    def test_a_placeholder_does_not_get_through(self):
        self.assertGreater(len(finish.scorecard_problems("TODO", MEASURE, SCORE)), 10)

    def test_a_missing_number_is_named(self):
        text = self.GOOD.replace("28,110", "about 28 thousand")
        self.assertEqual(
            finish.scorecard_problems(text, MEASURE, SCORE),
            ["session load, claude-code (28110)"],
        )

    def test_a_number_inside_a_longer_number_does_not_count(self):
        self.assertTrue(finish.has_number("There are 1,204 notes.", 1204))
        self.assertTrue(finish.has_number("There are 1204 notes.", 1204))
        self.assertFalse(finish.has_number("There are 11,204 notes.", 1204))
        self.assertFalse(finish.has_number("A rate of 0.17.", 17))
        self.assertFalse(finish.has_number("A rate of 17.5.", 17))
        self.assertTrue(finish.has_number("Broken links: 17.", 17))

    def test_the_date_of_the_run_must_be_shown(self):
        text = self.GOOD.replace("2026-11-12", "last week")
        self.assertEqual(
            finish.scorecard_problems(text, MEASURE, SCORE),
            ["the date of the run (2026-11-12)"],
        )


if __name__ == "__main__":
    unittest.main()
