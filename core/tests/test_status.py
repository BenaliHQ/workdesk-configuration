"""`wd status`: the status page, on a tiny vault built for the test."""

import datetime
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
HOME = FIXTURES / "home"
for folder in (CORE, TESTS):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import sample_vault as sample  # noqa: E402
import stage0_finish as stage0  # noqa: E402
import stage1_finish as stage1  # noqa: E402
from wd import check, cli, measure, places, status  # noqa: E402

LIMIT = json.loads((CORE / "budgets.json").read_text(encoding="utf-8"))[
    "Words loaded into a session, everything counted"
]
WHEN = datetime.datetime(2026, 11, 15, 7, 5, 9)
LEE = "objects/people/lee-castillo.md"

# The made-up home loads 42 words in Claude Code and 15 in Codex when a
# session starts in an empty folder (counted by hand in test_measure).
# The clean vault adds, in Claude Code: CLAUDE.md, 1 word, the 10 words
# of AGENTS.md it imports, and a skill description of 7. In Codex:
# AGENTS.md, 10, and the same description, 7.
CLAUDE_LINE = ("- Claude Code: 60 words in all. 18 from the vault and 42 from outside it. "
               "Under the limit.")
CODEX_LINE = "- Codex: 32 words in all. 17 from the vault and 15 from outside it. Under the limit."


def built(files, home=HOME):
    """The page for a vault made of these files."""
    with tempfile.TemporaryDirectory() as folder:
        text, unreadable = status.build(sample.build(folder, files), home, written=WHEN)
    assert unreadable == []
    return text


def run_wd(arguments, state=None, home=HOME):
    environment = dict(os.environ, HOME=str(home))
    if state is not None:
        environment["WD_STATE_DIR"] = str(state)
    return subprocess.run(
        [sys.executable, str(WD)] + [str(argument) for argument in arguments],
        env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True,
    )


def without_the_time(text):
    return [line for line in text.splitlines() if not line.startswith(status.WRITTEN)]


class ThePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = built(sample.CLEAN)
        cls.lines = cls.page.splitlines()

    def test_it_says_at_the_top_that_a_program_writes_it(self):
        self.assertEqual(self.lines[0], "# Status")
        self.assertIn("written by a program", self.lines[2])
        self.assertIn("Do not edit it by hand", self.lines[2])

    def test_it_says_when_it_was_written(self):
        self.assertIn("Written on 2026-11-15 at 07:05:09.", self.lines)

    def test_it_has_no_opening_block_and_no_links(self):
        # So it never shows in the graph.
        self.assertFalse(self.page.startswith("---"))
        self.assertNotIn("[[", self.page)
        self.assertNotIn("](", self.page)

    def test_the_notes_in_each_home(self):
        homes = [home for _, home in places.OBJECT_HOMES] + places.SIGNAL_HOMES + places.SOURCE_HOMES
        counts = {home: 1 for _, home in places.OBJECT_HOMES}
        counts.update({"signals/briefs": 0, "signals/syntheses": 1, "sources/recordings": 1,
                       "sources/links": 0, "sources/sessions": 0, "sources/captures": 0})
        start = self.lines.index("## Notes in each home") + 2
        self.assertEqual(
            self.lines[start:start + len(homes)],
            ["- %s: %d" % (home, counts[home]) for home in homes],
        )

    def test_no_problems(self):
        self.assertIn("The check found 0 problems. It looked at 8 objects and 1 synthesis.", self.lines)
        self.assertNotIn("By kind:", self.lines)

    def test_the_words_a_session_loads_split_in_two(self):
        self.assertIn(CLAUDE_LINE, self.lines)
        self.assertIn(CODEX_LINE, self.lines)

    def test_the_limit_is_the_contracts(self):
        self.assertEqual(status.session_limit(), LIMIT)
        self.assertEqual(LIMIT, 3000)
        self.assertIn("The limit is 3,000 words, everything counted.", self.lines)

    def test_it_says_what_outside_means(self):
        self.assertIn("starts in an empty folder", self.page)

    def test_the_page_meets_the_finish_test(self):
        # The split the finish test wants: what the same home loads in an
        # empty folder is "outside", and the rest is the vault's.
        with tempfile.TemporaryDirectory() as folder:
            vault = sample.build(Path(folder) / "vault", sample.CLEAN)
            empty = Path(folder) / "empty"
            empty.mkdir()
            inside = measure.measure(vault, HOME)
            outside = measure.measure(empty, HOME)
            found = check.check(vault)
        load = {
            runtime: {
                "vault": inside["session_load"][runtime] - outside["session_load"][runtime],
                "outside": outside["session_load"][runtime],
            }
            for runtime, _ in stage1.RUNTIMES
        }
        self.assertEqual(load, {"claude-code": {"vault": 18, "outside": 42},
                                "codex": {"vault": 17, "outside": 15}})
        self.assertEqual(
            stage1.status_problems(self.page, inside["notes"], len(found["problems"]), load), [])

    def test_the_same_vault_gives_the_same_page(self):
        self.assertEqual(built(sample.CLEAN), self.page)


