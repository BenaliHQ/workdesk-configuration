from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ReleaseArchiveTests(unittest.TestCase):
    def test_build_excludes_host_metadata_and_private_state_preserving_payload(self):
        with tempfile.TemporaryDirectory(prefix='workdesk-package-test-') as folder:
            root = Path(folder)
            for name in ('scripts/release.sh', 'tests/genericity-check.sh', 'tests/genericity-allowlist.txt'):
                target = root/name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT/name, target)
            config = root/'config'
            (config/'scripts').mkdir(parents=True)
            (config/'VERSION').write_text('9.8.7\n')
            payload = config/'scripts/check.sh'
            payload.write_text('#!/bin/sh\nprintf "ok\\n"\n')
            payload.chmod(0o755)
            (config/'scripts/linked.sh').symlink_to('check.sh')
            (config/'note.md').write_text('Synthetic distributable note.\n')
            if sys.platform == 'darwin':
                subprocess.run(['/usr/bin/xattr', '-w', 'com.workdesk.release-test',
                                'synthetic host metadata', str(config/'note.md')], check=True)
            for name in ('._note.md', '.DS_Store', 'operator-policy.md', 'cache.pyc',
                         'defaults/old.md', 'state/runtime.json', 'snapshots/prior.md', '__pycache__/a.pyc'):
                target = config/name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('Synthetic excluded data.\n')
            process = subprocess.run(['bash', str(root/'scripts/release.sh'), '--dry-run'],
                                     capture_output=True, text=True, timeout=60)
            self.assertEqual(process.returncode, 0, process.stdout+process.stderr)
            archive = root/'dist/workdesk-os-9.8.7.tar.gz'
            self.assertEqual(hashlib.sha256(archive.read_bytes()).hexdigest(),
                             Path(str(archive)+'.sha256').read_text().split()[0])
            with tarfile.open(archive) as opened:
                members = {m.name.removeprefix('./'): m for m in opened.getmembers()}
                self.assertFalse(any(part.startswith('._') for name in members for part in Path(name).parts))
                regular = {name for name,m in members.items() if m.isfile()}
                self.assertEqual(regular, {'manifest.json', 'workdesk/VERSION',
                                          'workdesk/note.md', 'workdesk/scripts/check.sh'})
                self.assertEqual(opened.extractfile(members['workdesk/scripts/check.sh']).read(), payload.read_bytes())
                self.assertEqual(members['workdesk/scripts/check.sh'].mode & 0o777, 0o755)
                link = members['workdesk/scripts/linked.sh']
                self.assertTrue(link.issym())
                self.assertEqual(link.linkname, 'check.sh')
                self.assertEqual(json.load(opened.extractfile(members['manifest.json'])),
                                 {'version': '9.8.7', 'migrations': []})


if __name__ == '__main__':
    unittest.main()
