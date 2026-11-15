"""Finish test for stage 0, Measure.

This file was written and committed before any stage 0 program existed,
so it fails until the stage is built. Only the operator seeing it pass
finishes the stage.

Changed in package S1.1, after stage 0 was built. The test vault, the
cases and the command list moved to the new vault's layout (build spec
2.0), so the checks on the test vault now run on that layout. With the
operator's approval of 2026-11-15, checks (a) and (e) are no longer
asked for here. They moved to stage 1 (S1.R2) and its finish test.

Every check names the build spec line it comes from. A check that cannot
run is reported as NOT RUN and counts as a failure. Unknown is never
healthy.

Run it through the runner:

    /usr/bin/python3 core/tests/run.py --finish 0 \
        --vault <vault> --scorecard <note> --build-log <note>

What the packages that follow must meet. The build spec fixes the first
two. The rest are choices this test had to make because it was written
first.

Commands and places

- `wd check --measure <vault>` and `wd score <vault>` take the vault as
  their argument (build spec, "Commands").
- The twelve cases are in `core/tests/fixtures/cases/<nn>-<slug>/`, each
  with an `input/` folder and an `expected.json` (build spec, "Where
  things live").
- `wd` reads the machine state location from WD_STATE_DIR, so a test can
  point it at a scratch folder. It finds the user's own instruction
  files through HOME.
- `core/tests/fixtures/home/` is a made-up home folder with Claude Code
  and Codex instructions, rules and skills. Runs on the test vault use
  it, so session load is the same on every machine.

`measure.json`, written into machine state by `wd check --measure`

- `vault`: the vault that was measured, as a full path.
- `run_at`: when, as local time with its offset, 2026-11-12T07:00:00-06:00.
- `notes`: a whole number for each home.
- `broken_links`, `unlinked_objects`, `people_without_full_name`,
  `meetings_with_missing_source`, `sources_unprocessed`: whole numbers.
  Since S1.1 a source counts as unprocessed when its `produced` list is
  empty.
- `session_load`: words for `claude-code` and for `codex`.

`score.json`, written into machine state by `wd score`

- `vault` and `run_at`, as above.
- `by_type`: for each object type, `correct`, `wrong` and `missed`.
  The scorer takes each existing link whose shown words are a name of
  two words or more and strips its brackets. `correct`: the matcher
  linked that spot to the same object. `wrong`: it linked that spot to
  a different object. `missed`: it left that spot unlinked.
- `right_rate`: correct / (correct + wrong), over all types.
- `miss_rate`: missed / (correct + wrong + missed), over all types.
- `scratch`: the scratch copy, a folder under machine state. It is left
  in place after the run.

Known right answers

- `core/tests/fixtures/answers.json` has a `measure` part with every
  measure above for the test vault, and a `score` part with `by_type`.
- Each case's `expected.json` has an `exists` part and an `absent`
  part. Each part has three lists: `objects`, `links` and `history`.

The checks in the build log (S0.5)

One line for each check. Checks (b) and (c) have one line for each
runtime. A check that was run again counts by its last line. Checks (a)
and (e) are logged the same way, and are read by stage 1's finish test.

    S0.5 (d): verified. Evidence: <what was done and seen>.
    S0.5 (b) Claude Code: failed. Evidence: <...>. Consequence: <...>.
    S0.5 (b) Codex: verified. Evidence: <...>.

The outcome is `verified`, `failed` or `worked around`. Anything but
`verified` also needs its consequence from the build spec's table.

The scorecard (S0.6)

`notes/core-stage-0-scorecard.md`, beside the build log. It shows the
date of the run as 2026-11-12 and every number from the two reports of
that run, which stay in machine state.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CORE = Path(__file__).resolve().parents[1]
WD = CORE / "bin" / "wd"
FIXTURES = CORE / "tests" / "fixtures"
TEST_VAULT = FIXTURES / "vault"
FIXTURE_HOME = FIXTURES / "home"
CASES_HOME = FIXTURES / "cases"
ANSWERS = FIXTURES / "answers.json"

# Build spec, "Commands". Version 2.0 dropped `names` and
# `repair-sources` and added `init`, `add` and `process`.
COMMANDS = [
    "init", "check", "score", "status", "graph-setting", "add", "process", "link",
    "track", "fix", "find", "pack", "brief", "tick", "install",
]

# Build spec, "Measure fields", in its order.
COUNTS = [
    "broken_links",
    "unlinked_objects",
    "people_without_full_name",
    "meetings_with_missing_source",
    "sources_unprocessed",
]
RUNTIMES = ("claude-code", "codex")
MEASURES = ["notes"] + COUNTS + ["session_load"]

# Build spec, S0.4.
SCORE_COUNTS = ("correct", "wrong", "missed")

# Build spec, "The 12 cases", in its order.
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
CASE_PARTS = ("exists", "absent")
CASE_KINDS = ("objects", "links", "history")

# Build spec, S0.5: the checks and the three allowed outcomes. Checks (a)
# and (e) moved to stage 1 (S1.R2), so stage 0 asks for (b), (c) and (d).
# The line format still covers all five letters.
S05_CHECKS = ["b", "c", "d"]
S05_PER_RUNTIME = ("b", "c")
S05_RUNTIMES = ("Claude Code", "Codex")
S05_LINE = re.compile(
    r"^[ \t>*-]*S0\.5 \(([a-e])\)(?: (Claude Code|Codex))?: "
    r"(verified|failed|worked around)\.(.*)$",
    re.MULTILINE,
)

# Build spec, "Gate to stage 1": right at least 99 times in 100, and
# misses at most 1 in 100, on the test vault.
GATE_RIGHT_RATE = 0.99
GATE_MISS_RATE = 0.01

# Build spec, S0.6.
SCORECARD_NAME = "core-stage-0-scorecard.md"

# The operator's own folder in the new vault's layout. The scorer never opens it.
PRIVATE_FOLDER = "writing"
CANARY = "wd-finish-canary-7f3a91c2"
LONG_RUN_SECONDS = 3600

# Left out of every before-and-after comparison, and so not covered by
# "nothing else changed": the vault's own git folder, and the window
# layout Obsidian rewrites whenever the app is open.
SKIPPED_FOLDERS = (".git",)
VOLATILE_FILES = (".obsidian/workspace",)

STAMP = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")


def snapshot(root):
    """Hash every file under root. Returns the hashes and what could not be read."""
    root = Path(root)
    found, problems = {}, []

    def could_not_open(problem):
        problems.append(
            "could not open %s: %s" % (problem.filename, type(problem).__name__)
        )

    for folder, folders, names in os.walk(str(root), onerror=could_not_open):
        folders[:] = sorted(name for name in folders if name not in SKIPPED_FOLDERS)
        for name in sorted(names):
            path = Path(folder) / name
            relative = path.relative_to(root).as_posix()
            if relative.startswith(VOLATILE_FILES):
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
                problems.append(
                    "could not read %s: %s" % (relative, type(problem).__name__)
                )
                continue
            found[relative] = digest.hexdigest()
    return found, problems


def changed_files(before, after):
    return sorted(
        name
        for name in set(before) | set(after)
        if before.get(name) != after.get(name)
    )


def whole(value):
    """A count: a whole number, zero or more. True and False are not counts."""
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def stamp_problems(report, vault):
    """Does the report say which vault it measured, and when?"""
    problems = []
    named = report.get("vault") if isinstance(report, dict) else None
    if not isinstance(named, str) or not named:
        problems.append("vault: the report does not say which vault it measured")
    elif Path(named).resolve() != Path(vault).resolve():
        problems.append("vault: the report is for %s, not %s" % (named, vault))
    run_at = report.get("run_at") if isinstance(report, dict) else None
    if not isinstance(run_at, str) or not STAMP.match(run_at):
        problems.append("run_at: expected a time like 2026-11-12T07:00:00-06:00")
    return problems


def measure_problems(report):
    """Everything wrong with the shape of a measure report."""
    if not isinstance(report, dict):
        return ["the report is not a group of values"]
    problems = []
    notes = report.get("notes")
    if not isinstance(notes, dict) or not notes:
        problems.append("notes: expected a count for each home")
    else:
        for home, count in sorted(notes.items()):
            if not whole(count):
                problems.append("notes.%s: not a count" % home)
    for name in COUNTS:
        if not whole(report.get(name)):
            problems.append("%s: not a count" % name)
    load = report.get("session_load")
    for runtime in RUNTIMES:
        if not isinstance(load, dict) or not whole(load.get(runtime)):
            problems.append("session_load.%s: not a count" % runtime)
    return problems


def by_type_problems(by_type):
    if not isinstance(by_type, dict) or not by_type:
        return ["by_type: expected counts for each object type"]
    problems = []
    for object_type, counts in sorted(by_type.items()):
        for name in SCORE_COUNTS:
            if not isinstance(counts, dict) or not whole(counts.get(name)):
                problems.append("by_type.%s.%s: not a count" % (object_type, name))
    return problems


def rates(by_type):
    """The two gate numbers, worked out from the counts.

    Returns (right rate, miss rate, None), or (None, None, why not).
    """
    correct, wrong, missed = (
        sum(counts[name] for counts in by_type.values()) for name in SCORE_COUNTS
    )
    if correct + wrong + missed == 0:
        return None, None, "no links were scored, so the gate cannot be judged"
    if correct + wrong == 0:
        return None, None, "the matcher made no links, so it was never right"
    return (
        correct / float(correct + wrong),
        missed / float(correct + wrong + missed),
        None,
    )


def score_problems(report):
    """Everything wrong with a score report, apart from where its scratch copy is."""
    if not isinstance(report, dict):
        return ["the report is not a group of values"]
    problems = by_type_problems(report.get("by_type"))
    if problems:
        return problems
    right, miss, why_not = rates(report["by_type"])
    if why_not:
        return [why_not]
    for name, worked_out in (("right_rate", right), ("miss_rate", miss)):
        reported = report.get(name)
        if isinstance(reported, bool) or not isinstance(reported, (int, float)):
            problems.append("%s: not a number" % name)
        elif abs(reported - worked_out) > 1e-6:
            problems.append(
                "%s: the report says %r but the counts give %r"
                % (name, reported, worked_out)
            )
    return problems


def case_problems(expected):
    """Everything wrong with one case's expected.json."""
    if not isinstance(expected, dict):
        return ["not a group of values"]
    problems, listed = [], 0
    for part in CASE_PARTS:
        group = expected.get(part)
        if not isinstance(group, dict):
            problems.append("%s: expected objects, links and history" % part)
            continue
        for kind in CASE_KINDS:
            entries = group.get(kind)
            if not isinstance(entries, list):
                problems.append("%s.%s: expected a list" % (part, kind))
                continue
            for entry in entries:
                named = isinstance(entry, str) and entry.strip()
                described = isinstance(entry, dict) and entry
                if not (named or described):
                    problems.append("%s.%s: an entry says nothing" % (part, kind))
            listed += len(entries)
        for extra in sorted(set(group) - set(CASE_KINDS)):
            problems.append("%s.%s: not objects, links or history" % (part, extra))
    if not problems and not listed:
        problems.append("lists nothing that must exist or be absent")
    return problems