class WithProblems(unittest.TestCase):
    # A person whose heading holds words that must not reach the page.
    SECRET = (
        "---\ntype: person\nname: Lee Castillo\naliases: []\nprivate: true\n---\n"
        "# Quietly Leaving Soon\n\nTalks to [[objects/people/sam-rivera|Sam]] about [[moving-away]].\n"
    )

    def test_the_count_by_kind_and_the_first_few(self):
        page = built(sample.with_files({LEE: self.SECRET})).splitlines()
        self.assertIn("The check found 3 problems. It looked at 9 objects and 1 synthesis.", page)
        start = page.index("By kind:")
        self.assertEqual(page[start:start + 11], [
            "By kind:",
            "",
            "- The name is not the first heading: 1",
            "- A link goes nowhere: 1",
            "- A link to a person shows one word: 1",
            "",
            "All of them:",
            "",
            "- `%s`: The name is not the first heading" % LEE,
            "- `%s`: A link goes nowhere" % LEE,
            "- `%s`: A link to a person shows one word" % LEE,
        ])

    def test_nothing_a_note_says_reaches_the_page(self):
        # The check's sentences quote the note. The page shows the note's
        # path and the kind of problem, and no more.
        page = built(sample.with_files({LEE: self.SECRET}))
        for words in ("Quietly", "Leaving", "moving-away", "Talks to", "Sam Rivera", "Acme"):
            self.assertNotIn(words, page)
        for line in page.splitlines():
            if line.startswith("- `"):
                self.assertRegex(line, r"^- `[a-z0-9/.-]+\.md`: [A-Za-z ]+$")

    def test_only_the_first_few_are_listed(self):
        files = dict(sample.CLEAN)
        for number in range(7):
            files["objects/people/person-%d.md" % number] = (
                "---\ntype: person\nname: Person Number%d\naliases: []\nprivate: false\n---\n"
                "# Person Number%d\n\nNobody links here.\n" % (number, number)
            )
        page = built(files).splitlines()
        self.assertIn("The check found 7 problems. It looked at 15 objects and 1 synthesis.", page)
        self.assertIn("- An object has no link in or out: 7", page)
        self.assertIn("The first %d:" % status.FIRST_FEW, page)
        self.assertEqual(len([line for line in page if line.startswith("- `")]), status.FIRST_FEW)
        self.assertIn("Run `wd check` to read each one in a sentence.", page)

    def test_the_status_page_itself_is_not_a_note_that_is_checked(self):
        files = sample.with_files({"status.md": "# Status\n\nAn old page. [[gone]]\n"})
        self.assertEqual(without_the_time(built(files)), without_the_time(built(sample.CLEAN)))


