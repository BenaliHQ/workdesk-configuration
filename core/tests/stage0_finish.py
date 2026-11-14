"""Finish test for stage 0, Measure.

This file was written and committed before any stage 0 program existed,
so it fails until the stage is built. Only the operator seeing it pass
finishes the stage.

Every check names the build spec line it comes from. A check that cannot
run is reported as NOT RUN and counts as a failure. Unknown is never
healthy.

Run it through the runner:

    /usr/bin/python3 core/tests/run.py --finish 0 \
        --vault <vault> --scorecard <note> --build-log <note>

What this test expects from the packages that follow:

- `wd` reads the vault location from WD_VAULT and the machine state
  location from WD_STATE_DIR, so every program can run on a copy.
- `wd check --measure` writes `measure.json` into the state location.
- `wd score` writes `score.json` into the state location.
- The test vault's known right answers are in
  `core/tests/fixtures/answers.json`, with three parts: `cases`,
  `measure` and `score`.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CORE = Path(__file__).resolve().parents[2]
WD = CORE / "bin" / "wd"
FIXTURES = CORE / "tests" / "fixtures"
TEST_VAULT = FIXTURES / "vault"
ANSWERS = FIXTURES / "answers.json"

# Build spec, "Commands".
COMMANDS = [
    "check", "score", "link", "track", "fix", "find",
    "pack", "brief", "status", "tick", "install",
]

# Build spec, S0.2: what `wd check --measure` counts.
MEASURES = [
    "notes",
    "broken_links",
    "unlinked_objects",
    "people_without_full_name",
    "meetings_with_dead_transcript_link",
    "sources_unprocessed",
    "session_start_words",
]

# Build spec, S0.3: the twelve sources with known right answers.
CASES = [
    "clean-meeting",
    "swapped-speakers",
    "no-content",
    "invitee-absent",
    "tentative-price",
    "contradicted-decision",
    "shared-first-name",
    "private-meeting",
    "article",
    "video",
    "duplicate-person",
    "calendar-day",
]

# Build spec, S0.5: the five checks and the three allowed outcomes.
S05_CHECKS = ["a", "b", "c", "d", "e"]
S05_OUTCOMES = ("verified", "failed", "worked around")

# Build spec, "Gate to stage 1".
GATE_FULL_NAME_ACCURACY = 0.99

PRIVATE_FOLDER = "personal"
LONG_RUN_SECONDS = 3600


def file_hashes(root):
    """Hash every file under root, so a later pass can prove nothing changed."""
    root = Path(root)
    found = {}
    for folder, folders, names in os.walk(str(root)):
        folders[:] = sorted(name for name in folders if name != ".git")
        for name in sorted(names):
            path = Path(folder) / name
            relative = path.relative_to(root).as_posix()
            # Obsidian rewrites its window layout whenever the app is open.
            if relative.startswith(".obsidian/workspace"):
                continue
            if path.is_symlink():
                found[relative] = "link:" + os.readlink(str(path))
                continue
            digest = hashlib.sha256()
            try:
                with open(str(path), "rb") as handle:
                    for block in iter(lambda: handle.read(1 << 20), b""):
                        digest.update(block)
            except OSError as problem:
                found[relative] = "unreadable:" + type(problem).__name__
                continue
            found[relative] = digest.hexdigest()
    return found


def changed_files(before, after):
    return sorted(
        name
        for name in set(before) | set(after)
        if before.get(name) != after.get(name)
    )


def run_wd(arguments, vault, state):
    environment = dict(os.environ)
    environment["WD_VAULT"] = str(vault)
    environment["WD_STATE_DIR"] = str(state)
    return subprocess.run(
        [sys.executable, str(WD)] + list(arguments),
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        timeout=LONG_RUN_SECONDS,
    )


def every_key(document):
    keys = set()
    if isinstance(document, dict):
        for key, value in document.items():
            keys.add(key)
            keys |= every_key(value)
    elif isinstance(document, list):
        for value in document:
            keys |= every_key(value)
    return keys


def differences(expected, actual, where=""):
    """List every place the known right answer is missing or different."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return ["%s: expected a group of values" % (where or "top")]
        found = []
        for key, value in expected.items():
            here = "%s.%s" % (where, key) if where else key
            if key not in actual:
                found.append("%s: missing" % here)
            else:
                found.extend(differences(value, actual[key], here))
        return found
    if expected != actual:
        return ["%s: expected %r, got %r" % (where or "top", expected, actual)]
    return []


