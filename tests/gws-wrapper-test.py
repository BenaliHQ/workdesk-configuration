#!/usr/bin/env python3
"""Exercise the sourced wrapper in Bash and Zsh without OAuth or real secrets."""
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]/'config/shell/gws-env.sh'

class WrapperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='workdesk-gws-wrapper-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root/"vault ' $(touch injection-marker) space"
        shell = self.vault/'config/shell'
        shell.mkdir(parents=True)
        shutil.copy2(SOURCE, shell/'gws-env.sh')
        (self.vault/'config/operator-profile.md').write_text('---\nemail: operator@example.test\ninfisical-project-id: test-project\n---\n')
        self.bin = self.root/'tools with spaces'
        self.bin.mkdir()
        self.home = self.root/'home'
        self.home.mkdir()
        self.record = self.root/'call.json'
        self.env = dict(os.environ, HOME=str(self.home), PATH=str(self.bin)+':/usr/bin:/bin', RECORD=str(self.record))
        for key in ('WORKDESK_GWS_BIN', 'WORKDESK_INFISICAL_BIN', 'BASH_ENV', 'ENV'):
            self.env.pop(key, None)
        self.env['ZDOTDIR'] = str(self.home)
        for name in ('gws','infisical'):
            self.stub(self.bin/name)

    def stub(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('#!'+sys.executable+'\nimport json,os,sys\nfrom pathlib import Path\nPath(os.environ["RECORD"]).write_text(json.dumps({"binary":sys.argv[0],"args":sys.argv[1:]}))\nsys.exit(int(os.environ.get("STUB_EXIT","0")))\n')
        path.chmod(0o700)

    def run_wrapper(self, shell, args, snapshot=False):
        code = 'source '+shlex.quote(str(self.vault/'config/shell/gws-env.sh'))+'\n'
        if snapshot:
            # Copy only the function into another clean shell; no source variables.
            captured = subprocess.run([shell, '-f', '-c', code+'typeset -f gws'],
                env=self.env, text=True, capture_output=True, timeout=10, cwd=self.root)
            if captured.returncode:
                return captured
            code = captured.stdout+'\ngws '
        else:
            code += 'gws '
        code += ' '.join(shlex.quote(a) for a in args)
        return subprocess.run([shell,'-f','-c',code],env=self.env,text=True,capture_output=True,timeout=10,cwd=self.root)

    def both(self, fn):
        for shell in ('/bin/bash','/bin/zsh'):
            with self.subTest(shell=shell):
                if self.record.exists(): self.record.unlink()
                fn(shell)
                self.assertFalse((self.root/'injection-marker').exists())

    def test_path_discovery_preserves_arguments_and_status(self):
        args=['drive','files','list','--params','{"q":"name = \'$literal; `text`\'"}']
        self.env['STUB_EXIT']='17'
        def check(shell):
            r=self.run_wrapper(shell,args)
            self.assertEqual(r.returncode,17,r.stderr)
            self.assertEqual(json.loads(self.record.read_text())['args'],args)
        self.both(check)

    def test_explicit_binary_override(self):
        chosen=self.root/'chosen binary'
        self.stub(chosen)
        self.env['WORKDESK_GWS_BIN']=str(chosen)
        def check(shell):
            r=self.run_wrapper(shell,['--version'])
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(json.loads(self.record.read_text())['binary'],str(chosen))
        self.both(check)

    def test_invalid_override_never_falls_back(self):
        self.env['WORKDESK_GWS_BIN']='gws; echo unsafe'
        def check(shell):
            r=self.run_wrapper(shell,['--version'])
            self.assertEqual(r.returncode,127,r.stderr)
            self.assertFalse(self.record.exists())
        self.both(check)

    def test_home_fallback_and_function_snapshot(self):
        self.env['PATH']='/usr/bin:/bin'
        local=self.home/'.local/bin/gws'
        self.stub(local)
        def check(shell):
            r=self.run_wrapper(shell,['--version'],snapshot=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertEqual(json.loads(self.record.read_text())['binary'],str(local))
        self.both(check)

    def test_login_discovers_infisical_and_quotes_binary(self):
        def check(shell):
            r=self.run_wrapper(shell,['auth','login','--account','operator@example.test'])
            self.assertEqual(r.returncode,0,r.stderr)
            call=json.loads(self.record.read_text())
            self.assertEqual(call['binary'],str(self.bin/'infisical'))
            self.assertIn('--projectId=test-project',call['args'])
            cmd=next(a.removeprefix('--command=') for a in call['args'] if a.startswith('--command='))
            words=shlex.split(cmd)
            self.assertEqual(words[-5:],[str(self.bin/'gws'),'auth','login','--account','operator@example.test'])
        self.both(check)

    def test_login_invalid_infisical_override_fails_before_auth(self):
        self.env['WORKDESK_INFISICAL_BIN']=str(self.root/'absent')
        def check(shell):
            r=self.run_wrapper(shell,['auth','login'])
            self.assertEqual(r.returncode,127,r.stderr)
            self.assertFalse(self.record.exists())
        self.both(check)

if __name__ == '__main__':
    unittest.main(verbosity=2)