class TheLimit(unittest.TestCase):
    def test_under_at_and_over(self):
        def line(total):
            return status.load_line("Codex", {"total": total, "vault": 0, "outside": total}, 3000)
        self.assertTrue(line(2999).endswith(" Under the limit."))
        self.assertTrue(line(3000).endswith(" Under the limit."))
        self.assertTrue(line(3001).endswith(" Over the limit by 1."))
        self.assertEqual(
            status.load_line("Claude Code", {"total": 4403, "vault": 28, "outside": 4375}, 3000),
            "- Claude Code: 4,403 words in all. 28 from the vault and 4,375 from outside it. "
            "Over the limit by 1,403.",
        )

    def page(self, load):
        report = {"problems": [], "checked": {"objects": 1, "syntheses": 0}, "by_kind": {}}
        return status.page(report, {"objects/people": 0}, load, 3000, WHEN)

    def test_it_says_when_outside_alone_is_over_the_limit(self):
        page = self.page({
            "claude-code": {"total": 4403, "vault": 28, "outside": 4375},
            "codex": {"total": 1720, "vault": 28, "outside": 1692},
        })
        self.assertIn(
            "In Claude Code the words from outside the vault are over the limit "
            "before the vault adds anything.", page)
        self.assertNotIn("In Codex", page)

    def test_a_vault_that_switches_plugins_off_can_be_below_zero(self):
        page = self.page({
            "claude-code": {"total": 2403, "vault": -1972, "outside": 4375},
            "codex": {"total": 1720, "vault": 28, "outside": 1692},
        })
        line = next(line for line in page.splitlines() if line.startswith("- Claude Code"))
        self.assertIn("-1,972 from the vault", line)
        self.assertTrue(line.endswith("Under the limit."))
        # The finish test finds the number written this way.
        self.assertTrue(stage0.has_number(line, -1972))
        self.assertIn("In Claude Code the vault's number is below zero", page)

    def test_the_vaults_settings_change_the_number(self):
        # The made-up home has one plugin switched on, with a skill
        # description of 7 words. The vault switches it off, so the
        # vault's 18 words become 11. Written by Python, in a scratch folder.
        off = json.dumps({"enabledPlugins": {"extras@made-up": False}})
        page = built(sample.with_files({".claude/settings.json": off}))
        self.assertIn(
            "- Claude Code: 53 words in all. 11 from the vault and 42 from outside it. "
            "Under the limit.", page.splitlines())
        self.assertIn(CODEX_LINE, page.splitlines())

    def test_a_budget_file_without_the_limit_is_an_error(self):
        kept = status.BUDGETS
        with tempfile.TemporaryDirectory() as folder:
            status.BUDGETS = Path(folder) / "budgets.json"
            try:
                self.assertRaises(status.StatusError, status.session_limit)
                status.BUDGETS.write_text("{\"%s\": true}" % status.SESSION_LIMIT, encoding="utf-8")
                self.assertRaises(status.StatusError, status.session_limit)
            finally:
                status.BUDGETS = kept


