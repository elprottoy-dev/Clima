import unittest,tempfile,json
from pathlib import Path
from deployment.prepare_vercel import prepare
from deployment.prepare_server import prepare as prepare_server
class Deployment(unittest.TestCase):
 def test_static_only_and_proxy(self):
  with tempfile.TemporaryDirectory() as d:
   out=prepare('https://backend.clima.test',Path(d)/'site')
   config=json.loads((out/'vercel.json').read_text())
   self.assertEqual(config['rewrites'][0]['destination'],'https://backend.clima.test/api/:path*')
   self.assertFalse(list(out.rglob('*.py')))
   self.assertFalse(list(out.rglob('*.sqlite3')))
   text=''.join(p.read_text() for p in (out/'public').iterdir())
   self.assertNotIn('bmd.gov.bd',text)
   self.assertNotIn('official-alerts.js',text)
   self.assertIn('admin-crud.js',text)
   self.assertIn('draft-vault.js',text)
   self.assertIn('no-store',json.dumps(config))
   with self.assertRaises(FileExistsError):prepare('https://backend.clima.test',out)
 def test_invalid_upstream_rejected(self):
  for url in ['http://api.test','https://user:pass@api.test','https://api.test/path','https://api.test?key=secret','https://localhost','https://api.example']:
   with self.subTest(url=url),tempfile.TemporaryDirectory() as d:
    with self.assertRaises(ValueError):prepare(url,Path(d)/'site')
 def test_private_configuration_not_overwritten(self):
  with tempfile.TemporaryDirectory() as d:
   target=prepare_server('backend.clima.test',d)
   self.assertEqual(target.stat().st_mode&0o777,0o600)
   original=target.read_bytes()
   with self.assertRaises(FileExistsError):prepare_server('backend.clima.test',d)
   self.assertEqual(target.read_bytes(),original)
if __name__=='__main__':unittest.main()
