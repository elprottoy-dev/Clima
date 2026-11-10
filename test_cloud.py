import unittest,os,io,json,base64
from unittest.mock import patch,Mock
import test_upgrade
import server,cloud_transport,clinical,recovery_mail,scheduled
class Cloud(unittest.TestCase):
 setUp=test_upgrade.UpgradeFlow.setUp
 tearDown=test_upgrade.UpgradeFlow.tearDown
 call=test_upgrade.UpgradeFlow.call
 register=test_upgrade.UpgradeFlow.register
 report=test_upgrade.UpgradeFlow.report
 def env(self,path,token,data=None):
  from urllib.parse import urlsplit
  u=urlsplit(path);raw=json.dumps(data).encode() if data is not None else b''
  return {'PATH_INFO':u.path,'QUERY_STRING':u.query,'REQUEST_METHOD':'POST' if data is not None else 'GET','HTTP_AUTHORIZATION':'Bearer '+token,'CONTENT_TYPE':'application/json','CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw)}
 def transfer(self,path,token,data=None):
  env=self.env(path,token,data);status=[]
  out=cloud_transport.incoming(env,lambda s,h:status.append((s,h)))
  return status,json.loads(b''.join(out)) if out else None,env
 def test_upload_chunks_owner_and_assembly(self):
  raw=json.dumps({'case_id':123,'name':'test.pdf','content':'example'}).encode();pieces=[raw[:20],raw[20:]]
  _,start,_=self.transfer('/api/transfer/start',self.user,{'path':'documents','total':2});tid=start['id']
  other=self.register('other_user')
  status,_,_=self.transfer('/api/transfer/part',other,{'id':tid,'part':0,'content':base64.b64encode(pieces[0]).decode()});self.assertTrue(status[0][0].startswith('403'))
  for i,p in enumerate(pieces):self.transfer('/api/transfer/part',self.user,{'id':tid,'part':i,'content':base64.b64encode(p).decode()})
  _,result,env=self.transfer('/api/transfer/submit',self.user,{'id':tid})
  self.assertIsNone(result);self.assertEqual(env['PATH_INFO'],'/api/documents');self.assertEqual(env['wsgi.input'].read(),raw)
 def test_export_chunks_encrypted_and_owner_checked(self):
  raw=b'private export data'*200000;env=self.env('/api/admin/export?format=csv',self.admin);status=[]
  out=cloud_transport.outgoing(env,lambda s,h:status.append((s,h)),'200 OK',[('Content-Type','application/zip')],raw)
  meta=json.loads(b''.join(out));self.assertIn(('X-Clima-Transfer','1'),status[0][1])
  status,_,_=self.transfer('/api/transfer/read?id='+meta['id']+'&part=0',self.user);self.assertTrue(status[0][0].startswith('403'))
  result=b''
  for i in range(meta['total']):
   _,part,_=self.transfer('/api/transfer/read?id='+meta['id']+'&part='+str(i),self.admin);result+=base64.b64decode(part['content'])
  self.assertEqual(result,raw)
  with server.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM transfers').fetchone()[0],0)
 def test_postgres_backup_restore(self):
  if not os.getenv('CLIMA_TEST_POSTGRES'):self.skipTest('Disposable PostgreSQL only')
  import pg_backup,psycopg,tempfile
  from pathlib import Path
  cid=self.report();url=os.environ['CLIMA_TEST_POSTGRES'];connect=psycopg.connect
  def local_connect(url,**kwargs):return connect(url,sslmode='disable')
  with tempfile.TemporaryDirectory() as folder,patch.object(pg_backup.psycopg,'connect',side_effect=local_connect):
   target=folder+'/backup.climapg';pg_backup.snapshot(url,os.environ['CLIMA_DATA_KEY'],target,'long-backup-test-passphrase')
   self.assertNotIn(b'Sensitive Name',Path(target).read_bytes())
   with self.assertRaises(ValueError):pg_backup.restore(url,target,'long-backup-test-passphrase')
   with connect(url,sslmode='disable') as c:
    c.execute('DROP SCHEMA clima CASCADE');c.execute(Path('deployment/postgres-bootstrap.sql').read_text())
   server.init();pg_backup.restore(url,target,'long-backup-test-passphrase')
   with server.db() as c:
    self.assertEqual(c.execute('SELECT name_en FROM users WHERE id=1').fetchone()['name_en'],'Sensitive Name')
    self.assertIsNotNone(c.execute('SELECT id FROM cases WHERE id=?',(cid,)).fetchone())
 def test_postgres_scheduler(self):
  if not os.getenv('CLIMA_DATABASE_URL'):self.skipTest('PostgreSQL-only scheduler lock')
  self.assertTrue(scheduled.run(server.db)['ok'])
  with server.db() as c:self.assertIsNotNone(c.execute("SELECT value FROM app_settings WHERE key='scheduler_heartbeat'").fetchone())
 def test_wsgi_authenticated_api_and_cron_denial(self):
  with patch.dict(os.environ,{'CLIMA_SERVERLESS':'1'}):
   import wsgi
  status=[];out=wsgi.application(self.env('/api/me',self.user),lambda s,h:status.append((s,h)))
  self.assertTrue(status[0][0].startswith('200'));self.assertEqual(json.loads(b''.join(out))['role'],'user')
  status=[];out=wsgi.application(self.env('/api/cron',self.user,{}),lambda s,h:status.append((s,h)))
  self.assertTrue(status[0][0].startswith('403'))
 def test_brevo_and_cron_auth(self):
  with patch.dict(os.environ,{'BREVO_API_KEY':'synthetic','CLIMA_SMTP_FROM':'test@example.org','CLIMA_CRON_SECRET':'x'*40}),patch('requests.post',return_value=Mock(status_code=201)) as post:
   recovery_mail.deliver('recipient@example.org','12345678');self.assertEqual(post.call_args.kwargs['json']['to'][0]['email'],'recipient@example.org')
   self.assertTrue(scheduled.authorized('Bearer '+'x'*40));self.assertFalse(scheduled.authorized('Bearer wrong'))
if __name__=='__main__':unittest.main()