def said_enough(rest, label, until=None):
    """Are there at least three words after `label:` on the line?"""
    pattern = r"%s: (.+?)(?= %s: |$)" % (label, until) if until else r"%s: (.+)$" % label
    found = re.search(pattern, rest)
    return bool(found) and len(found.group(1).split()) >= 3


def s05_problems(text):
    """Everything missing from the build log's record of checks (b), (c) and (d)."""
    latest = {}
    for match in S05_LINE.finditer(text):
        letter, runtime, outcome, rest = match.groups()
        latest[(letter, runtime)] = (outcome, rest)
    problems = []
    for letter in S05_CHECKS:
        runtimes = S05_RUNTIMES if letter in S05_PER_RUNTIME else (None,)
        for runtime in runtimes:
            label = "S0.5 (%s)%s" % (letter, " " + runtime if runtime else "")
            if (letter, runtime) not in latest:
                problems.append("%s: no outcome logged" % label)
                continue
            outcome, rest = latest[(letter, runtime)]
            if not said_enough(rest, "Evidence", until="Consequence"):
                problems.append("%s: no evidence given" % label)
            if outcome != "verified" and not said_enough(rest, "Consequence"):
                problems.append("%s: %s, with no consequence given" % (label, outcome))
    outcomes = [latest.get(("b", runtime), ("", ""))[0] for runtime in S05_RUNTIMES]
    if all(outcome == "failed" for outcome in outcomes):
        problems.append(
            "S0.5 (b): the model step failed in both runtimes. "
            "The build spec says stop and ask the operator."
        )
    return problems


