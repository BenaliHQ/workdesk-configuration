"""The `wd` entry point and the rules every program file follows."""

import ast
import importlib.util
import io
import os
import subprocess
import sys
import sysconfig
import unittest
from pathlib import Path

from wd import cli

CORE = Path(__file__).resolve().parents[1]
WD = CORE / "bin" / "wd"

# Build spec, "Commands", in its order.
SPEC_COMMANDS = [
    "check", "score", "link", "track", "fix", "find",
    "pack", "brief", "status", "tick", "install",
]


def run(arguments):
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(arguments, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


class Commands(unittest.TestCase):
    def test_the_commands_are_the_ones_in_the_build_spec(self):
        self.assertEqual([name for name, _, _ in cli.COMMANDS], SPEC_COMMANDS)

    def test_help_lists_every_command(self):
        code, out, _ = run(["--help"])
        self.assertEqual(code, cli.OK)
        for name in SPEC_COMMANDS:
            self.assertRegex(out, r"(?m)^\s*%s\b" % name)

    def test_no_command_is_a_failure(self):
        code, out, err = run([])
        self.assertEqual(code, cli.USAGE)
        self.assertEqual(out, "")
        self.assertIn("usage: wd", err)

    def test_an_unknown_command_is_a_failure(self):
        code, _, err = run(["tasks"])
        self.assertEqual(code, cli.USAGE)
        self.assertIn("no command called 'tasks'", err)

    def test_a_command_that_is_not_built_fails_and_says_so(self):
        for name, _, package in cli.COMMANDS:
            if name in cli.BUILT:
                continue
            code, out, err = run([name])
            self.assertEqual(code, cli.NOT_BUILT, name)
            self.assertEqual(out, "", name)
            self.assertIn("not built yet", err, name)
            if package:
                self.assertIn(package, err, name)

    def test_only_spec_commands_can_be_built(self):
        self.assertEqual(set(cli.BUILT) - set(SPEC_COMMANDS), set())


class EntryPoint(unittest.TestCase):
    def test_bin_wd_can_be_run_directly(self):
        self.assertTrue(os.access(str(WD), os.X_OK), "core/bin/wd is not executable.")

    def test_bin_wd_runs_and_returns_the_code(self):
        helped = subprocess.run(
            [sys.executable, str(WD), "--help"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
        )
        self.assertEqual(helped.returncode, cli.OK, helped.stderr)
        self.assertIn("usage: wd", helped.stdout)
        unbuilt = subprocess.run(
            [sys.executable, str(WD), "install"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
        )
        self.assertEqual(unbuilt.returncode, cli.NOT_BUILT)

    def test_bin_wd_works_through_a_link(self):
        # An install is reached through a `current` link.
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            link = Path(folder) / "current"
            os.symlink(str(CORE), str(link))
            result = subprocess.run(
                [sys.executable, str(link / "bin" / "wd"), "--help"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                universal_newlines=True,
            )
        self.assertEqual(result.returncode, cli.OK, result.stderr)


class StandardLibraryOnly(unittest.TestCase):
    """Build spec, "Language": Python 3, standard library only."""

    OWN = {"wd", "tests"}

    def program_files(self):
        files = [WD]
        files += sorted(
            path for path in CORE.rglob("*.py")
            if "fixtures" not in path.relative_to(CORE).parts
        )
        return files

    def imported(self, path):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names.add(node.module.split(".")[0])
        return names

    def in_standard_library(self, name):
        if name in sys.builtin_module_names:
            return True
        spec = importlib.util.find_spec(name)
        if spec is None:
            return False
        if spec.origin in ("built-in", "frozen"):
            return True
        if not spec.origin:
            return False
        origin = Path(spec.origin).resolve()
        if "site-packages" in origin.parts or "dist-packages" in origin.parts:
            return False
        homes = {
            Path(sysconfig.get_paths()[key]).resolve()
            for key in ("stdlib", "platstdlib")
        }
        return any(home in origin.parents for home in homes)

    def test_every_import_is_in_the_standard_library(self):
        outside = []
        for path in self.program_files():
            for name in sorted(self.imported(path) - self.OWN):
                if not self.in_standard_library(name):
                    outside.append("%s imports %s" % (path.relative_to(CORE), name))
        self.assertEqual(outside, [])

    def test_the_files_parse_on_the_oldest_python_we_support(self):
        # macOS ships Python 3.9. Newer grammar must not creep in.
        for path in self.program_files():
            ast.parse(
                path.read_text(encoding="utf-8"),
                filename=str(path),
                feature_version=(3, 9),
            )


if __name__ == "__main__":
    unittest.main()