class Command(unittest.TestCase):
    def vault(self, folder, files=None):
        return sample.build(Path(folder) / "vault", files or sample.CLEAN)

    def test_a_dry_run_prints_the_page_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = self.vault(folder)
            before, _ = stage0.snapshot(vault)
            result = run_wd(["status", vault, "--dry-run"], Path(folder) / "state")
            after, _ = stage0.snapshot(vault)
            self.assertEqual(stage0.changed_files(before, after), [])
            self.assertFalse((Path(folder) / "state").exists())
        self.assertEqual(result.returncode, cli.OK, result.stderr)
        self.assertTrue(result.stdout.startswith("# Status\n"))
        self.assertIn(CLAUDE_LINE, result.stdout.splitlines())
        self.assertIn("Nothing was written", result.stderr)

    def test_apply_writes_the_page_and_nothing_else(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = self.vault(folder)
            before, _ = stage0.snapshot(vault)
            result = run_wd(["status", "--apply", vault], Path(folder) / "state")
            after, _ = stage0.snapshot(vault)
            self.assertEqual(result.returncode, cli.OK, result.stderr)
            self.assertEqual(stage0.changed_files(before, after), ["status.md"])
            # No temporary file is left behind, and no machine state is kept.
            self.assertEqual(
                sorted(path.name for path in vault.iterdir() if path.is_file()),
                ["AGENTS.md", "CLAUDE.md", "status.md"],
            )
            self.assertFalse((Path(folder) / "state").exists())
            page = (vault / "status.md").read_text(encoding="utf-8")
            self.assertIn("Wrote %s" % (vault.resolve() / "status.md"), result.stdout)
        self.assertIn(CLAUDE_LINE, page.splitlines())
        self.assertTrue(page.endswith("\n"))

    def test_a_second_run_changes_only_the_time(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = self.vault(folder)
            run_wd(["status", vault, "--apply"])
            first = (vault / "status.md").read_text(encoding="utf-8")
            # An old time, so the second run is seen to replace the line.
            (vault / "status.md").write_text(
                first.replace(status.WRITTEN + "20", status.WRITTEN + "19"), encoding="utf-8")
            result = run_wd(["status", vault, "--apply"])
            second = (vault / "status.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, cli.OK, result.stderr)
        self.assertEqual(without_the_time(second), without_the_time(first))
        self.assertEqual(len(first.splitlines()) - len(without_the_time(first)), 1)
        self.assertNotIn(status.WRITTEN + "19", second)

    def test_it_never_writes_under_the_owners_writing(self):
        files = sample.with_files({"writing/2026-11-13.md": "Met %s today.\n" % sample.SAM_LINK})
        with tempfile.TemporaryDirectory() as folder:
            vault = self.vault(folder, files)
            before, _ = stage0.snapshot(vault / "writing")
            run_wd(["status", vault, "--apply"])
            after, _ = stage0.snapshot(vault / "writing")
        self.assertEqual(stage0.changed_files(before, after), [])

    def test_a_vault_with_problems_still_gets_its_page(self):
        # The page is where the problems are read, so writing it is not a failure.
        files = sample.with_files({LEE: WithProblems.SECRET})
        with tempfile.TemporaryDirectory() as folder:
            vault = self.vault(folder, files)
            result = run_wd(["status", vault, "--apply"])
            page = (vault / "status.md").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, cli.OK, result.stderr)
        self.assertIn("The check found 3 problems.", page)

    def test_it_wants_one_vault_and_one_of_the_two_ways(self):
        for arguments in (
            ["status"], ["status", "vault"], ["status", "--apply"],
            ["status", "vault", "--dry-run", "--apply"], ["status", "a", "b", "--apply"],
            ["status", "vault", "--apply", "--force"],
        ):
            out, err = io.StringIO(), io.StringIO()
            self.assertEqual(cli.main(arguments, out=out, err=err), cli.USAGE, arguments)
            self.assertEqual(out.getvalue(), "")
            self.assertIn("usage: wd status <vault> --dry-run", err.getvalue())

    def test_a_missing_vault_fails(self):
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(
            cli.main(["status", "/no/such/vault", "--apply"], out=out, err=err), cli.FAILED)
        self.assertIn("there is no vault", err.getvalue())

    def test_apply_refuses_a_folder_that_is_not_a_vault(self):
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / "notes.md").write_text("Not a vault.\n", encoding="utf-8")
            result = run_wd(["status", folder, "--apply"])
            self.assertEqual(sorted(os.listdir(folder)), ["notes.md"])
        self.assertEqual(result.returncode, cli.FAILED)
        self.assertIn("not a Workdesk vault", result.stderr)

    def test_apply_leaves_alone_a_page_that_is_not_a_plain_file(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = self.vault(folder)
            (vault / "status.md").mkdir()
            result = run_wd(["status", vault, "--apply"])
            self.assertTrue((vault / "status.md").is_dir())
        self.assertEqual(result.returncode, cli.FAILED)
        self.assertIn("not a plain file", result.stderr)

    def test_a_page_that_changed_while_it_ran_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = self.vault(folder)
            (vault / "status.md").write_text("Written by someone else.\n", encoding="utf-8")
            with self.assertRaises(status.StatusError) as raised:
                status.write(vault, "# Status\n", before=b"What was there at the start.\n")
            self.assertIn("changed while this ran", str(raised.exception))
            self.assertEqual(
                (vault / "status.md").read_text(encoding="utf-8"), "Written by someone else.\n")
            self.assertEqual(sorted(path.name for path in vault.glob(".status*")), [])
            # With nothing changed it goes in, and with no page there at all.
            status.write(vault, "# Status\n", before=b"Written by someone else.\n")
            self.assertEqual((vault / "status.md").read_text(encoding="utf-8"), "# Status\n")
            (vault / "status.md").unlink()
            status.write(vault, "# Status\n", before=None)
            self.assertTrue((vault / "status.md").is_file())

    @unittest.skipIf(os.geteuid() == 0, "the administrator can read every file")
    def test_a_note_that_cannot_be_read_is_a_failure_and_nothing_is_written(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = self.vault(folder)
            locked = vault / sample.CONCEPT
            locked.chmod(0)
            try:
                result = run_wd(["status", vault, "--apply"])
            finally:
                locked.chmod(0o600)
            self.assertFalse((vault / "status.md").exists())
        self.assertEqual(result.returncode, cli.FAILED)
        self.assertIn("could not be read", result.stderr)


class TheFinishTestForS14(stage1.S14CheckAndStatus):
    """The S1.4 checks of the stage 1 finish test, run here as they are written.

    They make their vault with `wd init --samples`, so every ordinary
    test run also proves that the samples pass the check, that the
    check finds each kind of wrong note, and that the status page is
    really written again over an old one.
    """


if __name__ == "__main__":
    unittest.main()
