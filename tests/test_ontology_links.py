import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('links', Path(__file__).parents[1] / 'migrations/manual/ontology_links.py')
links = importlib.util.module_from_spec(spec)
spec.loader.exec_module(links)


class LinkTests(unittest.TestCase):
    def test_links_anchors_spaces_and_historical_exclusions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            old = 'gtd/projects/demo/_brief.md'
            new = 'gtd/projects/demo/brief.md'
            p = root / old
            p.parent.mkdir(parents=True)
            p.write_text('Original brief')
            note = root / 'atlas/meetings/test.md'
            note.parent.mkdir(parents=True)
            note.write_text('[[gtd/projects/demo/_brief#Purpose|Demo]]\n[Demo](../../gtd/projects/demo/_brief.md#Purpose)\n```\n[[gtd/projects/demo/_brief]]\n```\n')
            raw = root / 'system/session-log/raw.md'
            raw.parent.mkdir(parents=True)
            raw.write_text(note.read_text())
            plan = links.plan_links(root, {'moves': [{'from': old, 'to': new}]})
            self.assertEqual(len(plan['changes']), 1)
            text = plan['changes'][0]['text']
            self.assertIn('[[gtd/projects/demo/brief#Purpose|Demo]]', text)
            self.assertIn('../../gtd/projects/demo/brief.md#Purpose', text)
            self.assertIn('```\n[[gtd/projects/demo/_brief]]\n```', text)
            links.apply_links(root, plan)
            self.assertIn('_brief', raw.read_text())

    def test_newer_content_prevents_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            p = root / 'gtd/projects/demo/_brief.md'
            p.parent.mkdir(parents=True)
            p.write_text('brief')
            note = root / 'gtd/projects/demo/plan.md'
            note.write_text('[[_brief]]')
            plan = links.plan_links(root, {'moves': [{'from': 'gtd/projects/demo/_brief.md', 'to': 'gtd/projects/demo/brief.md'}]})
            note.write_text('Operator changed this')
            with self.assertRaises(ValueError):
                links.apply_links(root, plan)


if __name__ == '__main__':
    unittest.main()
