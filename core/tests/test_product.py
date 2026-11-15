"""What a new vault is given: the one rulebook and the four skills.

The files live in `core/product/`. This test holds their limits:

- The rulebook exists and is 1,200 words at most.
- `CLAUDE.md` is one line that loads the rulebook.
- The skills are exactly the four the contract names. Each has a
  `name` equal to its folder and a `description` of 40 words at most.
- None of these files holds an em dash.
- None names a folder that is not in the build spec's folder list, or
  a command that is not in its command list.

A word is counted as the budget test counts it: anything with a letter
or a digit in it.
"""

import json
import re
import unittest
from pathlib import Path

CORE = Path(__file__).resolve().parents[1]
PRODUCT = CORE / "product"
RULEBOOK = PRODUCT / "AGENTS.md"
LOADER = PRODUCT / "CLAUDE.md"
SKILLS = PRODUCT / "skills"
LIMITS = json.loads((CORE / "budgets.json").read_text(encoding="utf-8"))

# Build spec, stage 1, package S1.2.
RULEBOOK_MAX_WORDS = 1200
DESCRIPTION_MAX_WORDS = 40

# The contract, "The parts": four skills.
SKILL_NAMES = ["context", "correct", "status", "track"]

# Build spec, "The new vault's folders", in its order.
FOLDERS = [
    "sources/",
    "sources/recordings/",
    "sources/links/",
    "sources/sessions/",
    "sources/captures/",
    "objects/",
    "objects/people/",
    "objects/companies/",
    "objects/projects/",
    "objects/terms/",
    "objects/concepts/",
    "objects/meetings/",
    "objects/decisions/",
    "objects/quotes/",
    "writing/",
    "signals/",
    "signals/briefs/",
    "signals/syntheses/",
]
ROOT_FILES = ["AGENTS.md", "CLAUDE.md", "status.md"]
HIDDEN_FOLDERS = [".obsidian/", ".claude/skills/", ".agents/skills/"]

# Build spec, "Commands".
COMMANDS = {
    "init", "check", "score", "status", "graph-setting", "add", "process",
    "link", "track", "fix", "find", "pack", "brief", "tick", "install",
}

EM_DASH = chr(0x2014)
HAS_LETTER_OR_DIGIT = re.compile(r"[^\W_]")
# A folder as it is written in a note: one or more names, each ending
# in a slash. A file name after the last slash is not part of it.
FOLDER = re.compile(r"(?<![\w/.-])(?:\.?[A-Za-z0-9_][\w.-]*/)+")
COMMAND = re.compile(r"`wd ([a-z][a-z-]*)")


def words(text):
    return [word for word in text.split() if HAS_LETTER_OR_DIGIT.search(word)]


def header(text):
    """The keys in the header block at the top of a skill, and the rest.

    Each line of the block is `key: value` on one line. That is all a
    skill needs, so that is all this reads.
    """
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("The file does not start with a header block.")
    keys = {}
    for number, line in enumerate(lines[1:], start=1):
        if line == "---":
            return keys, "\n".join(lines[number + 1:])
        key, colon, value = line.partition(":")
        if not colon or not key.strip() or key != key.strip():
            raise ValueError("Not a `key: value` line: %r" % line)
        if key in keys:
            raise ValueError("The key %r is there twice." % key)
        keys[key] = value.strip()
    raise ValueError("The header block is not closed.")


def folders_named(text):
    return sorted(set(FOLDER.findall(text)))


def folder_map(text):
    """The first cell of each row of the table under "The folders"."""
    found, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip() == "The folders"
            continue
        if not inside or not line.startswith("|"):
            continue
        cell = line.strip().strip("|").split("|")[0].strip()
        if cell.startswith("`") and cell.endswith("`"):
            found.append(cell.strip("`"))
    return found


def product_notes():
    return sorted(PRODUCT.rglob("*.md"))


def read(path):
    return path.read_text(encoding="utf-8")


SAMPLE_SKILL = """---
name: sample
description: Use when a test needs one. It has a colon: here.
---

# Sample

Body with `objects/people/` and `wd find <name>`.
"""


class Reading(unittest.TestCase):
    def test_words_are_counted_as_the_budget_test_counts_them(self):
        self.assertEqual(words("| a | b |\n|---|---|\n- one `wd fix`"),
                         ["a", "b", "one", "`wd", "fix`"])

    def test_the_header_block_is_read(self):
        keys, rest = header(SAMPLE_SKILL)
        self.assertEqual(keys, {
            "name": "sample",
            "description": "Use when a test needs one. It has a colon: here.",
        })
        self.assertTrue(rest.strip().startswith("# Sample"))

    def test_a_broken_header_block_is_refused(self):
        for text in ("# No block", "---\nname: open\n", "---\njust words\n---\n",
                     "---\nname: a\nname: b\n---\n", "---\n  name: a\n---\n"):
            with self.assertRaises(ValueError):
                header(text)

    def test_folders_are_found_where_they_are_written(self):
        self.assertEqual(
            folders_named("`objects/people/` [[sources/links/a-note#^p0001]] "
                          "`.claude/skills/` and `status.md` 2026-11-12"),
            [".claude/skills/", "objects/people/", "sources/links/"],
        )


