"""Encrypted backups and non-overwriting isolated restoration."""
import argparse,os,getpass,io,zipfile,sqlite3,base64,hashlib,tempfile
from pathlib import Path
from cryptography.fernet import Fernet

def cipher(password,salt):
 if len(password)<16:raise ValueError('Passphrase must have at least 16 characters')
 return Fernet(base64.urlsafe_b64encode(hashlib.pbkdf2_hmac('sha256',password.encode(),salt,600000)))

def create(database,key,target,password):
 database=Path(database);target=Path(target)
 if not database.is_file():raise ValueError('Database does not exist')
 Fernet(key.strip().encode())
 with tempfile.TemporaryDirectory() as tmp:
  snap=Path(tmp)/'clima.sqlite3'
  with sqlite3.connect(database) as source,sqlite3.connect(snap) as dest:source.backup(dest)
  bio=io.BytesIO()
  with zipfile.ZipFile(bio,'w',zipfile.ZIP_DEFLATED) as z:z.write(snap,'clima.sqlite3');z.writestr('data.key',key)
  salt=os.urandom(16);payload=b'CLIMA4'+salt+cipher(password,salt).encrypt(bio.getvalue())
  fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'wb') as f:f.write(payload)

def verify(file,password):
 raw=Path(file).read_bytes()
 if not raw.startswith(b'CLIMA4'):raise ValueError('Invalid backup format')
 content=cipher(password,raw[6:22]).decrypt(raw[22:])
 with zipfile.ZipFile(io.BytesIO(content)) as z:
  if sorted(z.namelist())!=['clima.sqlite3','data.key']:raise ValueError('Unexpected backup entries')
  database,key=z.read('clima.sqlite3'),z.read('data.key');Fernet(key.strip())
  with tempfile.TemporaryDirectory() as tmp:
   db=Path(tmp)/'verify.sqlite3';db.write_bytes(database)
   with sqlite3.connect(db) as conn:
    if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Database integrity check failed')
 return database,key

def restore(file,password,destination):
 database,key=verify(file,password)
 target=Path(destination)
 # A new isolated directory prevents accidentally overwriting a running service.
 target.mkdir(mode=0o700,parents=False,exist_ok=False)
 (target/'private').mkdir(mode=0o700)
 for path,data in [(target/'clima.sqlite3',database),(target/'private/data.key',key)]:
  fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'wb') as f:f.write(data)
 return target

def main():
 p=argparse.ArgumentParser();p.add_argument('action',choices=['create','verify','restore']);p.add_argument('file');p.add_argument('--destination',help='New isolated directory for restoration');args=p.parse_args()
 password=getpass.getpass('Backup passphrase (16+ characters): ')
 if args.action=='create':
  if password!=getpass.getpass('Confirm backup passphrase: '):raise SystemExit('Passphrases do not match')
  root=Path(__file__).parent;key=os.getenv('CLIMA_DATA_KEY') or (root/'private/data.key').read_text()
  create(os.getenv('CLIMA_DB',str(root/'clima.sqlite3')),key,args.file,password)
  print('Encrypted backup created. Store the passphrase separately.')
 elif args.action=='verify':verify(args.file,password);print('Backup integrity verified.')
 else:
  if not args.destination:p.error('restore requires --destination pointing to a new directory')
  restore(args.file,password,args.destination)
  print('Restored to isolated directory. Validate before configuring the service to use this database and its matching key.')
if __name__=='__main__':main()