def has_number(text, number):
    """Is this number written in the text, with or without thousands commas?"""
    plain = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    return re.search(r"(?<![\d.])%d(?!\d|\.\d)" % number, plain) is not None


def scorecard_problems(text, measure, score):
    """Every number from the two reports that the scorecard leaves out."""
    wanted = [("the date of the run", None)]
    wanted += [("notes in %s" % home, count) for home, count in sorted(measure["notes"].items())]
    wanted += [(name, measure[name]) for name in COUNTS]
    wanted += [
        ("session load, %s" % runtime, measure["session_load"][runtime])
        for runtime in RUNTIMES
    ]
    for object_type, counts in sorted(score["by_type"].items()):
        wanted += [
            ("%s links %s" % (object_type, name), counts[name]) for name in SCORE_COUNTS
        ]
    problems = []
    for label, number in wanted:
        if number is None:
            if measure["run_at"][:10] not in text:
                problems.append("%s (%s)" % (label, measure["run_at"][:10]))
        elif not has_number(text, number):
            problems.append("%s (%d)" % (label, number))
    return problems


def note_count(vault):
    return len(list(Path(vault).rglob("*.md")))


class FinishCase(unittest.TestCase):
    maxDiff = None

    def read_json(self, path, built_by):
        if not Path(path).is_file():
            self.fail("%s is missing. It is built by %s." % (path, built_by))
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except ValueError as problem:
            self.fail("%s is not valid JSON: %s" % (path, problem))

    def answers(self, part, built_by):
        document = self.read_json(ANSWERS, built_by)
        if not isinstance(document, dict) or not document.get(part):
            self.fail(
                "answers.json has no '%s' part. It is built by %s." % (part, built_by)
            )
        return document[part]

    def setting(self, name, what):
        value = os.environ.get(name, "").strip()
        if not value:
            self.fail("NOT RUN: %s was not given." % what)
        return Path(value).expanduser()

    def environment(self, state, made_up_home):
        environment = dict(os.environ)
        environment["WD_STATE_DIR"] = str(state)
        if made_up_home:
            if not FIXTURE_HOME.is_dir():
                self.fail("The made-up home folder is missing. It is built by S0.2.")
            # Nothing from the real user may leak into a run on the test vault.
            for name in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "XDG_CONFIG_HOME",
                         "XDG_DATA_HOME", "XDG_STATE_HOME"):
                environment.pop(name, None)
            environment["HOME"] = str(FIXTURE_HOME)
        return environment

    def snapshot(self, vault):
        found, problems = snapshot(vault)
        self.assertEqual(
            problems, [],
            "NOT RUN: parts of the vault could not be read, so nothing can be "
            "said about whether it changed.",
        )
        return found

    def run_read_only(self, arguments, vault, state, made_up_home):
        """Run one command on a vault and prove the vault is the same afterwards."""
        shown = "wd %s <vault>" % " ".join(arguments)
        environment = self.environment(state, made_up_home)
        before = self.snapshot(vault)
        result = subprocess.run(
            [sys.executable, str(WD)] + list(arguments) + [str(vault)],
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=LONG_RUN_SECONDS,
        )
        after = self.snapshot(vault)
        self.assertEqual(
            changed_files(before, after), [],
            "`%s` changed files in the vault." % shown,
        )
        self.assertEqual(
            result.returncode, 0,
            "`%s` failed:\n%s%s" % (shown, result.stdout, result.stderr),
        )
        self.assertTrue(result.stdout.strip(), "`%s` printed nothing." % shown)
        return result

    def check_measure(self, vault, state, made_up_home):
        self.run_read_only(["check", "--measure"], vault, state, made_up_home)
        report = self.read_json(Path(state) / "measure.json", "S0.2")
        self.assertEqual(measure_problems(report), [], "measure.json is not right.")
        self.assertEqual(stamp_problems(report, vault), [], "measure.json is not right.")
        return report

    def check_score(self, vault, state, made_up_home):
        result = self.run_read_only(["score"], vault, state, made_up_home)
        report = self.read_json(Path(state) / "score.json", "S0.4")
        self.assertEqual(score_problems(report), [], "score.json is not right.")
        self.assertEqual(stamp_problems(report, vault), [], "score.json is not right.")
        scratch = report.get("scratch")
        self.assertTrue(
            isinstance(scratch, str) and scratch,
            "score.json does not say where the scratch copy was.",
        )
        scratch = Path(scratch).resolve()
        self.assertIn(
            Path(state).resolve(), scratch.parents,
            "The scratch copy is not under machine state: %s" % scratch,
        )
        self.assertTrue(scratch.is_dir(), "There is no scratch copy at %s." % scratch)
        self.assertEqual(
            [path for path in scratch.rglob(PRIVATE_FOLDER)], [],
            "The private folder was copied to the scratch folder.",
        )
        return report, result


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
            self.assertRegex(result.stdout, r"(?m)^\s*%s(\s|$)" % re.escape(command))


