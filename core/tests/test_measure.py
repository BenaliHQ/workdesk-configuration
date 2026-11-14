"""`wd check --measure`: each count, on a small vault made for the test."""

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
HOME = TESTS / "fixtures" / "home"
for folder in (CORE, TESTS):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import stage0_finish as finish  # noqa: E402
from wd import cli, measure, notes, places  # noqa: E402

SOURCE = "---\ntype: source\nprocessed: %s\n---\n%s\n"

VAULT = {
    "atlas/people/sam-rivera.md":
        "# Sam Rivera\n\nWorks with [[atlas/companies/acme|Acme]]. "
        "Met in [[2026-11-10-acme-kickoff]]. See [[missing-note]].\n",
    "atlas/people/nick.md": "# Nick\n\nNo last name known.\n",
    "atlas/people/index.md": "# People\n\n[[nowhere]]\n",
    "atlas/companies/acme.md":
        "# Acme\n\nA made-up company. ![[logo.png]] and `[[not-a-link]]`\n\n"
        "```\n[[also-not-a-link]]\n```\n",
    "attachments/logo.png": "not really a picture",
    "atlas/meetings/2026-11-10-acme-kickoff.md":
        "---\ntranscript: \"[[system/transcripts/2026-11-10-acme-kickoff]]\"\n---\n"
        "# Acme kickoff\n\nWith [[atlas/people/sam-rivera|Sam Rivera]].\n\n"
        "| who | where |\n|---|---|\n| Sam | [[atlas/companies/acme\\|Acme]] |\n",
    "atlas/meetings/2026-11-11-lost.md":
        "---\ntranscript: \"[[system/transcripts/2026-11-11-gone]]\"\n---\n# Lost\n",
    "atlas/meetings/2026-11-12-web.md":
        "---\nsource: https://example.com/call\ntranscript:\n---\n# Web\n",
    "atlas/meetings/2026-11-13-plain.md":
        "---\nsource: system/transcripts/2026-11-13-nope.md\n---\n# Plain\n",
    "atlas/decisions/2026-11-10-price.md":
        "# Price\n\nDecided in [[2026-11-10-acme-kickoff#Decisions]].\n",
    "gtd/projects/alpha/brief.md": "# Alpha Brief\n\nFor [[Acme]].\n",
    "gtd/projects/_archive/brief.md": "# Archived Brief\n",
    "gtd/projects/_archive/old/brief.md": "# Old Brief\n",
    "atlas/clients/acme/brief.md": "# A client brief is not a project\n",
    "atlas/clients/acme/projects/site/brief.md": "# Site Brief\n",
    "intel/syntheses/2026-11-12-pricing.md":
        "About [[atlas/people/sam-rivera]] and [[ghost]].\n",
    "intel/concepts/bespoke-systems.md": "# Bespoke systems\n",
    "system/transcripts/2026-11-10-acme-kickoff.md":
        SOURCE % ("true", "Sam: hello [[unknown-in-a-source]]"),
    "system/intake/a.md": SOURCE % ("false", "Dropped today."),
    "system/bookmarks/b.md": SOURCE % ("false", "A saved link."),
    "system/bookmarks/c.md": SOURCE % ("true", "A read link."),
    "daily/2026-11-12.md": "Read about [[bespoke-systems]] today.\n",
    ".hidden/x.md": "A dot folder is not part of the vault: [[atlas/people/nick]].\n",
    ".obsidian/app.json": "{}",
}

SESSION = {
    "CLAUDE.md": "@AGENTS.md\n",
    "AGENTS.md": "# Vault rules\n\nNever change the private folder.\n",
    "config/rules/vault-rule.md": "Link every full name.\n",
    "config/skills/find/SKILL.md":
        "---\nname: find\ndescription: \"Find an object by name.\"\n---\n# Find\n",
}


def build(folder, files):
    for name, text in files.items():
        path = Path(folder) / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return Path(folder)