class Rulebook(unittest.TestCase):
    def setUp(self):
        self.assertTrue(RULEBOOK.is_file(), "There is no rulebook at %s." % RULEBOOK)
        self.text = read(RULEBOOK)

    def test_it_is_within_its_word_limit(self):
        count = len(words(self.text))
        print("\n    words in the rulebook: %d of %d" % (count, RULEBOOK_MAX_WORDS))
        self.assertGreater(count, 0)
        self.assertLessEqual(count, RULEBOOK_MAX_WORDS)

    def test_it_has_no_header_block(self):
        # A session loads the page as it is, so every line of it counts.
        self.assertTrue(self.text.startswith("# "))

    def test_its_map_is_the_build_specs_folder_list(self):
        self.assertEqual(folder_map(self.text), FOLDERS + ROOT_FILES)

    def test_it_names_the_hidden_folders(self):
        for folder in HIDDEN_FOLDERS:
            self.assertIn("`%s`" % folder, self.text)


class Loader(unittest.TestCase):
    def test_claude_md_is_the_one_line_that_loads_the_rulebook(self):
        self.assertTrue(LOADER.is_file(), "There is no file at %s." % LOADER)
        self.assertEqual(read(LOADER), "@AGENTS.md\n")


class Skills(unittest.TestCase):
    def test_the_skills_are_exactly_the_four(self):
        self.assertEqual(len(SKILL_NAMES), LIMITS["Skills"])
        folders = sorted(path.name for path in SKILLS.iterdir() if path.is_dir())
        self.assertEqual(folders, SKILL_NAMES)
        for name in SKILL_NAMES:
            self.assertTrue((SKILLS / name / "SKILL.md").is_file(), name)

    def test_each_name_is_its_folder(self):
        for name in SKILL_NAMES:
            keys, _ = header(read(SKILLS / name / "SKILL.md"))
            self.assertEqual(sorted(keys), ["description", "name"], name)
            self.assertEqual(keys["name"], name)

    def test_each_description_is_within_its_word_limit(self):
        for name in SKILL_NAMES:
            keys, _ = header(read(SKILLS / name / "SKILL.md"))
            description = keys["description"]
            count = len(words(description))
            print("\n    words in the description of %s: %d of %d"
                  % (name, count, DESCRIPTION_MAX_WORDS))
            self.assertGreater(count, 0, name)
            self.assertLessEqual(count, DESCRIPTION_MAX_WORDS, name)

    def test_each_description_is_plain_text_on_one_line(self):
        # No colon and no quote mark, so every reader of the header
        # block sees the same words this test counted.
        for name in SKILL_NAMES:
            keys, _ = header(read(SKILLS / name / "SKILL.md"))
            for mark in (":", '"', "#"):
                self.assertNotIn(mark, keys["description"], name)
            self.assertNotIn(keys["description"][0], "'[{>|*&!%@`", name)

    def test_each_body_says_what_to_do_when_a_command_is_not_built(self):
        for name in SKILL_NAMES:
            _, rest = header(read(SKILLS / name / "SKILL.md"))
            self.assertIn("not built yet", rest, name)
            self.assertIn("one plain sentence", rest, name)


class EveryFile(unittest.TestCase):
    def test_the_files_are_there(self):
        notes = product_notes()
        for path in [RULEBOOK, LOADER] + [SKILLS / name / "SKILL.md"
                                          for name in SKILL_NAMES]:
            self.assertIn(path, notes)

    def test_no_file_holds_an_em_dash(self):
        for path in product_notes():
            self.assertNotIn(EM_DASH, read(path), str(path.relative_to(CORE)))

    def test_no_file_names_a_folder_outside_the_list(self):
        known = set(FOLDERS) | set(HIDDEN_FOLDERS)
        for path in [RULEBOOK] + [SKILLS / name / "SKILL.md" for name in SKILL_NAMES]:
            unknown = [folder for folder in folders_named(read(path))
                       if folder not in known]
            self.assertEqual(unknown, [], str(path.relative_to(CORE)))

    def test_no_file_names_a_command_outside_the_list(self):
        for path in [RULEBOOK] + [SKILLS / name / "SKILL.md" for name in SKILL_NAMES]:
            named = set(COMMAND.findall(read(path)))
            self.assertEqual(named - COMMANDS, set(), str(path.relative_to(CORE)))


if __name__ == "__main__":
    unittest.main()
