import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('ontology', Path(__file__).parents[1] / 'migrations/manual/ontology_migrate.py')
o = importlib.util.module_from_spec(spec)
spec.loader.exec_module(o)


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'vault'
        (self.root / 'config').mkdir(parents=True)
        self.old = 'atlas/businesses/example/projects/library'
        self.new = 'atlas/businesses/example/initiatives/training/projects/library'
        for name in [self.old + '/_brief.md', self.old + '/_status.md',
                     'gtd/actions/next/task.md', 'gtd/actions/waiting/result.md',
                     'system/_processing/finding.md', 'system/log/run.log']:
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('Original bytes: ' + name)

    def tearDown(self):
        self.temp.cleanup()

    def test_migration_preserves_bytes_and_replay(self):
        plan = o.make_plan(self.root, {self.old: self.new})
        o.apply(self.root, plan, self.base / 'backup')
        self.assertEqual(o.verify(self.root, plan), [])
        self.assertTrue((self.root / self.new / 'brief.md').is_file())
        self.assertEqual(list(o.project_dirs(self.root)), [self.root / self.new])
        self.assertEqual(o.make_plan(self.root, {self.old: self.new})['moves'], [])
        self.assertTrue((self.base / 'backup/sources.tar').is_file())

    def test_collision_aborts_without_moving(self):
        (self.root / self.old / 'brief.md').write_text('Other work')
        with self.assertRaises(ValueError):
            o.make_plan(self.root, {})
        self.assertTrue((self.root / self.old / '_brief.md').is_file())

    def test_concurrent_edit_aborts(self):
        plan = o.make_plan(self.root, {})
        (self.root / self.old / '_brief.md').write_text('Newer operator work')
        with self.assertRaises(ValueError):
            o.apply(self.root, plan, self.base / 'backup')
        self.assertFalse((self.base / 'backup').exists())

    def test_unsupported_and_escaping_paths(self):
        for name in ('personal/note.md', '../outside', '/absolute'):
            with self.assertRaises(ValueError):
                o.safe(self.root, name)
        (self.root / 'gtd/escape').symlink_to(self.base)
        with self.assertRaises(ValueError):
            o.safe(self.root, 'gtd/escape/outside')

    def test_concurrent_addition_aborts(self):
        plan = o.make_plan(self.root, {self.old: self.new})
        (self.root / self.old / 'new-note.md').write_text('Concurrent note')
        with self.assertRaises(ValueError):
            o.apply(self.root, plan, self.base / 'backup')
        self.assertFalse((self.base / 'backup').exists())

    def test_archive_not_migrated(self):
        p = self.root / 'gtd/projects/_archive/old/_brief.md'
        p.parent.mkdir(parents=True)
        p.write_text('History')
        plan = o.make_plan(self.root, {})
        self.assertNotIn(str(p.relative_to(self.root)), plan['source_hashes'])


if __name__ == '__main__':
    unittest.main()
