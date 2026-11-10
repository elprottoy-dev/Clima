"""Encrypted PostgreSQL data snapshots; restore only into a fresh initialized target."""
import os,json,argparse,getpass,secrets
from pathlib import Path
import psycopg,certifi
from psycopg import sql
from backup import cipher
from cryptography.fernet import Fernet
MAGIC=b'CLIMAPG1'

def snapshot(url,key,path,password):
 Fernet(key.encode())
 with psycopg.connect(url,sslmode='verify-full',sslrootcert=certifi.where()) as c:
  c.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
  tables={}
  for (name,) in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='clima' ORDER BY tablename").fetchall():
   if name in ('transfers','transfer_parts'):continue
   cur=c.execute(sql.SQL('SELECT * FROM clima.{}').format(sql.Identifier(name)))
   tables[name]={'columns':[x.name for x in cur.description],'rows':cur.fetchall()}
 payload=json.dumps({'version':10,'key':key,'tables':tables}).encode();salt=secrets.token_bytes(16)
 fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as f:f.write(MAGIC+salt+cipher(password,salt).encrypt(payload))
def read(path,password):
 raw=Path(path).read_bytes()
 if not raw.startswith(MAGIC):raise ValueError('Not a PostgreSQL CliMa snapshot')
 data=json.loads(cipher(password,raw[8:24]).decrypt(raw[24:]));Fernet(data['key'].encode())
 if data['version']!=10:raise ValueError('Unsupported snapshot version')
 return data

def restore(url,path,password):
 data=read(path,password)
 if os.environ.get('CLIMA_DATA_KEY')!=data['key']:raise ValueError('Configure the target with the original encryption key before restoring')
 with psycopg.connect(url,sslmode='verify-full',sslrootcert=certifi.where()) as c:
  c.execute('SET search_path TO clima,extensions,public')
  c.execute("SELECT set_config('clima.data_key',%s,true)",(__import__('base64').urlsafe_b64decode(data['key']).hex(),))
  existing={r[0] for r in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='clima'")}
  if set(data['tables'])!=existing-{'transfers','transfer_parts'}:raise ValueError('Initialize an empty v10 target schema first')
  for name in existing:
   rows=c.execute(sql.SQL('SELECT COUNT(*) FROM clima.{}').format(sql.Identifier(name))).fetchone()[0]
   if rows and name not in ('schedules','app_settings','identity_sequence'):raise ValueError('Target is not empty; refusing overwrite')
  if c.execute("SELECT COUNT(*) FROM app_settings WHERE key<>'default_daily'").fetchone()[0] or c.execute('SELECT COUNT(*) FROM schedules').fetchone()[0]>1:raise ValueError('Target has configuration; refusing overwrite')
  if c.execute('SELECT COUNT(*) FROM identity_sequence WHERE value<>0').fetchone()[0]:raise ValueError('Target has prior identity history; refusing overwrite')
  c.execute('DELETE FROM schedules');c.execute('DELETE FROM app_settings');c.execute('DELETE FROM identity_sequence')
  for name,table in data['tables'].items():
   columns=table['columns'];statement=sql.SQL('INSERT INTO clima.{} ({}) VALUES ({})').format(sql.Identifier(name),sql.SQL(',').join(map(sql.Identifier,columns)),sql.SQL(',').join(sql.Placeholder() for _ in columns))
   with c.cursor() as cur:cur.executemany(statement,table['rows'])
  for table,column in c.execute("SELECT table_name,column_name FROM information_schema.columns WHERE table_schema='clima' AND is_identity='YES'").fetchall():
   seq=c.execute('SELECT pg_get_serial_sequence(%s,%s)',('clima.'+table,column)).fetchone()[0]
   maximum=c.execute(sql.SQL('SELECT COALESCE(MAX({}),0) FROM clima.{}').format(sql.Identifier(column),sql.Identifier(table))).fetchone()[0]
   c.execute('SELECT setval(%s,%s,%s)',(seq,max(1,maximum),maximum>0))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('action',choices=['create','verify','restore']);p.add_argument('file');p.add_argument('--confirm-empty-target',action='store_true');a=p.parse_args()
 password=getpass.getpass('Backup passphrase (16+ characters): ')
 if a.action=='create':
  if password!=getpass.getpass('Confirm passphrase: '):raise SystemExit('Passphrases differ')
  snapshot(os.environ['CLIMA_DATABASE_URL'],os.environ['CLIMA_DATA_KEY'],a.file,password)
 elif a.action=='verify':read(a.file,password)
 else:
  if not a.confirm_empty_target:raise SystemExit('Restore requires --confirm-empty-target and a fresh initialized database')
  restore(os.environ['CLIMA_DATABASE_URL'],a.file,password)
 print('Operation completed. Keep backup passphrase and encryption key separately.')