class S02Measure(FinishCase):
    """S0.2: `wd check --measure` is read-only and counts the right things."""

    def test_the_answers_cover_every_measure(self):
        expected = self.answers("measure", "S0.2 and S0.3")
        self.assertEqual(
            measure_problems(expected), [], "answers.json 'measure' is not complete."
        )

    def test_measure_on_the_test_vault(self):
        expected = self.answers("measure", "S0.2 and S0.3")
        with tempfile.TemporaryDirectory() as state:
            report = self.check_measure(TEST_VAULT, state, made_up_home=True)
        self.assertEqual(
            {name: report.get(name) for name in MEASURES},
            {name: expected.get(name) for name in MEASURES},
        )


class S03TestVault(FinishCase):
    """S0.3: about 40 made-up notes and 12 cases with known right answers."""

    def test_about_forty_notes(self):
        if not TEST_VAULT.is_dir():
            self.fail("The test vault is missing. It is built by S0.3.")
        count = note_count(TEST_VAULT)
        self.assertTrue(
            35 <= count <= 45,
            "The test vault has %d notes. The build spec says about 40." % count,
        )

    def test_twelve_cases_with_known_right_answers(self):
        if not CASES_HOME.is_dir():
            self.fail("The cases folder is missing. It is built by S0.3.")
        wanted = ["%02d-%s" % (number, name) for number, name in enumerate(CASES, 1)]
        found = sorted(path.name for path in CASES_HOME.iterdir() if path.is_dir())
        self.assertEqual(found, wanted)
        for name in wanted:
            case = CASES_HOME / name
            given = case / "input"
            self.assertTrue(
                given.is_dir() and any(path.is_file() for path in given.rglob("*")),
                "%s has nothing in its input folder." % name,
            )
            expected = self.read_json(case / "expected.json", "S0.3")
            self.assertEqual(
                case_problems(expected), [], "%s: expected.json is not right." % name
            )