class Counts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.report = measure.measure(build(cls.folder.name, VAULT), HOME)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_notes_in_each_home(self):
        self.assertEqual(self.report["notes"], {
            "atlas/people": 2,
            "atlas/companies": 1,
            "atlas/terms": 0,
            "intel/concepts": 1,
            "atlas/meetings": 4,
            "atlas/decisions": 1,
            "gtd/reference/quotes": 0,
            "projects": 2,
            "intel/briefings/daily": 0,
            "intel/syntheses": 1,
            "system/transcripts": 1,
            "system/bookmarks": 2,
            "system/session-log": 0,
            "system/intake": 1,
        })

    def test_links_with_a_missing_target(self):
        # Only in objects and syntheses. Code, pictures that exist,
        # headings, shown words and table bars do not confuse it.
        self.assertEqual(self.report["examples"]["broken_links"], [
            "atlas/people/sam-rivera.md -> missing-note",
            "atlas/meetings/2026-11-11-lost.md -> system/transcripts/2026-11-11-gone",
            "intel/syntheses/2026-11-12-pricing.md -> ghost",
        ])
        self.assertEqual(self.report["broken_links"], 3)

    def test_objects_nothing_links_to(self):
        self.assertEqual(self.report["unlinked_objects"], 7)
        self.assertEqual(self.report["examples"]["unlinked_objects"], [
            "atlas/people/nick.md",
            "atlas/meetings/2026-11-11-lost.md",
            "atlas/meetings/2026-11-12-web.md",
            "atlas/meetings/2026-11-13-plain.md",
            "atlas/decisions/2026-11-10-price.md",
        ])

    def test_people_without_a_full_name(self):
        self.assertEqual(self.report["people_without_full_name"], 1)
        self.assertEqual(
            self.report["examples"]["people_without_full_name"], ["atlas/people/nick.md"]
        )

    def test_meetings_with_a_missing_source(self):
        # A web address is not a vault target. An empty value names nothing.
        self.assertEqual(self.report["examples"]["meetings_with_missing_source"], [
            "atlas/meetings/2026-11-11-lost.md",
            "atlas/meetings/2026-11-13-plain.md",
        ])
        self.assertEqual(self.report["meetings_with_missing_source"], 2)

    def test_sources_not_processed(self):
        self.assertEqual(self.report["examples"]["sources_unprocessed"], [
            "system/bookmarks/b.md", "system/intake/a.md",
        ])
        self.assertEqual(self.report["sources_unprocessed"], 2)

    def test_the_report_has_the_shape_the_finish_test_wants(self):
        self.assertEqual(finish.measure_problems(self.report), [])
        self.assertEqual(finish.stamp_problems(self.report, self.folder.name), [])
        self.assertEqual(self.report["unreadable"], [])


