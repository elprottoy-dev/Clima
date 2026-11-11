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
   text=''.join(p.read_text() for p in (out/'public').iterdir() if p.suffix in ['.js','.html','.css'])
   # A source link is permitted; automated BMD ingestion remains disabled.
   self.assertNotIn('api.bmd.gov.bd',text)
   self.assertNotIn('official-alerts.js',text)
   self.assertIn('admin-crud.js',text)
   self.assertIn('draft-vault.js',text)
   self.assertIn('no-store',json.dumps(config))
   with self.assertRaises(FileExistsError):prepare('https://backend.clima.test',out)
 def test_backend_location_asset_packaged(self):
  config=json.loads(Path('vercel.json').read_text())
  assets=config['builds'][0]['config']['includeFiles']
  self.assertIn('public/locations.json',assets)
  for name in assets:self.assertTrue(Path(name).is_file(),name)
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