def note_type(path):
    """The `type` in a note's opening block, or None."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            return None
        if line.startswith("type:"):
            return line.split(":", 1)[1].strip()
    return None


class FinishCase(unittest.TestCase):
    maxDiff = None

    def read_json(self, path, built_by):
        if not Path(path).is_file():
            self.fail("%s is missing. It is built by %s." % (path, built_by))
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except ValueError as problem:
            self.fail("%s is not valid JSON: %s" % (path, problem))

    def answers(self, part):
        document = self.read_json(ANSWERS, "S0.3")
        if not document.get(part):
            self.fail("answers.json has no '%s' part. It is built by S0.3." % part)
        return document[part]

    def setting(self, name, what):
        value = os.environ.get(name, "").strip()
        if not value:
            self.fail("NOT RUN: %s was not given." % what)
        return Path(value).expanduser()

    def run_read_only(self, arguments, vault, state):
        """Run one command and prove the vault is the same afterwards."""
        before = file_hashes(vault)
        result = run_wd(arguments, vault, state)
        after = file_hashes(vault)
        self.assertEqual(
            changed_files(before, after), [],
            "`wd %s` changed files in the vault." % " ".join(arguments),
        )
        self.assertEqual(
            result.returncode, 0,
            "`wd %s` failed:\n%s%s"
            % (" ".join(arguments), result.stdout, result.stderr),
        )
        self.assertTrue(
            result.stdout.strip(),
            "`wd %s` printed nothing." % " ".join(arguments),
        )
        return result

    def check_measure(self, vault, state):
        self.run_read_only(["check", "--measure"], vault, state)
        report = self.read_json(Path(state) / "measure.json", "S0.2")
        missing = [name for name in MEASURES if name not in every_key(report)]
        self.assertEqual(missing, [], "measure.json leaves out: %s" % missing)
        return report

    def check_score(self, vault, state):
        self.run_read_only(["score"], vault, state)
        report = self.read_json(Path(state) / "score.json", "S0.4")
        by_type = report.get("by_type")
        self.assertTrue(by_type, "score.json has no 'by_type' part.")
        for object_type, counts in by_type.items():
            for count in ("correct", "missed"):
                self.assertIsInstance(
                    counts.get(count), int,
                    "score.json by_type.%s.%s is not a whole number."
                    % (object_type, count),
                )
        accuracy = report.get("full_name_accuracy")
        self.assertIsInstance(
            accuracy, (int, float), "score.json has no 'full_name_accuracy'."
        )
        self.assertTrue(0 <= accuracy <= 1, "full_name_accuracy is not 0 to 1.")
        scratch = report.get("scratch")
        self.assertTrue(scratch, "score.json does not say where the scratch copy was.")
        scratch = Path(scratch).resolve()
        vault = Path(vault).resolve()
        self.assertFalse(
            scratch == vault or vault in scratch.parents,
            "The scratch copy was inside the vault: %s" % scratch,
        )
        if scratch.is_dir():
            self.assertFalse(
                (scratch / PRIVATE_FOLDER).exists(),
                "The private folder was copied to the scratch folder.",
            )
        return report


class S01Skeleton(FinishCase):
    """S0.1: the `wd` entry point."""

    def test_wd_lists_every_command(self):
        result = subprocess.run(
            [sys.executable, str(WD), "--help"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in COMMANDS:
            self.assertRegex(result.stdout, r"(?m)^\s*%s\b" % command)


class S02Measure(FinishCase):
    """S0.2: `wd check --measure` is read-only and counts the right things."""

    def test_measure_on_the_test_vault(self):
        expected = self.answers("measure")
        with tempfile.TemporaryDirectory() as state:
            report = self.check_measure(TEST_VAULT, state)
        self.assertEqual(differences(expected, report), [])

    def test_the_answers_cover_every_measure(self):
        expected = self.answers("measure")
        missing = [name for name in MEASURES if name not in every_key(expected)]
        self.assertEqual(missing, [], "answers.json 'measure' leaves out: %s" % missing)


class S03TestVault(FinishCase):
    """S0.3: about 40 made-up notes and 12 sources with known right answers."""

    def test_about_forty_notes(self):
        if not TEST_VAULT.is_dir():
            self.fail("The test vault is missing. It is built by S0.3.")
        notes = [
            path for path in TEST_VAULT.rglob("*.md")
            if note_type(path) != "source"
        ]
        self.assertTrue(
            35 <= len(notes) <= 45,
            "The test vault has %d notes. The build spec says about 40." % len(notes),
        )

    def test_twelve_sources_with_known_right_answers(self):
        cases = self.answers("cases")
        self.assertEqual(sorted(cases), sorted(CASES))
        for name in CASES:
            case = cases[name]
            self.assertTrue(case.get("expect"), "%s has no right answer." % name)
            source = case.get("source")
            self.assertTrue(source, "%s names no source file." % name)
            self.assertTrue(
                (FIXTURES / source).is_file(),
                "%s points at a file that is not there: %s" % (name, source),
            )


class S04Score(FinishCase):
    """S0.4: `wd score` works on a copy outside the vault and reports by type."""

    def test_score_on_the_test_vault(self):
        expected = self.answers("score")
        with tempfile.TemporaryDirectory() as state:
            report = self.check_score(TEST_VAULT, state)
        self.assertEqual(differences(expected, report), [])


class S05FiveChecks(FinishCase):
    """S0.5: five checks, each logged as verified, failed, or worked around."""

    def test_each_check_has_an_outcome_in_the_build_log(self):
        log = self.setting("WD_FINISH_BUILD_LOG", "The build log (--build-log)")
        if not log.is_file():
            self.fail("NOT RUN: the build log is not at %s." % log)
        text = log.read_text(encoding="utf-8")
        missing = []
        for letter in S05_CHECKS:
            pattern = r"(?im)^.*S0\.5\s*\(%s\).*\b(%s)\b" % (
                letter, "|".join(S05_OUTCOMES),
            )
            if not re.search(pattern, text):
                missing.append("S0.5 (%s)" % letter)
        self.assertEqual(
            missing, [],
            "No outcome logged for: %s. Each needs a line with one of: %s."
            % (", ".join(missing), ", ".join(S05_OUTCOMES)),
        )


class YouWillSee(FinishCase):
    """Stage 0, "You will see": one scorecard note, nothing else changed."""

    def test_the_scorecard_note_exists(self):
        scorecard = self.setting("WD_FINISH_SCORECARD", "The scorecard note (--scorecard)")
        self.assertTrue(scorecard.is_file(), "No scorecard note at %s." % scorecard)
        self.assertEqual(
            scorecard.parent.name, "notes",
            "The scorecard belongs in the project's notes folder.",
        )
        self.assertTrue(
            scorecard.read_text(encoding="utf-8").strip(), "The scorecard is empty."
        )

    def test_nothing_else_in_the_vault_changed(self):
        vault = self.setting("WD_FINISH_VAULT", "The vault (--vault)")
        state = self.setting("WD_FINISH_STATE", "The machine state folder (--state)")
        if not vault.is_dir():
            self.fail("NOT RUN: there is no vault at %s." % vault)
        # Prove both commands are read-only on the test vault before they
        # are allowed near the real one.
        with tempfile.TemporaryDirectory() as practice:
            self.check_measure(TEST_VAULT, practice)
            self.check_score(TEST_VAULT, practice)
        self.check_measure(vault, state)
        self.check_score(vault, state)


class ZGateToStage1(FinishCase):
    """Gate to stage 1: right at least 99 times in 100 on full names."""

    def test_the_linker_score_on_the_vault(self):
        state = self.setting("WD_FINISH_STATE", "The machine state folder (--state)")
        report = self.read_json(state / "score.json", "S0.4, run on the vault")
        accuracy = report.get("full_name_accuracy")
        self.assertIsInstance(accuracy, (int, float))
        self.assertGreaterEqual(
            accuracy, GATE_FULL_NAME_ACCURACY,
            "The linker is right %.1f times in 100 on full names. The gate is 99."
            % (accuracy * 100),
        )


if __name__ == "__main__":
    unittest.main()
