import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('indexes', REPO / 'config/scripts/ontology-index.py')
indexes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(indexes)


class NavigationTests(unittest.TestCase):
    def test_nested_hooks_find_vault_without_running_real_hooks(self):
        settings = json.loads((REPO / 'config/settings.json').read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            scripts = root / 'config/scripts'
            scripts.mkdir(parents=True)
            nested = root / 'atlas/businesses/example/initiatives/training/projects/course'
            nested.mkdir(parents=True)
            (scripts / 'json-get.sh').write_text('# marker')
            for groups in settings['hooks'].values():
                for group in groups:
                    for hook in group['hooks']:
                        command = hook['command']
                        filename = command.split('/config/scripts/')[-1].rstrip('\"\'')
                        (scripts / filename).write_text('printf "resolved-correctly"\n')
                        result = subprocess.run(['bash', '-c', command], cwd=nested,
                            env=dict(os.environ, CLAUDE_PROJECT_DIR=str(nested)), capture_output=True, text=True)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stdout, 'resolved-correctly')

    def test_indexes_preserve_handwritten_and_private_space(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / 'personal/daily').mkdir(parents=True)
            (root / 'gtd/projects/demo').mkdir(parents=True)
            own = root / 'gtd/projects/demo/index.md'
            own.write_text('Handwritten navigation')
            indexes.generate(root)
            self.assertEqual(own.read_text(), 'Handwritten navigation')
            self.assertEqual(list((root / 'personal').rglob('index.md')), [])
            self.assertEqual(indexes.generate(root), [])


if __name__ == '__main__':
    unittest.main()
