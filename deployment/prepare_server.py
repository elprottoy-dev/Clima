"""Generate private first-run configuration on the actual backend host."""
import argparse,os,re,secrets
from pathlib import Path
from cryptography.fernet import Fernet

def prepare(domain,root):
 if not re.fullmatch(r'(?=.{1,253}$)[a-zA-Z0-9]+(?:[.-][a-zA-Z0-9]+)+',domain):raise ValueError('Supply only a public DNS hostname')
 root=Path(root);target=root/'.env'
 text='\n'.join(['CLIMA_DOMAIN='+domain,'CLIMA_ADMIN_PASSWORD='+secrets.token_urlsafe(30),'CLIMA_DATA_KEY='+Fernet.generate_key().decode(),'FIREBASE_PROJECT_ID=','CLIMA_SMTP_HOST=','CLIMA_SMTP_PORT=587','CLIMA_SMTP_FROM=','CLIMA_SMTP_USER=','CLIMA_SMTP_PASSWORD=',''])
 fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as f:f.write(text)
 (root/'secrets').mkdir(mode=0o700,exist_ok=True)
 return target
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--domain',required=True);a=p.parse_args()
 prepare(a.domain,Path(__file__).resolve().parents[1]);print('Created private .env and secrets directory. Existing configuration is never overwritten.')
