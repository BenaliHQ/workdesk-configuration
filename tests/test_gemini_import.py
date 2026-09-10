"""Run the Gemini importer against synthetic Docs responses in a temporary vault."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class GeminiImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='workdesk-gemini-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root/'vault'
        scripts = self.vault/'config/scripts'
        (scripts/'lib').mkdir(parents=True)
        for name in ['pull-gemini-transcripts.sh','lib/gws-layout.sh']:
            shutil.copy2(ROOT/'config/scripts'/name,scripts/name)
        self.script = scripts/'pull-gemini-transcripts.sh'
        (self.vault/'system/transcripts').mkdir(parents=True)
        home=self.root/'home';state=home/'.config/gws';state.mkdir(parents=True)
        for name in ['credentials.enc','client_secret.json']:(state/name).write_text('synthetic')
        self.bin=self.root/'bin';self.bin.mkdir()
        gws=self.bin/'gws'
        gws.write_text('#!'+sys.executable+'\n'+'''import json,os,sys
from pathlib import Path
a=sys.argv[1:]
if a[:3]==['drive','about','get']: print('{"user":{"emailAddress":"fixture@example.test"}}')
elif a[:3]==['docs','documents','get']:
 p=json.loads(a[a.index('--params')+1])
 if p.get('includeTabsContent'):print(Path(os.environ['DOC_FIXTURE']).read_text())
 else:print('{"documentId":"fixture-doc","title":"Fixture"}')
else:sys.exit(90)
''');gws.chmod(0o700)
        self.doc=self.root/'doc.json'
        self.env=dict(os.environ,HOME=str(home),XDG_CONFIG_HOME=str(home/'.config'),PATH=str(self.bin)+':'+os.environ['PATH'],DOC_FIXTURE=str(self.doc))
        self.checkpoint=self.vault/'config/state/pull-gemini.json'
        self.checkpoint.parent.mkdir(parents=True)
        self.before=b'{"last_success_at":"2026-09-01T00:00:00Z"}\n'
        self.checkpoint.write_bytes(self.before)

    def document(self, chunks):
        self.doc.write_text(json.dumps({'documentId':'fixture-doc','tabs':[
            {'tabProperties':{'title':'Notes'},'documentTab':{'body':{'content':[{'paragraph':{'elements':[{'textRun':{'content':'AI SUMMARY MUST NOT BE IMPORTED'}}]}}]}}},
            {'tabProperties':{'title':'Transcript'},'documentTab':{'body':{'content':[{'paragraph':{'elements':[{'textRun':{'content':c}} for c in chunks]}}]}}}
        ]}))

    def run_import(self,*args):
        return subprocess.run(['bash',str(self.script),'--doc-id','fixture-doc','--force',*args],env=self.env,capture_output=True,text=True,timeout=20)

    def notes(self):return list((self.vault/'system/intake').glob('*.md'))

    def test_exact_speaker_turns_blank_lines_unicode_and_trailing_newlines(self):
        chunks=['Alex: Café — keep this turn.\n\n','Robin: Preserve every newline.\n'*30,'\n\n']
        self.document(chunks);r=self.run_import();self.assertEqual(r.returncode,0,r.stderr)
        body=self.notes()[0].read_bytes().split(b'## Transcript\n\n',1)[1]
        self.assertEqual(body,''.join(chunks).encode())
        self.assertNotIn(b'AI SUMMARY',body)
        self.assertEqual(self.checkpoint.read_bytes(),self.before)

    def test_dry_run_preserves_checkpoint_and_publishes_nothing(self):
        self.document(['Alex: fixture line.\n'*60]);r=self.run_import('--dry-run')
        self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(self.notes(),[])
        self.assertEqual(self.checkpoint.read_bytes(),self.before)

    def test_malformed_document_is_a_failure_without_checkpoint_advance(self):
        self.doc.write_text('{invalid');r=self.run_import()
        self.assertNotEqual(r.returncode,0);self.assertEqual(self.notes(),[])
        self.assertEqual(self.checkpoint.read_bytes(),self.before)

    def test_single_doc_denied_is_not_reported_as_success(self):
        self.doc.write_text('{"error":{"code":403}}');r=self.run_import()
        self.assertNotEqual(r.returncode,0);self.assertEqual(self.notes(),[])
        self.assertEqual(self.checkpoint.read_bytes(),self.before)

if __name__=='__main__':unittest.main(verbosity=2)
