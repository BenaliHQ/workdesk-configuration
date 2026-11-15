"""`wd init`, the nine samples, and `wd graph-setting` (package S1.3)."""

import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
CORE = TESTS.parent
WD = CORE / "bin" / "wd"
PRODUCT = CORE / "product"
SAMPLES = PRODUCT / "samples"
for folder in (CORE, TESTS):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import stage1_finish as finish  # noqa: E402
from wd import cli, declarations, notes, obsidian, places  # noqa: E402
from wd import init as maker  # noqa: E402

TYPE_HOMES = dict(places.OBJECT_HOMES)
RECORDINGS = declarations.sources()["meeting-recording"]["home"]
# Build spec, "Object frontmatter": the keys every object opens with, in order.
OPENING_KEYS = ["type", "name", "aliases", "private"]
MAX_SUMMARY_LINES = 3
MIN_TURNS = 10
EM_DASH = chr(0x2014)
TUESDAY = 1

BASES = ("stated", "reported", "inferred", "correction")
PASSAGE = r"\[\[([^\[\]|#\n]+)#\^(p\d{4})\]\]"
HISTORY = re.compile(
    r"^- (\d{4}-\d\d-\d\d) \| ([^|]+) \| (%s) \| %s \| run-\d{8}-\d{4}$"
    % ("|".join(BASES), PASSAGE)
)
CURRENTLY = re.compile(r"^- (.+)\. (\d{4}-\d\d-\d\d), %s$" % PASSAGE)
CITED = re.compile(r"^- (.+) %s$" % PASSAGE)
TURN = re.compile(r"^([A-Z][a-z]+(?: [A-Z][a-z]+)+): (.+) \^(p\d{4})$")
LINK = re.compile(r"\[\[([^\[\]\n]+)\]\]")
WORD = re.compile(r"[A-Za-z]+")
# One entry of a list written on one line: in quotes, or plain.
ENTRY = re.compile(r'"([^"]*)"|([^,\[\]"]+)')
# One term of the graph's filter: a regular expression between slashes.
TERM = re.compile(r"^-path:/(.+)/$")
# Words a line uses to report what was said. They are not in the passage.
REPORTING = {"said"}


# ---- helpers ----