class S04Score(FinishCase):
    """S0.4: `wd score` works on a copy under machine state and reports by type."""

    def expected_by_type(self):
        expected = self.answers("score", "S0.3 and S0.4")
        by_type = expected.get("by_type") if isinstance(expected, dict) else None
        self.assertEqual(
            by_type_problems(by_type), [], "answers.json 'score' is not complete."
        )
        return by_type

    def test_score_on_the_test_vault(self):
        by_type = self.expected_by_type()
        with tempfile.TemporaryDirectory() as state:
            report, _ = self.check_score(TEST_VAULT, state, made_up_home=True)
        self.assertEqual(report["by_type"], by_type)

    def test_the_scorer_never_reads_the_private_folder(self):
        by_type = self.expected_by_type()
        if not TEST_VAULT.is_dir():
            self.fail("The test vault is missing. It is built by S0.3.")
        with tempfile.TemporaryDirectory() as folder:
            vault = Path(folder) / "vault"
            state = Path(folder) / "state"
            state.mkdir()
            shutil.copytree(
                str(TEST_VAULT), str(vault),
                ignore=shutil.ignore_patterns(PRIVATE_FOLDER),
            )
            # A private folder holding a copy of every note, so a scorer
            # that reads it counts every link twice, and one marked note.
            private = vault / PRIVATE_FOLDER
            (private / "copies").mkdir(parents=True)
            for number, note in enumerate(sorted(TEST_VAULT.rglob("*.md"))):
                if PRIVATE_FOLDER in note.relative_to(TEST_VAULT).parts:
                    continue
                shutil.copyfile(
                    str(note), str(private / "copies" / ("%03d-%s" % (number, note.name)))
                )
            (private / "marked.md").write_text("# Marked\n\n%s\n" % CANARY, encoding="utf-8")

            report, result = self.check_score(vault, state, made_up_home=True)
            self.assertEqual(
                report["by_type"], by_type,
                "The counts changed when a private folder was added.",
            )
            self.assertNotIn(CANARY, result.stdout + result.stderr)
            leaked = [
                path.relative_to(state).as_posix()
                for path in state.rglob("*")
                if path.is_file() and CANARY.encode() in path.read_bytes()
            ]
            self.assertEqual(leaked, [], "Private words reached machine state.")


