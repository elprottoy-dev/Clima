"""Create a static-only Vercel project. Never copies backend code or secrets."""
import argparse,json,re,shutil
from pathlib import Path
from urllib.parse import urlsplit
ASSETS=('cloud-transport.js','index.html','style.css','app.js','clinical.js','upgrade.js','draft-vault.js','offline.js','labels.js','retention.js','admin-crud.js','sw.js')
def prepare(origin,destination,source=None):
 u=urlsplit(origin)
 if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ('','/') or u.port not in (None,443):
  raise ValueError('Use a public HTTPS backend origin without a path, credentials or port')
 if not re.fullmatch(r'[a-zA-Z0-9.-]+',u.hostname) or '.' not in u.hostname or u.hostname.endswith(('.example','.localhost','.invalid')):
  raise ValueError('Use the actual public backend hostname')
 dest=Path(destination);dest.mkdir(parents=True,exist_ok=False)
 public=dest/'public';public.mkdir()
 source=Path(source) if source else Path(__file__).resolve().parents[1]/'public'
 for name in ASSETS:shutil.copyfile(source/name,public/name)
 config={'$schema':'https://openapi.vercel.sh/vercel.json','framework':None,'outputDirectory':'public',
 'rewrites':[{'source':'/api/:path*','destination':origin.rstrip('/')+'/api/:path*'},{'source':'/admin','destination':'/index.html'}],
 'headers':[{'source':'/api/:path*','headers':[{'key':'Cache-Control','value':'private, no-store'},{'key':'CDN-Cache-Control','value':'no-store'},{'key':'Vercel-CDN-Cache-Control','value':'no-store'}]},
 {'source':'/(.*)','headers':[{'key':'X-Content-Type-Options','value':'nosniff'},{'key':'X-Frame-Options','value':'DENY'},{'key':'Referrer-Policy','value':'no-referrer'}]},
 {'source':'/sw.js','headers':[{'key':'Cache-Control','value':'no-cache'}]}]}
 (dest/'vercel.json').write_text(json.dumps(config,indent=2)+'\n')
 (dest/'README.md').write_text('Import this directory as a Vercel project. Framework: Other. Output: public. No build command. Backend must already be reachable over HTTPS. No secrets belong in this project. Hobby eligibility and all provider quotas still apply.\n')
 return dest
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--backend',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 print(prepare(a.backend,a.output))