def run(arguments):
    """Run a command inside this process. Returns (code, what it printed, its errors).

    The home folder is the made-up one, so the status page `wd init`
    writes counts the same words on every machine.
    """
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, {"HOME": str(TESTS / "fixtures" / "home")}):
        code = cli.main([str(argument) for argument in arguments], out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def snapshot(root):
    """Every folder and every file under root, with each file's bytes."""
    root = Path(root)
    found = {}
    for here, names, file_names in os.walk(str(root)):
        for name in names:
            found[(Path(here) / name).relative_to(root).as_posix() + "/"] = None
        for name in file_names:
            path = Path(here) / name
            found[path.relative_to(root).as_posix()] = (
                os.readlink(str(path)) if path.is_symlink() else path.read_bytes()
            )
    return found


def raw_keys(text):
    """(key, value as written) for each line of a note's opening block."""
    found = []
    for line in text.split("\n")[1:]:
        if line.strip() == "---":
            break
        match = notes.KEY.match(line)
        if match:
            found.append((match.group(1), match.group(2).strip()))
    return found


def sections(body):
    """The lines under each `## ` heading, by heading, in order."""
    found, current = [], None
    for line in body.split("\n"):
        if line.startswith("## "):
            current = (line[3:].strip(), [])
            found.append(current)
        elif current is not None and line.strip():
            current[1].append(line)
    return found


def summary(body):
    """The first paragraph under the title, as its lines."""
    lines = body.split("\n")
    start = next(number for number, line in enumerate(lines) if line.startswith("# ")) + 1
    while not lines[start].strip():
        start += 1
    end = start
    while end < len(lines) and lines[end].strip():
        end += 1
    return lines[start:end]


def links(text):
    """(target without passage, passage or None, shown words or None) for each link."""
    found = []
    for inner in LINK.findall(text):
        target, _, shown = inner.partition("|")
        target, _, passage = target.partition("#")
        found.append((target.strip(), passage.lstrip("^") or None, shown.strip() or None))
    return found


def entries(value):
    """The entries of a list written on one line, such as `["a b", c d]`."""
    assert value.startswith("[") and value.endswith("]"), value
    return [
        (quoted or plain).strip()
        for quoted, plain in ENTRY.findall(value[1:-1]) if (quoted or plain).strip()
    ]


def shown_words(line):
    """A line as it reads: each link replaced by the words it shows."""
    return LINK.sub(lambda match: match.group(1).partition("|")[2].strip(), line)


def hidden_from_the_graph(search, paths):
    """The paths Obsidian's graph leaves out under this filter.

    Each term is `-path:/<expression>/`. Obsidian tries the expression
    against a note's path from the top of the vault, and without regard
    to case. A note is left out when any term finds a match.
    """
    expressions = []
    for term in search.split():
        match = TERM.match(term)
        assert match, "%s is not a -path: term with a regular expression" % term
        expressions.append(re.compile(match.group(1), re.IGNORECASE))
    return [path for path in paths if any(found.search(path) for found in expressions)]


def rests_on(word, passage):
    """Is this word in the passage, give or take its ending?"""
    word = word.lower()
    return word[:max(4, len(word) - 2)] in passage.lower()


def not_in_passage(text, passage):
    """The words of four letters or more that the passage does not hold."""
    return [
        word for word in WORD.findall(text)
        if len(word) >= 4 and word.lower() not in REPORTING and not rests_on(word, passage)
    ]


class Samples:
    """The sample notes in the product folder, read once."""

    def __init__(self):
        self.vault = notes.Vault(SAMPLES)
        self.objects = [
            (kind, note) for kind, home in places.OBJECT_HOMES
            for note in self.vault.notes if places.in_home(note, home)
        ]
        self.recordings = [n for n in self.vault.notes if places.in_home(n, RECORDINGS)]
        self.passages = {}
        for name in self.recordings:
            _, body = notes.front(self.vault.text(name))
            for block in body.strip().split("\n\n"):
                match = TURN.match(block)
                if match:
                    self.passages[(name[:-3], match.group(3))] = block
        # The name of each object that is linked by name, by its path.
        self.names = {}
        for kind, note in self.objects:
            if kind in places.LINKABLE:
                self.names[note[:-3]] = notes.front(self.vault.text(note))[0].get("name", "")

    def text(self, note):
        return self.vault.text(note)

    def parts(self, note):
        return notes.front(self.text(note))

    def of(self, kind):
        return [note for found, note in self.objects if found == kind]

    def passage(self, target, marker):
        return self.passages.get((target, marker))

    def plain(self, line):
        """A line as it reads, without the links to things that have a name.

        A link to a person, company, project, term or concept that shows
        the object's own name is taken out: who is meant comes from the
        attendee list, not from the passage. Any other link is replaced
        by the words it shows.
        """
        def shown(match):
            target, _, words = match.group(1).partition("|")
            target = target.split("#", 1)[0].strip()
            if self.names.get(target) == words.strip():
                return " "
            return words.strip() or " "
        return LINK.sub(shown, line)


SAMPLE = Samples()


# ---- wd init ----

class Init(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name).resolve()
        self.vault = self.scratch / "vault"

    def test_the_folders_are_the_build_specs_and_come_from_the_declarations(self):
        self.assertEqual(maker.folders(), finish.FOLDERS)
        homes = [found["home"] for found in declarations.objects().values()]
        for home in homes + declarations.source_homes():
            self.assertIn(home, maker.folders())

    def test_it_makes_the_empty_vault(self):
        code, out, err = run(["init", self.vault])
        self.assertEqual((code, err), (cli.OK, ""))
        self.assertEqual(finish.init_problems(self.vault, samples=False), [])
        made = snapshot(self.vault)
        folders = sorted(name[:-1] for name in made if name.endswith("/"))
        self.assertEqual(folders, sorted(finish.allowed_folders() | {
            "%s/%s" % (place, name) for place in finish.SKILL_FOLDERS for name in finish.SKILLS
        } | {".claude", ".agents"}))
        files = sorted(name for name in made if not name.endswith("/"))
        self.assertEqual(files, sorted(
            ["AGENTS.md", "CLAUDE.md", "status.md", ".obsidian/app.json", ".obsidian/graph.json"]
            + ["%s/%s/SKILL.md" % (place, name)
               for place in finish.SKILL_FOLDERS for name in finish.SKILLS]
        ))

    def test_the_rulebook_and_the_skills_are_copies_of_the_product(self):
        run(["init", self.vault])
        for name in ("AGENTS.md", "CLAUDE.md"):
            self.assertEqual((self.vault / name).read_bytes(), (PRODUCT / name).read_bytes())
        for place in (".claude/skills", ".agents/skills"):
            for name in finish.SKILLS:
                self.assertEqual(
                    (self.vault / place / name / "SKILL.md").read_bytes(),
                    (PRODUCT / "skills" / name / "SKILL.md").read_bytes(),
                    "%s/%s" % (place, name),
                )

    def test_it_finishes_with_the_status_page(self):
        # The third root file, written by the same code as `wd status`.
        run(["init", self.vault, "--samples"])
        page = (self.vault / "status.md").read_text(encoding="utf-8")
        self.assertTrue(page.startswith("# Status\n"))
        self.assertIn("- objects/people: 1", page)
        self.assertIn("- sources/recordings: 1", page)
        self.assertIn("The check found 0 problems. It looked at 8 objects and 0 syntheses.", page)
        self.assertRegex(page, r"- Claude Code: [\d,]+ words in all\. [\d,]+ from the vault "
                               r"and 42 from outside it\.")
        code, again, _ = run(["status", self.vault, "--dry-run"])
        self.assertEqual(code, cli.OK)
        written = [line for line in page.splitlines() if not line.startswith("Written on ")]
        self.assertEqual(
            [line for line in again.splitlines() if not line.startswith("Written on ")], written)
        run(["init", self.scratch / "empty"])
        empty = (self.scratch / "empty" / "status.md").read_text(encoding="utf-8")
        self.assertIn("- objects/people: 0", empty)
        self.assertIn("The check found 0 problems.", empty)

    def test_it_writes_no_writing_and_no_runtime_settings(self):
        run(["init", self.vault, "--samples"])
        made = snapshot(self.vault)
        self.assertEqual([name for name in made if name.startswith("writing/")], ["writing/"])
        self.assertEqual([name for name in made if name.startswith(".codex")], [])
        for name in made:
            if name.endswith("/"):
                continue
            if name.startswith(".claude/") or name.startswith(".agents/"):
                self.assertTrue(
                    name.startswith((".claude/skills/", ".agents/skills/")), name)
                self.assertFalse(name.endswith((".json", ".toml")), name)

    def test_with_samples_it_adds_the_nine_notes_as_they_are_kept(self):
        code, out, err = run(["init", self.vault, "--samples"])
        self.assertEqual((code, err), (cli.OK, ""))
        self.assertEqual(finish.init_problems(self.vault, samples=True), [])
        made = snapshot(self.vault)
        copied = sorted(name for name in made if name.endswith(".md") and (
            name.startswith("objects/") or name.startswith("sources/")))
        self.assertEqual(copied, sorted(SAMPLE.vault.notes))
        self.assertEqual(len(copied), 9)
        for name in copied:
            self.assertEqual(made[name], (SAMPLES / name).read_bytes(), name)

    def test_an_empty_folder_that_is_already_there_is_fine(self):
        self.vault.mkdir()
        code, _, err = run(["init", self.vault])
        self.assertEqual((code, err), (cli.OK, ""))
        self.assertEqual(finish.init_problems(self.vault), [])

    def test_folders_above_the_vault_are_made(self):
        vault = self.scratch / "new" / "deeper" / "vault"
        code, _, err = run(["init", vault])
        self.assertEqual((code, err), (cli.OK, ""))
        self.assertEqual(finish.init_problems(vault), [])

    def test_it_says_what_it_made(self):
        _, out, _ = run(["init", self.vault, "--samples"])
        self.assertIn(str(self.vault), out)
        for folder in finish.FOLDERS:
            self.assertIn("%s/" % folder, out)
        for name in list(finish.FILES_FROM_INIT) + finish.SKILLS + list(finish.SKILL_FOLDERS):
            self.assertIn(name, out)
        for name in (".obsidian/graph.json", ".obsidian/app.json"):
            self.assertIn(name, out)
        for name in SAMPLE.vault.notes:
            self.assertIn(name, out)
        self.assertIn("status.md", out)
        self.assertNotIn(EM_DASH, out)
        _, plain, _ = run(["init", self.scratch / "second"])
        self.assertNotIn("Samples", plain)

    def refused(self, arguments, expected=cli.FAILED):
        before = snapshot(self.scratch)
        code, out, err = run(arguments)
        self.assertEqual(code, expected)
        self.assertEqual(out, "")
        self.assertEqual(snapshot(self.scratch), before, "Something was changed.")
        return err

    def test_a_folder_that_is_not_empty_is_refused_and_left_untouched(self):
        self.vault.mkdir()
        (self.vault / "kept.md").write_text("Already here.\n", encoding="utf-8")
        err = self.refused(["init", self.vault, "--samples"])
        self.assertEqual(len(err.strip().splitlines()), 1, "One plain sentence.")
        self.assertIn(str(self.vault), err)
        self.assertIn("nothing was made", err)

    def test_a_folder_with_only_a_hidden_file_is_refused(self):
        self.vault.mkdir()
        (self.vault / ".DS_Store").write_bytes(b"\x00")
        self.refused(["init", self.vault])

    def test_a_folder_with_only_an_empty_folder_in_it_is_refused(self):
        (self.vault / "objects").mkdir(parents=True)
        self.refused(["init", self.vault])

    def test_a_file_is_refused(self):
        self.vault.write_text("A file, not a folder.\n", encoding="utf-8")
        err = self.refused(["init", self.vault])
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertIn("not a folder", err)

    def test_a_link_that_points_nowhere_is_refused(self):
        os.symlink(str(self.scratch / "gone"), str(self.vault))
        err = self.refused(["init", self.vault])
        self.assertIn("is a link", err)

    def test_a_link_to_an_empty_folder_is_refused(self):
        # The vault would land somewhere other than the path that was given.
        elsewhere = self.scratch / "elsewhere"
        elsewhere.mkdir()
        os.symlink(str(elsewhere), str(self.vault))
        err = self.refused(["init", self.vault, "--samples"])
        self.assertEqual(len(err.strip().splitlines()), 1, "One plain sentence.")
        self.assertIn("is a link", err)
        self.assertIn("nothing was made", err)
        self.assertEqual(list(elsewhere.iterdir()), [])
        self.assertTrue(self.vault.is_symlink())

    def test_a_link_to_a_file_is_refused(self):
        kept = self.scratch / "kept.md"
        kept.write_text("Not a folder.\n", encoding="utf-8")
        os.symlink(str(kept), str(self.vault))
        err = self.refused(["init", self.vault])
        self.assertIn("is a link", err)

    def test_a_vault_that_init_made_is_refused_the_second_time(self):
        run(["init", self.vault])
        self.refused(["init", self.vault])

    def test_wrong_arguments_are_a_usage_failure_and_make_nothing(self):
        for arguments in (
            ["init"],
            ["init", "--samples"],
            ["init", self.vault, self.scratch / "other"],
            ["init", self.vault, "--sample"],
            ["init", self.vault, "--dry-run"],
        ):
            err = self.refused(arguments, expected=cli.USAGE)
            self.assertIn("usage: wd init <vault> [--samples]", err)

    def test_a_product_folder_with_a_piece_missing_stops_it_before_anything_is_made(self):
        empty = self.scratch / "empty"
        empty.mkdir()
        for name in ("SKILLS", "SAMPLES", "PRODUCT"):
            with mock.patch.object(maker, name, empty):
                err = self.refused(["init", self.vault, "--samples"])
            self.assertIn("product folder", err, name)
        with mock.patch.object(obsidian, "PRODUCT_FILE", empty / "obsidian.json"):
            err = self.refused(["init", self.vault])
        self.assertIn("obsidian.json is missing", err)

    def test_a_sample_outside_the_homes_is_refused(self):
        strays = self.scratch / "strays"
        (strays / "notes").mkdir(parents=True)
        (strays / "notes" / "stray.md").write_text("# Stray\n", encoding="utf-8")
        with mock.patch.object(maker, "SAMPLES", strays):
            err = self.refused(["init", self.vault, "--samples"])
        self.assertIn("notes/stray.md", err)

    def test_it_never_writes_outside_the_folder_it_is_given(self):
        # Run as its own program, with a made-up home, state folder and
        # working folder. Only the vault may change.
        for name in ("home", "state", "cwd", "beside"):
            (self.scratch / name).mkdir()
        (self.scratch / "beside" / "note.md").write_text("Not yours.\n", encoding="utf-8")
        before = snapshot(self.scratch)
        # Python on macOS keeps its own compiled files under the home
        # folder. That is Python, not `wd`, so it is switched off here.
        environment = dict(
            os.environ, HOME=str(self.scratch / "home"),
            WD_STATE_DIR=str(self.scratch / "state"), PYTHONDONTWRITEBYTECODE="1",
        )
        result = subprocess.run(
            [sys.executable, str(WD), "init", str(self.vault), "--samples"],
            env=environment, cwd=str(self.scratch / "cwd"),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        after = snapshot(self.scratch)
        changed = sorted(
            name for name in set(before) | set(after) if before.get(name, 0) != after.get(name, 0)
        )
        self.assertTrue(changed)
        for name in changed:
            self.assertTrue(name == "vault/" or name.startswith("vault/"), name)

    def test_the_product_folder_is_not_changed(self):
        before = snapshot(PRODUCT)
        run(["init", self.vault, "--samples"])
        self.assertEqual(snapshot(PRODUCT), before)

    def test_no_temporary_file_is_left_behind(self):
        run(["init", self.vault, "--samples"])
        self.assertEqual([name for name in snapshot(self.vault) if name.endswith(".tmp")], [])

    def test_the_settings_are_the_ones_graph_setting_writes(self):
        run(["init", self.vault])
        for name, keys in obsidian.wanted():
            self.assertEqual(finish.read_json(self.vault / ".obsidian" / name), keys, name)
        code, out, _ = run(["graph-setting", self.vault, "--dry-run"])
        self.assertEqual(code, cli.OK)
        self.assertEqual(out.count("already right"), 2)


# ---- the samples ----

class TheSamples(unittest.TestCase):
    def test_nine_notes_one_in_each_object_home_and_one_recording(self):
        self.assertEqual(len(SAMPLE.vault.files), 9)
        self.assertEqual(len(SAMPLE.vault.notes), 9)
        for kind, home in places.OBJECT_HOMES:
            self.assertEqual(len(SAMPLE.of(kind)), 1, home)
        self.assertEqual(len(SAMPLE.recordings), 1)
        self.assertEqual(
            sorted(SAMPLE.vault.notes),
            sorted([note for _, note in SAMPLE.objects] + SAMPLE.recordings),
        )

    def test_every_sample_says_it_is_one_as_its_last_key(self):
        for name in SAMPLE.vault.notes:
            self.assertEqual(raw_keys(SAMPLE.text(name))[-1], ("sample", "true"), name)

    def test_every_object_follows_its_declaration(self):
        for kind, note in SAMPLE.objects:
            declared = declarations.objects()[kind]
            text = SAMPLE.text(note)
            keys, body = SAMPLE.parts(note)
            self.assertEqual(keys.get("type"), kind, note)
            self.assertEqual(keys.get("private"), "false", note)
            order = [key for key, _ in raw_keys(text)]
            self.assertEqual(len(order), len(set(order)), note)
            # type, name, aliases, private, then the type's own keys.
            opening = [key for key in OPENING_KEYS if key in declared["required-keys"]]
            rest = [key for key in declared["required-keys"] if key not in OPENING_KEYS]
            self.assertEqual(order[:len(opening) + len(rest)], opening + rest, note)
            for key in rest:
                self.assertTrue(keys[key], "%s: %s is empty" % (note, key))
            # The sections a note has are ones its type lists, in that
            # order. A sample shows every one of them, but for History on
            # the meeting and the quote, which is left out while empty.
            has = [heading for heading, _ in sections(body)]
            self.assertEqual(has, [name for name in declared["sections"] if name in has], note)
            self.assertEqual(
                [name for name in declared["sections"] if name not in has],
                ["History"] if kind in ("meeting", "quote") else [], note,
            )
            if kind in places.LINKABLE:
                self.assertEqual(keys["name"], notes.first_heading(body), note)
                self.assertTrue(keys["aliases"].startswith("["), note)
            else:
                self.assertNotIn("name", keys, note)
                self.assertNotIn("aliases", keys, note)
            self.assertTrue(body.startswith("# "), "%s: the title comes first" % note)

    def test_values_are_quoted_only_when_they_must_be(self):
        # Build spec: quoted only with a colon, a hash, or a bracket at the start.
        for name in SAMPLE.vault.notes:
            for key, value in raw_keys(SAMPLE.text(name)):
                where = "%s: %s" % (name, key)
                if value.startswith("\""):
                    inner = value[1:-1]
                    self.assertTrue(
                        ":" in inner or "#" in inner or inner.startswith("["), where)
                elif value.startswith("["):
                    self.assertTrue(value.endswith("]"), "%s is a list on one line" % where)
                else:
                    self.assertNotIn(":", value, where)
                    self.assertNotIn("#", value, where)

    def test_each_summary_is_three_lines_and_sixty_words_at_most(self):
        for kind, note in SAMPLE.objects:
            _, body = SAMPLE.parts(note)
            lines = summary(body)
            self.assertLessEqual(len(lines), MAX_SUMMARY_LINES, note)
            sentences = [part for part in re.split(r"(?<=[.!?])\s+", " ".join(lines)) if part]
            self.assertLessEqual(len(sentences), MAX_SUMMARY_LINES, note)
            self.assertLessEqual(
                len(notes.words(" ".join(lines))),
                declarations.objects()[kind]["summary-max-words"], note,
            )
            self.assertFalse(lines[0].startswith("#"), note)

    def test_every_link_is_a_full_path_to_a_sample(self):
        count = 0
        for name in SAMPLE.vault.notes:
            for target, passage, _ in links(SAMPLE.text(name)):
                where = "%s -> %s" % (name, target)
                self.assertIn(target + ".md", SAMPLE.vault.notes, where)
                self.assertEqual(SAMPLE.vault.resolve(target, name), target + ".md", where)
                if passage is not None:
                    self.assertIsNotNone(
                        SAMPLE.passage(target, passage), "%s#^%s" % (where, passage))
                count += 1
        self.assertGreater(count, 60)

    def test_no_link_shows_a_first_name_on_its_own(self):
        people = set(SAMPLE.of("person"))
        first_names = {SAMPLE.names[note[:-3]].split()[0] for note in people}
        for name in SAMPLE.vault.notes:
            for target, _, shown in links(SAMPLE.text(name)):
                where = "%s -> %s" % (name, target)
                if shown is not None:
                    self.assertNotIn(shown, first_names, where)
                    self.assertFalse(shown.startswith("objects/"), where)
                if target + ".md" in people and shown is not None:
                    self.assertGreaterEqual(len(shown.split()), 2, where)

    def test_a_link_to_a_named_object_shows_its_exact_name(self):
        for kind, note in SAMPLE.objects:
            _, body = SAMPLE.parts(note)
            for target, _, shown in links(body):
                if target in SAMPLE.names:
                    self.assertEqual(shown, SAMPLE.names[target], "%s -> %s" % (note, target))

    def test_every_object_is_linked_from_the_body_of_another_object(self):
        linked = {}
        for _, note in SAMPLE.objects:
            _, body = SAMPLE.parts(note)
            for target, _, _ in links(body):
                if target + ".md" != note:
                    linked.setdefault(target + ".md", set()).add(note)
        for _, note in SAMPLE.objects:
            self.assertTrue(linked.get(note), "%s: no other object links to it" % note)
        self.assertEqual(finish.link_problems(
            {name: SAMPLE.text(name) for name in SAMPLE.vault.notes}), [])

    def test_every_mention_of_a_named_object_is_linked_outside_history(self):
        # In a summary, under `## Currently` and in a meeting's sections,
        # as the linker would leave them. The lines under `## History`
        # stay plain: a history line's text may hold no bar.
        for kind, note in SAMPLE.objects:
            _, body = SAMPLE.parts(note)
            own = SAMPLE.names.get(note[:-3])
            lines = list(summary(body))
            for heading, under in sections(body):
                if heading != "History":
                    lines += under
            if kind == "quote":
                lines = [line for line in body.split("\n") if line.strip() and line[0] not in "#>"]
            for line in lines:
                left = LINK.sub(" ", line)
                for name in SAMPLE.names.values():
                    if name == own:
                        continue
                    self.assertIsNone(
                        re.search(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(name), left),
                        "%s: %s is not linked in: %s" % (note, name, line),
                    )

    def test_every_history_line_points_at_a_passage_that_holds_its_words(self):
        count = 0
        dates = {SAMPLE.parts(name)[0]["date"] for name in SAMPLE.recordings}
        for kind, note in SAMPLE.objects:
            _, body = SAMPLE.parts(note)
            for heading, lines in sections(body):
                if heading != "History":
                    continue
                self.assertTrue(lines, "%s: an empty history" % note)
                for line in lines:
                    match = HISTORY.match(line)
                    self.assertIsNotNone(match, "%s: %s" % (note, line))
                    date, text, _, target, marker = match.groups()
                    self.assertIn(date, dates, note)
                    passage = SAMPLE.passage(target, marker)
                    self.assertIsNotNone(passage, "%s: %s" % (note, line))
                    self.assertEqual(not_in_passage(text, passage), [], "%s: %s" % (note, line))
                    count += 1
                stamps = [HISTORY.match(line).group(1) for line in lines]
                self.assertEqual(stamps, sorted(stamps, reverse=True), "%s: newest first" % note)
        self.assertGreaterEqual(count, 8)

    def test_every_current_fact_points_at_a_passage_and_has_its_history_line(self):
        count = 0
        for kind, note in SAMPLE.objects:
            _, body = SAMPLE.parts(note)
            found = dict(sections(body))
            if "Currently" not in found:
                continue
            history = [HISTORY.match(line).groups() for line in found["History"]]
            self.assertTrue(found["Currently"], "%s: nothing under Currently" % note)
            for line in found["Currently"]:
                match = CURRENTLY.match(line)
                self.assertIsNotNone(match, "%s: %s" % (note, line))
                text, date, target, marker = match.groups()
                # The history line says the same thing in plain text.
                text = shown_words(text)
                passage = SAMPLE.passage(target, marker)
                self.assertIsNotNone(passage, "%s: %s" % (note, line))
                self.assertEqual(not_in_passage(text, passage), [], "%s: %s" % (note, line))
                self.assertIn(
                    (date, text, target, marker),
                    [(a, b, d, e) for a, b, _, d, e in history],
                    "%s: no history line for: %s" % (note, line),
                )
                count += 1
        self.assertGreaterEqual(count, 5)

    def test_the_meeting(self):
        (note,) = SAMPLE.of("meeting")
        keys, body = SAMPLE.parts(note)
        (recording,) = SAMPLE.recordings
        self.assertEqual(datetime.date.fromisoformat(keys["date"]).weekday(), TUESDAY)
        self.assertEqual(notes.link_targets(keys["source"]), [recording[:-3]])
        self.assertEqual(keys["date"], SAMPLE.parts(recording)[0]["date"])
        # Each attendee is a full name. One who has a note is a link to it.
        # The owner has no note among the nine samples, so is plain text.
        attendees = entries(dict(raw_keys(SAMPLE.text(note)))["attendees"])
        full_names = []
        for entry in attendees:
            if LINK.search(entry):
                ((target, _, shown),) = links(entry)
                self.assertEqual(entry, "[[%s|%s]]" % (target, shown))
                self.assertIn(target + ".md", SAMPLE.of("person"))
                self.assertEqual(shown, SAMPLE.names[target])
                full_names.append(shown)
            else:
                self.assertNotIn(entry, SAMPLE.names.values(), "%s has a note" % entry)
                full_names.append(entry)
        for name in full_names:
            self.assertGreaterEqual(len(name.split()), 2, name)
        self.assertEqual(len(full_names), len(set(full_names)))
        self.assertEqual(
            sorted(full_names[:1]), [SAMPLE.names[SAMPLE.of("person")[0][:-3]]],
            "The person with a note comes first, as a link.",
        )
        # Everyone who speaks in the recording attended, and no one else.
        speakers = {TURN.match(block).group(1) for block in SAMPLE.passages.values()}
        self.assertEqual(set(full_names), speakers)
        self.assertEqual(SAMPLE.parts(recording)[0]["author"], full_names[-1])
        # Every line under a section ends with its passage, and rests on it.
        found = dict(sections(body))
        for heading in ("Decisions", "Promises", "Detail"):
            self.assertTrue(found[heading], heading)
            for line in found[heading]:
                match = CITED.match(line)
                self.assertIsNotNone(match, line)
                text, target, marker = match.groups()
                passage = SAMPLE.passage(target, marker)
                self.assertIsNotNone(passage, line)
                self.assertEqual(not_in_passage(SAMPLE.plain(text), passage), [], line)
        # The contract's example: a promise of a proposal to Sam Rivera.
        (promise,) = found["Promises"]
        self.assertIn("proposal", promise)
        self.assertIn("|Sam Rivera]]", promise)
        self.assertIn(SAMPLE.of("decision")[0][:-3], " ".join(found["Decisions"]))

    def test_the_decision(self):
        (note,) = SAMPLE.of("decision")
        keys, body = SAMPLE.parts(note)
        ((target, marker, _),) = links(keys["source"])
        passage = SAMPLE.passage(target, marker)
        self.assertIsNotNone(passage)
        self.assertIn("decided", passage)
        self.assertEqual(keys["date"], SAMPLE.parts(SAMPLE.of("meeting")[0])[0]["date"])
        self.assertIn(SAMPLE.of("meeting")[0][:-3], body)

    def test_the_quote_is_in_its_passage_word_for_word(self):
        (note,) = SAMPLE.of("quote")
        keys, body = SAMPLE.parts(note)
        quoted = [line[2:] for line in body.split("\n") if line.startswith("> ")]
        self.assertEqual(len(quoted), 1)
        ((target, marker, _),) = links(keys["source"])
        passage = SAMPLE.passage(target, marker)
        self.assertIsNotNone(passage)
        self.assertIn(quoted[0], passage)
        # The person it is by said it, and is linked.
        self.assertTrue(passage.startswith(keys["by"] + ": "))
        self.assertIn(keys["by"], SAMPLE.names.values())
        self.assertIn("|%s]]" % keys["by"], body)
        self.assertIn("[[%s#^%s]]" % (target, marker), body)

    def test_the_concept_says_who_it_comes_from_and_the_recording_says_so_too(self):
        (note,) = SAMPLE.of("concept")
        keys, body = SAMPLE.parts(note)
        (line,) = dict(sections(body))["History"]
        _, _, _, target, marker = HISTORY.match(line).groups()
        passage = SAMPLE.passage(target, marker)
        self.assertIn(keys["from"], passage)
        self.assertIn(keys["name"], passage)

    def test_the_recording(self):
        (name,) = SAMPLE.recordings
        text = SAMPLE.text(name)
        keys, body = SAMPLE.parts(name)
        declared = declarations.sources()["meeting-recording"]
        self.assertEqual(
            [key for key, _ in raw_keys(text)], declared["required-keys"] + ["sample"])
        self.assertEqual(
            (keys["type"], keys["kind"], keys["status"], keys["starred"], keys["private"]),
            ("source", "meeting-recording", "read", "false", "false"),
        )
        self.assertEqual(finish.marker_problems(text), [])
        blocks = body.strip().split("\n\n")
        self.assertGreaterEqual(len(blocks), MIN_TURNS)
        self.assertTrue(text.endswith("\n") and not text.endswith("\n\n"))
        speakers = set()
        for number, block in enumerate(blocks, 1):
            match = TURN.match(block)
            self.assertIsNotNone(match, "block %d is not one speaker turn on one line" % number)
            self.assertEqual(match.group(3), "p%04d" % number)
            speakers.add(match.group(1))
        self.assertGreaterEqual(len(speakers), 2)
        # The hash is of the recording as it arrived, before the markers.
        arrived = "\n\n".join(re.sub(r" \^p\d{4}$", "", block) for block in blocks) + "\n"
        self.assertEqual(
            keys["sha256-original"], hashlib.sha256(arrived.encode("utf-8")).hexdigest())
        # It produced the eight objects, and nothing else.
        produced = json.loads(dict(raw_keys(text))["produced"])
        self.assertEqual(
            sorted(produced), sorted("[[%s]]" % note[:-3] for _, note in SAMPLE.objects))

    def test_the_contracts_example_is_what_the_owner_sees(self):
        self.assertEqual(SAMPLE.of("person"), ["objects/people/sam-rivera.md"])
        self.assertEqual(SAMPLE.of("company"), ["objects/companies/acme.md"])
        self.assertEqual(SAMPLE.of("term"), ["objects/terms/bespoke-systems.md"])
        self.assertEqual(
            sorted(SAMPLE.names.values())[:1] + [SAMPLE.names["objects/terms/bespoke-systems"]],
            ["Acme", "bespoke systems"],
        )
        person = SAMPLE.text("objects/people/sam-rivera.md")
        self.assertIn("| Leads operations at Acme | stated |", person)

    def test_no_sample_holds_an_em_dash_or_a_tab(self):
        for name in SAMPLE.vault.notes:
            self.assertNotIn(EM_DASH, SAMPLE.text(name), name)
            self.assertNotIn("\t", SAMPLE.text(name), name)

    def test_the_word_check_can_fail(self):
        passage = "Sam Rivera: I lead operations at Acme. ^p0002"
        self.assertEqual(not_in_passage("Leads operations at Acme", passage), [])
        self.assertEqual(not_in_passage("Leads finance at Acme", passage), ["finance"])
        self.assertEqual(not_in_passage("Sam Rivera said he leads", passage), [])


# ---- wd graph-setting ----

class GraphSetting(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = Path(scratch.name).resolve()
        self.vault = self.scratch / "vault"
        for folder in maker.folders():
            (self.vault / folder).mkdir(parents=True)
        self.settings = self.vault / ".obsidian"

    def put(self, name, values):
        self.settings.mkdir(exist_ok=True)
        text = values if isinstance(values, str) else json.dumps(values, indent=2)
        (self.settings / name).write_text(text, encoding="utf-8")

    def get(self, name):
        return json.loads((self.settings / name).read_text(encoding="utf-8"))

    def test_the_settings_are_what_the_finish_test_asks_for(self):
        graph, app = (keys for _, keys in obsidian.wanted())
        self.assertEqual(finish.graph_problems(graph, app), [])
        self.assertEqual(sorted(graph), ["colorGroups", "search"])
        self.assertEqual(
            app, {"alwaysUpdateLinks": True, "newLinkFormat": "absolute", "useMarkdownLinks": False})

    def test_one_color_for_each_object_type_by_its_home(self):
        graph = dict(obsidian.wanted())["graph.json"]
        self.assertEqual(
            [group["query"] for group in graph["colorGroups"]],
            ["path:%s" % found["home"] for found in declarations.objects().values()],
        )
        colors = []
        for group in graph["colorGroups"]:
            self.assertEqual(sorted(group), ["color", "query"])
            self.assertEqual(sorted(group["color"]), ["a", "rgb"])
            self.assertEqual(group["color"]["a"], 1)
            self.assertIsInstance(group["color"]["rgb"], int)
            self.assertTrue(0 <= group["color"]["rgb"] <= 0xFFFFFF)
            colors.append(group["color"]["rgb"])
        self.assertEqual(len(set(colors)), len(places.OBJECT_HOMES))

    def test_sources_briefs_and_the_root_files_are_hidden(self):
        search = dict(obsidian.wanted())["graph.json"]["search"]
        self.assertEqual(
            search,
            r"-path:/^sources\// -path:/^signals\/briefs\// "
            r"-path:/^AGENTS\.md$/ -path:/^CLAUDE\.md$/ -path:/^status\.md$/",
        )
        self.assertEqual(search.split(), finish.graph_filter())
        for home in places.SOURCE_HOMES:
            self.assertTrue(home.startswith("sources/"), home)

    def test_the_filter_hides_those_and_nothing_else(self):
        # The same expressions, tried on paths the way Obsidian tries
        # them. The real proof is the owner looking at the graph.
        search = dict(obsidian.wanted())["graph.json"]["search"]
        hidden = [
            "sources/recordings/2026-11-10-acme-first-meeting.md",
            "sources/links/2026-11-04-the-case-for-small-tools.md",
            "sources/sessions/2026-11-12-session.md",
            "sources/captures/2026-11-11-voice-note.md",
            "signals/briefs/2026-11-11.md",
            "AGENTS.md",
            "CLAUDE.md",
            "status.md",
        ]
        shown = [
            # Words that a plain `path:` or `file:` would match by mistake.
            "writing/project-status.md",
            "writing/resources/note.md",
            "objects/terms/status.md",
            "objects/terms/agents.md",
            "objects/people/claude.md",
            "objects/concepts/sources-of-truth.md",
            "objects/terms/sources.md",
            "writing/sources/a-note-of-mine.md",
            "writing/signals/briefs/a-note-of-mine.md",
            "writing/AGENTS.md",
            "writing/status.md",
            "status.md.md",
            "my-status.md",
            "sources.md",
            "signals/briefs.md",
            # What the graph is for.
            "signals/syntheses/2026-11-07-what-clients-say-about-price.md",
            "writing/2026-11-12.md",
        ] + [note for note in SAMPLE.vault.notes if note.startswith("objects/")]
        self.assertEqual(hidden_from_the_graph(search, hidden + shown), hidden)
        # The filter this replaced hid three notes that are meant to show.
        loose = [re.compile(words) for words in (r"sources/", r"signals/briefs/",
                                                 r"AGENTS\.md", r"CLAUDE\.md", r"status\.md")]
        wrongly = [path for path in shown if any(found.search(path) for found in loose)]
        for path in ("writing/project-status.md", "writing/resources/note.md",
                     "objects/terms/status.md"):
            self.assertIn(path, wrongly)

    def test_dry_run_says_what_would_change_and_writes_nothing(self):
        self.put("graph.json", {"search": "tag:#mine", "scale": 0.5})
        before = snapshot(self.scratch)
        code, out, err = run(["graph-setting", self.vault, "--dry-run"])
        self.assertEqual((code, err), (cli.OK, ""))
        self.assertEqual(snapshot(self.scratch), before)
        for words in ("graph.json: would change", "colorGroups", "search", "tag:#mine",
                      "app.json: would be made", "alwaysUpdateLinks", "newLinkFormat",
                      "useMarkdownLinks", "Nothing was written"):
            self.assertIn(words, out)
        self.assertNotIn("scale", out)

    def test_apply_changes_only_its_own_keys_and_keeps_every_other(self):
        graph = {
            "collapse-filter": True, "search": "tag:#mine", "showTags": False,
            "colorGroups": [{"query": "tag:#old", "color": {"a": 1, "rgb": 1}}],
            "scale": 0.5, "close": False, "nested": {"kept": [1, 2, {"deep": None}]},
        }
        app = {
            "promptDelete": False, "alwaysUpdateLinks": False, "newLinkFormat": "shortest",
            "attachmentFolderPath": "files", "useMarkdownLinks": True, "tabSize": 2,
        }
        self.put("graph.json", graph)
        self.put("app.json", app)
        self.put("appearance.json", {"theme": "obsidian"})
        others = {name: data for name, data in snapshot(self.vault).items()
                  if name not in (".obsidian/graph.json", ".obsidian/app.json")}
        code, out, err = run(["graph-setting", self.vault, "--apply"])
        self.assertEqual((code, err), (cli.OK, ""))
        for name, before in (("graph.json", graph), ("app.json", app)):
            after = self.get(name)
            owned = dict(obsidian.wanted())[name]
            self.assertEqual(list(after), list(before), "%s: the keys keep their order" % name)
            for key in before:
                self.assertEqual(after[key], owned[key] if key in owned else before[key], key)
            self.assertTrue((self.settings / name).read_text(encoding="utf-8").endswith("}\n"))
        self.assertEqual(finish.graph_problems(self.get("graph.json"), self.get("app.json")), [])
        now = snapshot(self.vault)
        self.assertEqual(
            {name: data for name, data in now.items()
             if name not in (".obsidian/graph.json", ".obsidian/app.json")},
            others, "Nothing else in the vault changes, and no temporary file is left.",
        )
        self.assertIn("graph.json: changed", out)
        self.assertIn("Every other key is kept", out)

    def test_apply_makes_the_files_when_there_are_none(self):
        code, out, err = run(["graph-setting", self.vault, "--apply"])
        self.assertEqual((code, err), (cli.OK, ""))
        for name, keys in obsidian.wanted():
            self.assertEqual(self.get(name), keys)
        self.assertEqual(sorted(path.name for path in self.settings.iterdir()),
                         ["app.json", "graph.json"])
        self.assertEqual(out.count(": made."), 2)

    def test_applying_twice_changes_nothing_the_second_time(self):
        run(["graph-setting", self.vault, "--apply"])
        stamps = {path.name: path.stat().st_mtime_ns for path in self.settings.iterdir()}
        before = snapshot(self.vault)
        code, out, _ = run(["graph-setting", self.vault, "--apply"])
        self.assertEqual(code, cli.OK)
        self.assertEqual(snapshot(self.vault), before)
        self.assertEqual(
            {path.name: path.stat().st_mtime_ns for path in self.settings.iterdir()}, stamps)
        self.assertEqual(out.count("already right"), 2)

    def test_a_one_where_true_belongs_is_put_right(self):
        self.put("app.json", {"alwaysUpdateLinks": 1, "useMarkdownLinks": 0})
        code, _, _ = run(["graph-setting", self.vault, "--apply"])
        self.assertEqual(code, cli.OK)
        self.assertIs(self.get("app.json")["alwaysUpdateLinks"], True)
        self.assertIs(self.get("app.json")["useMarkdownLinks"], False)

    def test_an_empty_settings_file_is_filled(self):
        self.put("app.json", "")
        self.put("graph.json", "{}\n")
        code, _, err = run(["graph-setting", self.vault, "--apply"])
        self.assertEqual((code, err), (cli.OK, ""))
        self.assertEqual(finish.graph_problems(self.get("graph.json"), self.get("app.json")), [])

    def test_a_settings_file_that_cannot_be_read_stops_it_before_either_is_written(self):
        for broken in ("{not json", "[1, 2]", "\"words\""):
            self.put("graph.json", {"scale": 0.5})
            self.put("app.json", broken)
            before = snapshot(self.scratch)
            for mode in ("--dry-run", "--apply"):
                code, out, err = run(["graph-setting", self.vault, mode])
                self.assertEqual(code, cli.FAILED, broken)
                self.assertEqual(out, "")
                self.assertIn("app.json", err)
                self.assertIn("left alone", err)
                self.assertEqual(snapshot(self.scratch), before, broken)

    def test_it_needs_the_vault_and_one_of_dry_run_and_apply(self):
        before = snapshot(self.scratch)
        for arguments in (
            ["graph-setting"],
            ["graph-setting", self.vault],
            ["graph-setting", "--apply"],
            ["graph-setting", self.vault, "--dry-run", "--apply"],
            ["graph-setting", self.vault, "--apply", "--force"],
            ["graph-setting", self.vault, self.vault, "--apply"],
        ):
            code, out, err = run(arguments)
            self.assertEqual(code, cli.USAGE, arguments)
            self.assertEqual(out, "")
            self.assertIn("usage: wd graph-setting <vault> --dry-run", err)
        self.assertEqual(snapshot(self.scratch), before)

    def test_a_folder_that_is_not_a_vault_is_refused(self):
        other = self.scratch / "other"
        other.mkdir()
        before = snapshot(self.scratch)
        for folder, words in ((other, "not a Workdesk vault"), (self.scratch / "gone", "no vault at")):
            code, out, err = run(["graph-setting", folder, "--apply"])
            self.assertEqual(code, cli.FAILED)
            self.assertEqual(out, "")
            self.assertIn(words, err)
        self.assertEqual(snapshot(self.scratch), before)

    def refused_as_a_link(self, link):
        """Both modes refuse, in one sentence, and nothing anywhere changes."""
        before = snapshot(self.scratch)
        for mode in ("--dry-run", "--apply"):
            code, out, err = run(["graph-setting", self.vault, mode])
            self.assertEqual(code, cli.FAILED, mode)
            self.assertEqual(out, "")
            self.assertEqual(len(err.strip().splitlines()), 1, "One plain sentence.")
            self.assertIn("%s is a link, so nothing was changed." % link, err)
            self.assertEqual(snapshot(self.scratch), before, mode)
        self.assertTrue(link.is_symlink())

    def test_a_settings_folder_that_is_a_link_is_refused(self):
        # Outside the vault, and inside it: a link is refused either way.
        for name in ("outside", "vault/kept-settings"):
            target = self.scratch / name
            target.mkdir()
            os.symlink(str(target), str(self.settings))
            self.refused_as_a_link(self.settings)
            self.assertEqual(list(target.iterdir()), [])
            self.settings.unlink()
            target.rmdir()

    def test_a_settings_file_that_is_a_link_is_refused(self):
        outside = self.scratch / "outside.json"
        for name in ("graph.json", "app.json"):
            outside.write_text("{\"scale\": 0.5}\n", encoding="utf-8")
            self.settings.mkdir(exist_ok=True)
            link = self.settings / name
            os.symlink(str(outside), str(link))
            self.refused_as_a_link(link)
            self.assertEqual(outside.read_text(encoding="utf-8"), "{\"scale\": 0.5}\n")
            # The other file was not made on the way to the refusal.
            self.assertEqual([path.name for path in self.settings.iterdir()], [name])
            link.unlink()

    def test_a_settings_file_that_is_a_link_to_nowhere_is_refused(self):
        self.settings.mkdir()
        link = self.settings / "app.json"
        os.symlink(str(self.scratch / "gone.json"), str(link))
        self.refused_as_a_link(link)
        self.assertFalse((self.scratch / "gone.json").exists())

    def test_a_file_that_changed_since_it_was_read_is_not_written(self):
        self.put("app.json", {"tabSize": 2})
        path = self.settings / "app.json"
        with self.assertRaises(obsidian.SettingError):
            obsidian.write_safely(path, b"{}\n", b"what it held before")
        with self.assertRaises(obsidian.SettingError):
            obsidian.write_safely(path, b"{}\n", None)
        with self.assertRaises(obsidian.SettingError):
            obsidian.write_safely(self.settings / "new.json", b"{}\n", b"something")
        self.assertEqual(self.get("app.json"), {"tabSize": 2})
        self.assertEqual([p.name for p in self.settings.iterdir()], ["app.json"])
        obsidian.write_safely(path, b"{}\n", path.read_bytes())
        self.assertEqual(path.read_bytes(), b"{}\n")
        self.assertEqual([p.name for p in self.settings.iterdir()], ["app.json"])

    def test_a_file_or_link_left_at_a_temporary_name_is_never_written(self):
        # The old temporary name could be guessed. Whatever sits at it,
        # or at any name like it, is left exactly as it was.
        self.put("app.json", {"tabSize": 2})
        outside = self.scratch / "outside.txt"
        outside.write_text("Not yours.\n", encoding="utf-8")
        guessed = self.settings / (".app.json.wd-%d.tmp" % os.getpid())
        os.symlink(str(outside), str(guessed))
        left = self.settings / ".graph.json.tmp"
        left.write_text("Left by something else.\n", encoding="utf-8")
        code, _, err = run(["graph-setting", self.vault, "--apply"])
        self.assertEqual((code, err), (cli.OK, ""))
        self.assertEqual(outside.read_text(encoding="utf-8"), "Not yours.\n")
        self.assertTrue(guessed.is_symlink())
        self.assertEqual(left.read_text(encoding="utf-8"), "Left by something else.\n")
        self.assertEqual(
            sorted(path.name for path in self.settings.iterdir()),
            sorted([guessed.name, left.name, "app.json", "graph.json"]),
        )
        self.assertEqual(finish.graph_problems(self.get("graph.json"), self.get("app.json")), [])

    def test_each_temporary_file_has_its_own_name_and_is_made_only_if_new(self):
        self.put("app.json", {"tabSize": 2})
        made = []
        real = tempfile.mkstemp

        def watched(*arguments, **named):
            handle, name = real(*arguments, **named)
            made.append(name)
            return handle, name

        with mock.patch.object(tempfile, "mkstemp", watched):
            run(["graph-setting", self.vault, "--apply"])
            self.put("app.json", {"tabSize": 2})
            run(["graph-setting", self.vault, "--apply"])
        self.assertEqual(len(made), 3)
        self.assertEqual(len(set(made)), 3, "No temporary name is used twice.")
        for name in made:
            self.assertEqual(Path(name).parent, self.settings)
            self.assertTrue(Path(name).name.startswith("."), name)
            self.assertFalse(Path(name).exists(), "%s was left behind" % name)

    def test_a_write_that_fails_cleans_up_only_its_own_file(self):
        self.put("app.json", {"tabSize": 2})
        other = self.settings / ".app.json.other.tmp"
        other.write_text("Someone else's.\n", encoding="utf-8")
        path = self.settings / "app.json"

        def fails(source, target):
            raise OSError("the rename failed")

        with mock.patch.object(os, "replace", fails):
            with self.assertRaises(OSError):
                obsidian.write_safely(path, b"{}\n", path.read_bytes())
        self.assertEqual(
            sorted(found.name for found in self.settings.iterdir()), [other.name, "app.json"])
        self.assertEqual(other.read_text(encoding="utf-8"), "Someone else's.\n")
        self.assertEqual(self.get("app.json"), {"tabSize": 2})

    def test_a_written_file_keeps_its_permissions_and_a_new_one_is_not_private(self):
        self.put("app.json", {"tabSize": 2})
        os.chmod(str(self.settings / "app.json"), 0o640)
        run(["graph-setting", self.vault, "--apply"])
        self.assertEqual((self.settings / "app.json").stat().st_mode & 0o777, 0o640)
        mask = os.umask(0)
        os.umask(mask)
        self.assertEqual((self.settings / "graph.json").stat().st_mode & 0o777, 0o666 & ~mask)

    def test_a_link_is_never_written_through(self):
        outside = self.scratch / "outside.json"
        outside.write_text("{}\n", encoding="utf-8")
        self.settings.mkdir()
        link = self.settings / "app.json"
        os.symlink(str(outside), str(link))
        with self.assertRaises(obsidian.SettingError):
            obsidian.write_safely(link, b"new\n", b"{}\n")
        self.assertEqual(outside.read_text(encoding="utf-8"), "{}\n")
        self.assertTrue(link.is_symlink())

    def test_the_write_goes_through_a_hidden_file_and_a_rename(self):
        self.put("app.json", {"tabSize": 2})
        seen = []
        real = os.replace

        def watched(source, target):
            seen.append((Path(source).name, Path(target).name, Path(source).parent == Path(target).parent))
            return real(source, target)

        with mock.patch.object(os, "replace", watched):
            run(["graph-setting", self.vault, "--apply"])
        self.assertEqual(sorted(target for _, target, _ in seen), ["app.json", "graph.json"])
        for source, target, same_folder in seen:
            self.assertTrue(source.startswith("."), source)
            self.assertTrue(same_folder)

    def test_a_colors_file_that_is_not_right_is_a_plain_failure(self):
        good = json.loads(obsidian.PRODUCT_FILE.read_text(encoding="utf-8"))
        self.assertEqual(sorted(good["graph-colors"]), sorted(TYPE_HOMES))
        cases = []
        missing = json.loads(json.dumps(good))
        del missing["graph-colors"]["quote"]
        cases.append((missing, "one color for each object type"))
        shared = json.loads(json.dumps(good))
        shared["graph-colors"]["quote"] = shared["graph-colors"]["person"].lower()
        cases.append((shared, "share a color"))
        wrong = json.loads(json.dumps(good))
        wrong["graph-colors"]["quote"] = "teal"
        cases.append((wrong, "the color of quote"))
        no_app = json.loads(json.dumps(good))
        no_app["app"] = {}
        cases.append((no_app, "app is not a group of settings"))
        for values, words in cases:
            path = self.scratch / "obsidian.json"
            path.write_text(json.dumps(values), encoding="utf-8")
            with mock.patch.object(obsidian, "PRODUCT_FILE", path):
                code, out, err = run(["graph-setting", self.vault, "--apply"])
            self.assertEqual(code, cli.FAILED, words)
            self.assertIn(words, err)
            self.assertFalse(self.settings.exists(), words)


# ---- the stage 1 finish test ----

class FinishTest(unittest.TestCase):
    def test_the_s13_checks_of_the_stage_1_finish_test_pass(self):
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(finish.S13Init)
        self.assertEqual(suite.countTestCases(), 3)
        result = unittest.TestResult()
        suite.run(result)
        self.assertEqual(
            [text for _, text in result.failures + result.errors], [],
            "The S1.3 checks of the stage 1 finish test do not pass.",
        )
        self.assertEqual(result.testsRun, 3)

    def test_both_commands_are_built(self):
        self.assertIn("init", cli.BUILT)
        self.assertIn("graph-setting", cli.BUILT)


if __name__ == "__main__":
    unittest.main()