class S05FiveChecks(FinishCase):
    """S0.5: each check with an outcome, its evidence and its consequence.

    Three of the five are asked for here. Checks (a) and (e) are stage 1's.
    """

    def test_each_check_is_in_the_build_log(self):
        log = self.setting("WD_FINISH_BUILD_LOG", "The build log (--build-log)")
        if not log.is_file():
            self.fail("NOT RUN: the build log is not at %s." % log)
        self.assertEqual(s05_problems(log.read_text(encoding="utf-8")), [])


class YouWillSee(FinishCase):
    """Stage 0, "You will see": the scorecard, and nothing else changed.

    "Nothing else changed" is proven for the two commands: every file in
    the vault is hashed before and after each. The vault's git folder
    and Obsidian's window layout are left out.
    """

    def test_nothing_else_in_the_vault_changed(self):
        vault = self.setting("WD_FINISH_VAULT", "The vault (--vault)")
        if not vault.is_dir():
            self.fail("NOT RUN: there is no vault at %s." % vault)
        # Prove both commands are read-only on the test vault before they
        # are allowed near the real one.
        with tempfile.TemporaryDirectory() as practice:
            self.check_measure(TEST_VAULT, practice, made_up_home=True)
            self.check_score(TEST_VAULT, practice, made_up_home=True)
        # A scratch state folder, so the reports the scorecard was
        # written from stay as they are.
        with tempfile.TemporaryDirectory() as state:
            self.check_measure(vault, state, made_up_home=False)
            self.check_score(vault, state, made_up_home=False)

    def test_the_scorecard_shows_the_numbers(self):
        scorecard = self.setting("WD_FINISH_SCORECARD", "The scorecard note (--scorecard)")
        log = self.setting("WD_FINISH_BUILD_LOG", "The build log (--build-log)")
        vault = self.setting("WD_FINISH_VAULT", "The vault (--vault)")
        state = self.setting("WD_FINISH_STATE", "The machine state folder (--state)")
        self.assertTrue(scorecard.is_file(), "No scorecard note at %s." % scorecard)
        self.assertEqual(
            scorecard.name, SCORECARD_NAME,
            "The scorecard is notes/%s in the project." % SCORECARD_NAME,
        )
        self.assertEqual(
            scorecard.resolve().parent, log.resolve().parent,
            "The scorecard belongs beside the build log, in the project's notes.",
        )
        self.assertIn(
            vault.resolve(), scorecard.resolve().parents,
            "The scorecard is not inside the vault.",
        )
        # The reports of the S0.6 run. They must be for this vault.
        measure = self.read_json(state / "measure.json", "S0.6")
        score = self.read_json(state / "score.json", "S0.6")
        self.assertEqual(measure_problems(measure) + stamp_problems(measure, vault), [])
        self.assertEqual(score_problems(score) + stamp_problems(score, vault), [])
        missing = scorecard_problems(
            scorecard.read_text(encoding="utf-8"), measure, score
        )
        self.assertEqual(missing, [], "The scorecard leaves out numbers from the run.")


class ZGateToStage1(FinishCase):
    """Gate to stage 1, on the test vault."""

    def test_the_scorer_on_the_test_vault(self):
        with tempfile.TemporaryDirectory() as state:
            report, _ = self.check_score(TEST_VAULT, state, made_up_home=True)
        right, miss, why_not = rates(report["by_type"])
        self.assertIsNone(why_not, why_not)
        self.assertGreaterEqual(
            right, GATE_RIGHT_RATE,
            "The scorer is right %.1f times in 100. The gate is at least 99."
            % (right * 100),
        )
        self.assertLessEqual(
            miss, GATE_MISS_RATE,
            "The scorer misses %.1f in 100. The gate is at most 1." % (miss * 100),
        )


if __name__ == "__main__":
    unittest.main()
