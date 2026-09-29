import os,json,tempfile,shutil,subprocess,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
class Resolver(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.lib=self.root/'config/scripts/lib';self.lib.mkdir(parents=True)
  for n in ['resolve-secret.sh','operator-config.sh']:shutil.copy2(HERE.parent/'config/scripts/lib'/n,self.lib/n)
  (self.root/'config/operator-profile.md').write_text('---\nname: Synthetic Operator\nemail: operator@example.test\ninfisical-project-id: synthetic-project\n---\n')
  self.bin=self.root/'bin';self.bin.mkdir();self.trace=self.root/'calls'
  self.env={'PATH':str(self.bin)+':/usr/bin:/bin','HOME':str(self.root),'TRACE':str(self.trace)}
  # Never let the resolver reach the host's real macOS keychain: a fake
  # `security` shadows /usr/bin/security and has no credentials by default.
  self.keychain(None)
 def keychain(self,creds):
  p=self.bin/'security'
  if creds is None:p.write_text('#!/bin/bash\nexit 44\n')
  else:p.write_text('#!/bin/bash\ncase "$*" in *infisical-ua-client-id*) printf %s '+repr(creds[0])+';; *infisical-ua-client-secret*) printf %s '+repr(creds[1])+';; *) exit 44;; esac\n')
  p.chmod(0o700)
 def ua_provider(self,login_out,login_code,token_out,token_code):
  # User session always fails; a secrets lookup succeeds only with the minted token.
  p=self.bin/'infisical';p.write_text('#!/bin/bash\nprintf "%s\\n" "$1" >> "$TRACE"\nif [[ "$1" == login ]]; then printf "%s" '+repr(login_out)+'; exit '+str(login_code)+'; fi\nif [[ "${INFISICAL_TOKEN:-}" == synthetic-token ]]; then printf "%s" '+repr(token_out)+'; exit '+str(token_code)+'; fi\nexit 1\n');p.chmod(0o700)
 def provider(self,output,code):
  p=self.bin/'infisical';p.write_text('#!/bin/bash\nprintf \"called\\n\" >> \"$TRACE\"\nprintf \"%s\" '+repr(output)+'\nexit '+str(code)+'\n');p.chmod(0o700)
 def resolve(self):return subprocess.run(['/bin/bash','-c','source \"$1\"; wd_resolve_secret PERSONAL_GRANOLA_API_KEY','test',str(self.lib/'resolve-secret.sh')],env=self.env,capture_output=True,text=True)
 def test_environment_value_wins_without_provider(self):
  self.provider('unused',1);self.env['PERSONAL_GRANOLA_API_KEY']='synthetic-env';r=self.resolve();self.assertEqual((r.returncode,r.stdout),(0,'synthetic-env'));self.assertFalse(self.trace.exists())
 def test_successful_provider(self):
  self.provider('synthetic-provider',0);r=self.resolve();self.assertEqual((r.returncode,r.stdout),(0,'synthetic-provider'));self.assertTrue(self.trace.exists())
 def test_successful_empty_provider_is_not_a_credential(self):
  self.provider('',0);r=self.resolve();self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,'')
 def test_empty_failed_provider(self):
  self.provider('',1);r=self.resolve();self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,'')
 def test_failed_provider_stdout_is_not_a_credential(self):
  self.provider('grn_synthetic_partial_failure',1);r=self.resolve();self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,'')
 def test_keychain_is_isolated_from_host(self):
  self.provider('',1);r=self.resolve();self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,'')
 def test_ua_fallback_used_when_user_session_fails(self):
  self.keychain(('synthetic-id','synthetic-secret'));self.ua_provider('synthetic-token',0,'synthetic-ua-value',0);r=self.resolve()
  self.assertEqual((r.returncode,r.stdout),(0,'synthetic-ua-value'),r.stderr);self.assertIn('login',self.trace.read_text())
 def test_ua_fallback_failed_login_returns_nothing(self):
  self.keychain(('synthetic-id','synthetic-secret'));self.ua_provider('synthetic-token',1,'synthetic-ua-value',0);r=self.resolve();self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,'')
 def test_ua_fallback_failed_lookup_output_is_not_a_credential(self):
  self.keychain(('synthetic-id','synthetic-secret'));self.ua_provider('synthetic-token',0,'grn_synthetic_partial_failure',1);r=self.resolve();self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,'')
 def test_ua_fallback_skipped_without_keychain_credentials(self):
  self.ua_provider('synthetic-token',0,'synthetic-ua-value',0);r=self.resolve();self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,'');self.assertNotIn('login',self.trace.read_text())
if __name__=='__main__':unittest.main(verbosity=2)
