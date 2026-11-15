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

SOURCE = "---\ntype: source\nkind: %s\nproduced: %s\n---\n%s\n"

VAULT = {
    "objects/people/sam-rivera.md":
        "# Sam Rivera\n\nWorks with [[objects/companies/acme|Acme]]. "
        "Met in [[2026-11-10-acme-kickoff]]. See [[missing-note]].\n",
    "objects/people/nick.md": "# Nick\n\nNo last name known.\n",
    # A file at the top of the vault. Its links are navigation.
    "status.md": "# Status\n\n[[nowhere]] and [[nick]]\n",
    "objects/companies/acme.md":
        "# Acme\n\nA made-up company. ![[logo.png]] and `[[not-a-link]]`\n\n"
        "```\n[[also-not-a-link]]\n```\n",
    "attachments/logo.png": "not really a picture",
    "objects/meetings/2026-11-10-acme-kickoff.md":
        "---\nsource: \"[[sources/recordings/2026-11-10-acme-kickoff]]\"\n---\n"
        "# Acme kickoff\n\nWith [[objects/people/sam-rivera|Sam Rivera]].\n\n"
        "| who | where |\n|---|---|\n| Sam | [[objects/companies/acme\\|Acme]] |\n",
    "objects/meetings/2026-11-11-lost.md":
        "---\nsource: \"[[sources/recordings/2026-11-11-gone]]\"\n---\n# Lost\n",
    "objects/meetings/2026-11-12-web.md":
        "---\nsource: https://example.com/call\n---\n# Web\n",
    "objects/meetings/2026-11-13-plain.md":
        "---\nsource: sources/recordings/2026-11-13-nope.md\n---\n# Plain\n",
    "objects/meetings/2026-11-14-label.md": "---\nsource: a recorder\n---\n# Label\n",
    "objects/meetings/2026-11-15-empty.md": "---\nsource:\n---\n# Empty\n",
    "objects/decisions/2026-11-10-price.md":
        "# Price\n\nDecided in [[2026-11-10-acme-kickoff#Decisions]] "
        "with [[../people/sam-rivera|Sam Rivera]], not [[../people/nobody]].\n",
    "objects/projects/alpha.md": "# Alpha\n\nFor [[Acme]].\n",
    "objects/projects/site.md": "# Site\n",
    "signals/syntheses/2026-11-12-pricing.md":
        "About [[objects/people/sam-rivera]] and [[ghost]].\n",
    "objects/concepts/bespoke-systems.md": "# Bespoke systems\n",
    "sources/recordings/2026-11-10-acme-kickoff.md":
        SOURCE % ("meeting-recording", "[\"[[objects/meetings/2026-11-10-acme-kickoff]]\"]",
                  "Sam: hello [[unknown-in-a-source]]"),
    "sources/captures/a.md": SOURCE % ("capture", "[]", "Dropped today."),
    "sources/links/b.md": SOURCE % ("article", "[]", "A saved link."),
    "sources/links/c.md":
        SOURCE % ("article", "\n  - \"[[objects/concepts/bespoke-systems]]\"", "A read link."),
    # No `produced` key at all: nothing is known to have come of it.
    "sources/sessions/d.md": "---\ntype: source\nkind: agent-session\n---\nA session.\n",
    "writing/2026-11-12.md": "Read about [[bespoke-systems]] today.\n",
    ".hidden/x.md": "A dot folder is not part of the vault: [[objects/people/nick]].\n",
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
            "objects/people": 2,
            "objects/companies": 1,
            "objects/projects": 2,
            "objects/terms": 0,
            "objects/concepts": 1,
            "objects/meetings": 6,
            "objects/decisions": 1,
            "objects/quotes": 0,
            "signals/briefs": 0,
            "signals/syntheses": 1,
            "sources/recordings": 1,
            "sources/links": 2,
            "sources/sessions": 1,
            "sources/captures": 1,
        })
        # The homes come in the build spec's order: objects, signals, sources.
        self.assertEqual(
            list(self.report["notes"]),
            [home for _, home in places.OBJECT_HOMES] + places.SIGNAL_HOMES + places.SOURCE_HOMES,
        )

    def test_links_with_a_missing_target(self):
        # Only in objects and syntheses. Code, pictures that exist,
        # headings, shown words and table bars do not confuse it.
        self.assertEqual(self.report["examples"]["broken_links"], [
            "objects/people/sam-rivera.md -> missing-note",
            "objects/meetings/2026-11-11-lost.md -> sources/recordings/2026-11-11-gone",
            "objects/decisions/2026-11-10-price.md -> ../people/nobody",
            "signals/syntheses/2026-11-12-pricing.md -> ghost",
        ])
        self.assertEqual(self.report["broken_links"], 4)

    def test_objects_with_no_link_in_or_out(self):
        # The same rule as `wd check`. The status page links to Nick.
        # That file is outside the graph, so he still counts. A link
        # from the owner's own writing is a connection, and so is a
        # link out: Alpha links to Acme, and the decision links to its
        # meeting. A source naming what it produced is not one.
        self.assertEqual(self.report["unlinked_objects"], 7)
        self.assertEqual(self.report["examples"]["unlinked_objects"], [
            "objects/people/nick.md",
            "objects/projects/site.md",
            "objects/meetings/2026-11-11-lost.md",
            "objects/meetings/2026-11-12-web.md",
            "objects/meetings/2026-11-13-plain.md",
        ])

    def test_people_without_a_full_name(self):
        self.assertEqual(self.report["people_without_full_name"], 1)
        self.assertEqual(
            self.report["examples"]["people_without_full_name"], ["objects/people/nick.md"]
        )

    def test_meetings_with_a_missing_source(self):
        # A web address is not a vault target, and neither is a label such
        # as the name of the recorder. An empty value names nothing.
        self.assertEqual(self.report["examples"]["meetings_with_missing_source"], [
            "objects/meetings/2026-11-11-lost.md",
            "objects/meetings/2026-11-13-plain.md",
        ])
        self.assertEqual(self.report["meetings_with_missing_source"], 2)

    def test_sources_that_produced_nothing(self):
        # An empty list, or no list at all. A list written over several
        # lines is a list with something in it.
        self.assertEqual(self.report["examples"]["sources_unprocessed"], [
            "sources/links/b.md", "sources/sessions/d.md", "sources/captures/a.md",
        ])
        self.assertEqual(self.report["sources_unprocessed"], 3)

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
            # 15 words of skill descriptions, and 7 from the one plugin
            # that is switched on.
            "claude-code": {"instructions": 13, "rules": 7, "skills": 22},
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
            "claude-code": {"instructions": 21, "rules": 11, "skills": 27},
            "codex": {"instructions": 16, "rules": 0, "skills": 6},
        })
        self.assertEqual(report["session_load"], {"claude-code": 59, "codex": 22})

    def test_codex_does_not_follow_imports(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = build(folder, {"AGENTS.md": "one @extra.md\n", "extra.md": "two three four\n",
                                   "CLAUDE.md": "@AGENTS.md\n"})
            parts = measure.session_load(vault, Path(folder) / "no-home")
        self.assertEqual(parts["codex"]["instructions"], 2)
        self.assertEqual(parts["claude-code"]["instructions"], 6)

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


# A made-up home with two plugins: one the user switched on, one the
# user switched off. Each has one skill.
PLUGIN_HOME = {
    ".claude/settings.json": json.dumps(
        {"enabledPlugins": {"lantern@made-up": True, "anchor@made-up": False}}),
    ".claude/plugins/installed_plugins.json": json.dumps({"version": 2, "plugins": {
        "lantern@made-up": [{"installPath": "plugins/cache/made-up/lantern/1.0.0"}],
        "anchor@made-up": [{"installPath": "plugins/cache/made-up/anchor/1.0.0"}],
    }}),
    # Three words.
    ".claude/plugins/cache/made-up/lantern/1.0.0/skills/light/SKILL.md":
        "---\nname: light\ndescription: Light the way.\n---\n# Light\n",
    # Five words.
    ".claude/plugins/cache/made-up/anchor/1.0.0/skills/hold/SKILL.md":
        "---\nname: hold\ndescription: Hold the boat quite still.\n---\n# Hold\n",
}
LANTERN, ANCHOR = 3, 5


def plugins(chosen):
    """A settings file that switches these plugins on or off."""
    return json.dumps({"enabledPlugins": {
        "%s@made-up" % name: on for name, on in chosen.items()
    }})


class PluginsInLayers(unittest.TestCase):
    """Claude Code's settings are layered: the user's file, the vault's, the vault's local file.

    Each later file wins, plugin by plugin. Switching plugins off in
    the vault is how the owner gets a session under the word limit.
    The settings files are written here, by Python, in scratch folders.
    """

    def skills(self, vault_files):
        with tempfile.TemporaryDirectory() as folder:
            home = build(Path(folder) / "home", PLUGIN_HOME)
            vault = build(Path(folder) / "vault", dict({"AGENTS.md": "x\n"}, **vault_files))
            return measure.session_load(vault, home)["claude-code"]["skills"]

    def test_the_users_file_alone(self):
        self.assertEqual(self.skills({}), LANTERN)

    def test_the_vault_switches_off_a_plugin_the_user_switched_on(self):
        self.assertEqual(
            self.skills({".claude/settings.json": plugins({"lantern": False})}), 0)

    def test_the_vault_switches_on_a_plugin_the_user_switched_off(self):
        self.assertEqual(
            self.skills({".claude/settings.json": plugins({"anchor": True})}), LANTERN + ANCHOR)

    def test_the_vaults_local_file_switches_one_off(self):
        self.assertEqual(
            self.skills({".claude/settings.local.json": plugins({"lantern": False})}), 0)

    def test_the_vaults_local_file_switches_one_on(self):
        self.assertEqual(
            self.skills({".claude/settings.local.json": plugins({"anchor": True})}),
            LANTERN + ANCHOR,
        )

    def test_the_local_file_wins_over_the_vaults_file(self):
        self.assertEqual(self.skills({
            ".claude/settings.json": plugins({"lantern": False, "anchor": True}),
            ".claude/settings.local.json": plugins({"lantern": True, "anchor": False}),
        }), LANTERN)

    def test_a_plugin_a_later_file_does_not_name_keeps_its_setting(self):
        self.assertEqual(self.skills({
            ".claude/settings.json": plugins({"anchor": True}),
            ".claude/settings.local.json": plugins({"anchor": True}),
        }), LANTERN + ANCHOR)
        self.assertEqual(self.skills({
            ".claude/settings.json": plugins({"lantern": False}),
            ".claude/settings.local.json": "{}",
        }), 0)

    def test_a_settings_file_that_is_not_valid_changes_nothing(self):
        self.assertEqual(self.skills({".claude/settings.json": "{not json"}), LANTERN)
        self.assertEqual(self.skills({".claude/settings.json": "[]"}), LANTERN)


class Reading(unittest.TestCase):
    def test_the_opening_block(self):
        keys, body = notes.front(
            "---\ntitle: \"A: B\"\nlist:\n  - one\n  - two\nfolded: >\n  a b\n  c\n---\nBody\n"
        )
        self.assertEqual(keys, {"title": "A: B", "list": "- one - two", "folded": "a b c"})
        self.assertEqual(body, "Body\n")
        self.assertEqual(notes.front("No block\n"), ({}, "No block\n"))
        self.assertEqual(notes.front("---\nnever: closed\n"), ({}, "---\nnever: closed\n"))

    def test_comments_in_the_opening_block(self):
        keys, _ = notes.front(
            "---\nstarred: false # waiting\n# a line of its own\n"
            "title: \"A # B\" # after\nsource: sources/x.md   # where\n---\n"
        )
        self.assertEqual(keys, {"starred": "false", "title": "A # B", "source": "sources/x.md"})

    def test_links(self):
        self.assertEqual(
            notes.link_targets("[[a]] [[b/c|C]] [[d#E]] ![[f.png]] [[#here]] [[g\\|G]]"),
            ["a", "b/c", "d", "f.png", "g"],
        )

    def test_a_link_resolves_by_any_tail_of_the_path_and_any_case(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = notes.Vault(build(folder, {"objects/people/Sam Rivera.md": "x"}))
        for target in ("sam rivera", "people/Sam Rivera", "objects/people/sam rivera.md"):
            self.assertEqual(vault.resolve(target), "objects/people/Sam Rivera.md", target)
        self.assertIsNone(vault.resolve("rivera"))

    def test_a_file_in_the_linking_notes_own_folder_wins(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = notes.Vault(build(folder, {
                "a/acme.md": "x", "objects/companies/acme.md": "x",
                "objects/companies/bluepeak.md": "x",
            }))
        self.assertEqual(vault.resolve("acme"), "a/acme.md")
        self.assertEqual(
            vault.resolve("acme", "objects/companies/bluepeak.md"), "objects/companies/acme.md")
        self.assertEqual(vault.resolve("companies/acme", "a/acme.md"), "objects/companies/acme.md")

    def test_a_link_that_starts_from_the_notes_own_folder(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = notes.Vault(build(folder, {
                "objects/people/sam.md": "x", "objects/meetings/m.md": "x",
                "sources/recordings/t.md": "x", "other/meetings/m.md": "x",
            }))
        here = "objects/people/sam.md"
        self.assertEqual(vault.resolve("../meetings/m", here), "objects/meetings/m.md")
        self.assertEqual(vault.resolve("../Meetings/M.md", here), "objects/meetings/m.md")
        self.assertEqual(vault.resolve("../../sources/recordings/t", here), "sources/recordings/t.md")
        self.assertEqual(vault.resolve("./sam", here), "objects/people/sam.md")
        # It must name a file exactly: no guessing, and no leaving the vault.
        self.assertIsNone(vault.resolve("../meetings/gone", here))
        self.assertIsNone(vault.resolve("../../../outside", here))
        self.assertIsNone(vault.resolve("../m", "other/meetings/m.md"))
        self.assertIsNone(vault.resolve("../meetings/m"))

    def test_a_project_is_a_plain_note_in_its_home(self):
        home = places.home_of("project")
        self.assertEqual(home, "objects/projects")
        self.assertTrue(places.in_home("objects/projects/alpha.md", home))
        self.assertFalse(places.in_home("objects/projects.md", home))
        self.assertFalse(places.in_home("objects/projects-old/alpha.md", home))
        self.assertFalse(places.in_home("writing/objects/projects/alpha.md", home))


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
        self.assertEqual(report["broken_links"], 4)
        self.assertRegex(result.stdout, r"Objects with no link in or out\s+7\n")
        self.assertRegex(result.stdout, r"Sources that produced nothing\s+3\n")
        self.assertRegex(result.stdout, r"Session load, Claude Code \(words\)\s+42\n")
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

    def test_plain_check_wants_a_vault(self):
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(cli.main(["check"], out=out, err=err), cli.USAGE)
        self.assertIn("usage: wd check <vault>", err.getvalue())

    @unittest.skipIf(os.geteuid() == 0, "the administrator can read every file")
    def test_a_note_that_cannot_be_read_is_a_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            vault = build(Path(folder) / "vault", VAULT)
            locked = vault / "objects/people/nick.md"
            locked.chmod(0)
            try:
                result = self.run_wd(["check", "--measure", vault], Path(folder) / "state")
            finally:
                locked.chmod(0o600)
        self.assertEqual(result.returncode, cli.FAILED)
        self.assertIn("could not be read", result.stderr)


if __name__ == "__main__":
    unittest.main()