class SessionLoad(unittest.TestCase):
    def test_the_made_up_home_alone(self):
        with tempfile.TemporaryDirectory() as folder:
            parts = measure.session_load(folder, HOME)
        # Counted by hand from the files in fixtures/home.
        self.assertEqual(parts, {
            "claude-code": {"instructions": 13, "rules": 7, "skills": 15},
            "codex": {"instructions": 9, "rules": 0, "skills": 6},
        })

    def test_a_vault_adds_its_own_files(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = build(folder, SESSION)
            # The vault's .claude folder is a link to its config folder.
            os.symlink("config", str(vault / ".claude"))
            report = measure.measure(vault, HOME)
        self.assertEqual(report["session_load_parts"], {
            # CLAUDE.md imports AGENTS.md: 1 + 7 more words.
            "claude-code": {"instructions": 21, "rules": 11, "skills": 20},
            "codex": {"instructions": 16, "rules": 0, "skills": 6},
        })
        self.assertEqual(report["session_load"], {"claude-code": 52, "codex": 22})

    def test_a_rule_with_a_path_limit_is_not_loaded(self):
        seen = set()
        self.assertEqual(measure.rule_words(HOME / ".claude" / "rules", seen), 7)
        self.assertEqual(len(seen), 2)

    def test_a_file_is_counted_once(self):
        with tempfile.TemporaryDirectory() as folder:
            build(folder, {"a.md": "one two @b.md\n", "b.md": "three @a.md\n"})
            self.assertEqual(measure.with_imports(Path(folder) / "a.md", set()), 5)

    def test_an_email_address_is_not_an_import(self):
        with tempfile.TemporaryDirectory() as folder:
            build(folder, {"a.md": "write to sam@b.md\n", "b.md": "one two three\n"})
            self.assertEqual(measure.with_imports(Path(folder) / "a.md", set()), 3)


class Reading(unittest.TestCase):
    def test_the_opening_block(self):
        keys, body = notes.front(
            "---\ntitle: \"A: B\"\nlist:\n  - one\n  - two\nfolded: >\n  a b\n  c\n---\nBody\n"
        )
        self.assertEqual(keys, {"title": "A: B", "list": "- one - two", "folded": "a b c"})
        self.assertEqual(body, "Body\n")
        self.assertEqual(notes.front("No block\n"), ({}, "No block\n"))
        self.assertEqual(notes.front("---\nnever: closed\n"), ({}, "---\nnever: closed\n"))

    def test_links(self):
        self.assertEqual(
            notes.link_targets("[[a]] [[b/c|C]] [[d#E]] ![[f.png]] [[#here]] [[g\\|G]]"),
            ["a", "b/c", "d", "f.png", "g"],
        )

    def test_a_link_resolves_by_any_tail_of_the_path_and_any_case(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = notes.Vault(build(folder, {"atlas/people/Sam Rivera.md": "x"}))
        for target in ("sam rivera", "people/Sam Rivera", "atlas/people/sam rivera.md"):
            self.assertEqual(vault.resolve(target), "atlas/people/Sam Rivera.md", target)
        self.assertIsNone(vault.resolve("rivera"))

    def test_project_briefs(self):
        self.assertTrue(places.is_project_brief("gtd/projects/alpha/brief.md"))
        self.assertTrue(places.is_project_brief(
            "atlas/businesses/acme/initiatives/growth/projects/site/brief.md"))
        self.assertFalse(places.is_project_brief("gtd/projects/alpha/status.md"))
        self.assertFalse(places.is_project_brief("gtd/projects/_archive/brief.md"))
        self.assertFalse(places.is_project_brief("atlas/businesses/acme/brief.md"))


class Command(unittest.TestCase):
    def run_wd(self, arguments, state):
        environment = dict(os.environ, HOME=str(HOME), WD_STATE_DIR=str(state))
        return subprocess.run(
            [sys.executable, str(WD)] + [str(argument) for argument in arguments],
            env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True,
        )

    def test_it_measures_prints_saves_and_changes_nothing(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = build(Path(folder) / "vault", VAULT)
            state = Path(folder) / "state"
            before, problems = finish.snapshot(vault)
            self.assertEqual(problems, [])
            result = self.run_wd(["check", "--measure", vault], state)
            after, _ = finish.snapshot(vault)
            self.assertEqual(result.returncode, cli.OK, result.stderr)
            self.assertEqual(finish.changed_files(before, after), [])
            report = json.loads((state / "measure.json").read_text(encoding="utf-8"))
            self.assertEqual(sorted(path.name for path in state.iterdir()), ["measure.json"])
        self.assertEqual(finish.measure_problems(report), [])
        self.assertEqual(report["broken_links"], 3)
        self.assertRegex(result.stdout, r"Objects nothing links to\s+7\n")
        self.assertRegex(result.stdout, r"Session load, Claude Code \(words\)\s+35\n")
        self.assertIn("Saved to", result.stdout)

    def test_it_refuses_to_keep_its_state_inside_the_vault(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = build(folder, VAULT)
            before, _ = finish.snapshot(vault)
            result = self.run_wd(["check", "--measure", vault], vault / "state")
            after, _ = finish.snapshot(vault)
        self.assertEqual(result.returncode, cli.FAILED)
        self.assertIn("inside the vault", result.stderr)
        self.assertEqual(finish.changed_files(before, after), [])

    def test_no_vault_and_a_missing_vault_fail(self):
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(cli.main(["check", "--measure"], out=out, err=err), cli.USAGE)
        self.assertEqual(
            cli.main(["check", "--measure", "/no/such/vault"], out=out, err=err), cli.FAILED
        )
        self.assertEqual(out.getvalue(), "")

    def test_plain_check_is_not_built_yet(self):
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(cli.main(["check"], out=out, err=err), cli.NOT_BUILT)
        self.assertIn("S1.4", err.getvalue())

    @unittest.skipIf(os.geteuid() == 0, "the administrator can read every file")
    def test_a_note_that_cannot_be_read_is_a_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = build(Path(folder) / "vault", VAULT)
            locked = vault / "atlas/people/nick.md"
            locked.chmod(0)
            try:
                result = self.run_wd(["check", "--measure", vault], Path(folder) / "state")
            finally:
                locked.chmod(0o600)
        self.assertEqual(result.returncode, cli.FAILED)
        self.assertIn("could not be read", result.stderr)


if __name__ == "__main__":
    unittest.main()
