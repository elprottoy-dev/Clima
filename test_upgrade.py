import unittest,tempfile,threading,json,urllib.request,urllib.error,os,sqlite3,time,base64,io,datetime
from unittest.mock import patch
from cryptography.fernet import Fernet
import server,clinical,upgrade
class UpgradeFlow(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();server.DB=self.tmp.name+'/test.db';os.environ['CLIMA_ADMIN_PASSWORD']='Upgrade-admin-987654';os.environ['CLIMA_DATA_KEY']=Fernet.generate_key().decode();os.environ['CLIMA_REQUIRE_STAFF_MFA']='0';server.init();self.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=self.http.serve_forever,daemon=True).start();self.base='http://127.0.0.1:'+str(self.http.server_port)
  self.admin=self.call('login',{'username':'admin','password':'Upgrade-admin-987654'})[1]['token'];self.user=self.register('patient')
 def tearDown(self):self.http.shutdown();self.http.server_close();self.tmp.cleanup()
 def call(self,path,data=None,token=None,raw=False):
  req=urllib.request.Request(self.base+'/api/'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
  try:
   with urllib.request.urlopen(req) as r:return r.status,r.read() if raw else json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def register(self,name):return self.call('register',dict(username=name,password='Patient-password-123',name_en='Sensitive Name',name_bn='ব্যক্তিগত নাম',age=29,city='Dhaka'))[1]['token']
 def report(self):return self.call('cases',dict(categories=['sexual'],description='Private report',severity='moderate',consent=True,client_id='idempotent-report-00001'),self.user)[1]['id']
 def doctor(self,name):
  self.call('staff',dict(username=name,password='Doctor-password-123',role='clinician',name='Clinician',credential='Test credential'),self.admin)
  return self.call('login',dict(username=name,password='Doctor-password-123'))[1]['token']
 def test_assignment_grant_encryption_idempotency(self):
  doctor=self.doctor('doctor_one');other=self.doctor('doctor_two');cid=self.report();self.assertEqual(self.report(),cid)
  self.assertEqual(self.call('case?id='+str(cid),token=doctor)[0],403)
  self.assertEqual(self.call('cases',token=doctor)[1]['cases'],[])
  c=self.call('case?id='+str(cid),token=self.admin)[1]
  self.call('case',dict(id=cid,kind='workflow',version=c['version'],status='in_review',priority='routine',assigned=1),self.admin)
  self.assertEqual(self.call('case?id='+str(cid),token=doctor)[0],200)
  self.assertEqual(self.call('case?id='+str(cid),token=other)[0],403)
  self.call('access-grant',dict(case_id=cid,staff_id=2,reason='Approved second opinion'),self.admin)
  self.assertEqual(self.call('case?id='+str(cid),token=other)[0],200)
  with server.db() as conn:conn.execute('UPDATE access_grants SET expires=0')
  self.assertEqual(self.call('case?id='+str(cid),token=other)[0],403)
  with (__import__('psycopg').connect(os.environ['CLIMA_TEST_POSTGRES'],sslmode='disable',options='-c search_path=clima,public') if os.getenv('CLIMA_TEST_POSTGRES') else sqlite3.connect(server.DB)) as raw:
   name,age=raw.execute('SELECT name_en,age FROM users WHERE id=1').fetchone();self.assertTrue(name.startswith('enc:v1:'));self.assertTrue(age.startswith('enc:v1:'))
  self.assertEqual(self.call('me',token=self.user)[1]['user']['age'],29)
  self.assertGreater(self.call('notifications',token=self.admin)[1]['unread'],0)
 def test_privacy_fulfillment_and_columns(self):
  cid=self.report();doctor=self.doctor('privacy_doctor')
  c=self.call('case?id='+str(cid),token=self.admin)[1]
  self.call('case',dict(id=cid,kind='workflow',version=c['version'],status='in_review',priority='routine',assigned=1),self.admin)
  self.assertEqual(self.call('case?id='+str(cid),token=doctor)[0],200)
  self.call('privacy',dict(kind='withdraw_consent',detail='Pause sharing'),self.user)
  self.assertEqual(self.call('case?id='+str(cid),token=doctor)[0],403)
  self.assertEqual(self.call('cases',token=doctor)[1]['cases'],[])
  self.assertEqual(self.call('consent',dict(resume=True),self.user)[0],200)
  self.assertEqual(self.call('case?id='+str(cid),token=doctor)[0],200)
  r=self.call('privacy',dict(kind='correction',detail='Correct profile'),self.user)[1]['requests'][0]
  correction=dict(id=r['id'],response='Verified request',name_en='Corrected Name',name_bn='সঠিক নাম',age=30,city='Rajshahi')
  self.assertEqual(self.call('privacy-fulfill',correction,self.user)[0],403)
  self.assertEqual(self.call('privacy-fulfill',correction,self.admin)[0],200)
  self.assertEqual(self.call('me',token=self.user)[1]['user']['name_en'],'Corrected Name')
  with server.db() as conn:
   data=clinical.export_data(conn,[dict(conn.execute('SELECT id,username,name_en,name_bn,age,city FROM users').fetchone())])
   selected=upgrade.filter_export(conn,data,{'purpose':['Testing selected columns'],'sections':['Users'],'columns':[json.dumps({'Users':['city']})]},'test')
   self.assertEqual(selected,{'Users':[{'city':'Rajshahi'}]})
  r=self.call('privacy',dict(kind='delete',detail='Delete my account'),self.user)[1]['requests'][0]
  action=dict(id=r['id'],response='Request approved after review',confirmation='WRONG')
  self.assertEqual(self.call('privacy-fulfill',action,self.admin)[0],400)
  action['confirmation']='DELETE USER 1'
  self.assertEqual(self.call('privacy-fulfill',action,self.admin)[0],200)
  self.assertEqual(self.call('me',token=self.user)[0],401)
  with server.db() as conn:
   for table in ['users','cases','case_entries','privacy_requests','consent_events']:
    self.assertEqual(conn.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0)
  newuser=self.register('replacement')
  self.assertNotEqual(self.call('me',token=newuser)[1]['user']['id'],1)
 def test_verified_email_recovery(self):
  import recovery_mail
  with patch('recovery_mail.configured',return_value=True),patch('recovery_mail.deliver') as deliver:
   result=self.call('recovery-email',dict(action='start',email='test@example.org',password='Patient-password-123'),self.user)
   self.assertEqual(result[0],200);cid=result[1]['challenge'];code=deliver.call_args.args[1]
   self.assertEqual(self.call('recovery-email',dict(action='confirm',challenge=cid,email_code='bad'),self.user)[0],400)
   self.assertEqual(self.call('recovery-email',dict(action='confirm',challenge=cid,email_code=code),self.user)[0],200)
   with server.db() as c:c.execute('UPDATE email_challenges SET created=0')
   result=self.call('recover-email',dict(action='start',username='patient'));self.assertEqual(result[0],200)
   cid=result[1]['challenge'];code=deliver.call_args.args[1]
   data=dict(action='confirm',challenge=cid,email_code=code,new_password='Email-reset-password-123')
   self.assertEqual(self.call('recover-email',data)[0],200)
   self.assertEqual(self.call('recover-email',data)[0],400)
   self.assertEqual(self.call('me',token=self.user)[0],401)
   self.assertEqual(self.call('login',dict(username='patient',password='Email-reset-password-123'))[0],200)
 def test_scheduled_retention_holds_and_changes(self):
  import retention
  cid=self.report();current=self.call('case?id='+str(cid),token=self.admin)[1]
  self.call('case',dict(id=cid,kind='workflow',version=current['version'],status='closed',priority='routine'),self.admin)
  now=datetime.datetime.now(datetime.timezone.utc);due=(now+datetime.timedelta(days=2)).isoformat()
  action=dict(case_id=cid,action='schedule',due=due,reason='Retention approved after documented review',confirmation='DELETE CASE '+str(cid))
  self.assertEqual(self.call('retention',action,self.user)[0],403)
  self.assertEqual(self.call('retention',action,self.admin)[0],200)
  self.assertEqual(self.call('retention',dict(case_id=cid,action='hold',reason='Review pending'),self.admin)[0],200)
  with server.db() as conn:retention.tick(conn,now+datetime.timedelta(days=3))
  self.assertEqual(self.call('case?id='+str(cid),token=self.admin)[0],200)
  self.call('retention',action,self.admin)
  self.call('case',dict(id=cid,kind='note',note='New information after approval'),self.admin)
  with server.db() as conn:
   retention.tick(conn,now+datetime.timedelta(days=3));self.assertEqual(conn.execute('SELECT state FROM retention_jobs').fetchone()[0],'review_required')
  self.call('retention',action,self.admin)
  with server.db() as conn:
   retention.tick(conn,now+datetime.timedelta(days=3));self.assertEqual(conn.execute('SELECT COUNT(*) FROM cases').fetchone()[0],0)
   self.assertEqual(conn.execute('SELECT COUNT(*) FROM case_entries').fetchone()[0],0)
   self.assertEqual(conn.execute('SELECT state FROM retention_jobs').fetchone()[0],'completed')
  report=dict(categories=['sexual'],description='New report',severity='moderate',consent=True,client_id='different-report-after-deletion')
  self.assertGreater(self.call('cases',report,self.user)[1]['id'],cid)
 def test_health_reports_scheduler_failure(self):
  self.assertEqual(self.call('health')[0],503)
  with server.db() as c:c.execute("INSERT INTO app_settings VALUES('scheduler_heartbeat',?)",(str(time.time()),))
  self.assertEqual(self.call('health')[1],{'status':'ok'})
  with server.db() as c:c.execute("UPDATE app_settings SET value='0' WHERE key='scheduler_heartbeat'")
  self.assertEqual(self.call('health')[0],503)
 def test_admin_crud(self):
  self.assertEqual(self.call('admin/crud?entity=users',token=self.user)[0],403)
  create=dict(entity='users',action='create',username='managed_user',password='Managed-password-123',name_en='Managed User',name_bn='পরিচালিত ব্যবহারকারী',age=32,city='Dhaka')
  result=self.call('admin/crud',create,self.admin);self.assertEqual(result[0],200);rid=result[1]['id']
  self.assertNotIn('password',result[1]['rows'][0])
  self.assertEqual(self.call('admin/crud',{**create,'action':'update','id':rid,'age':33,'password':''},self.admin)[0],200)
  self.assertEqual(self.call('admin/crud',dict(entity='users',id=rid,action='archive'),self.admin)[0],200)
  self.assertEqual(self.call('login',dict(username='managed_user',password='Managed-password-123'))[0],401)
  self.call('admin/crud',dict(entity='users',id=rid,action='restore'),self.admin)
  self.assertEqual(self.call('login',dict(username='managed_user',password='Managed-password-123'))[0],200)
  msg=dict(entity='messages',action='create',title_en='Notice',title_bn='নোটিশ',body_en='Body',body_bn='বার্তা',priority='normal',city='Dhaka')
  result=self.call('admin/crud',msg,self.admin);self.assertEqual(result[0],200);mid=result[1]['id']
  self.assertEqual(self.call('admin/crud',{**msg,'action':'update','id':mid,'body_en':'Revised'},self.admin)[0],200)
  self.assertEqual(self.call('inbox',token=self.user)[1]['messages'][0]['body_en'],'Revised')
  self.call('admin/crud',dict(entity='messages',action='archive',id=mid),self.admin)
  self.assertEqual(self.call('inbox',token=self.user)[1]['messages'],[])
  schedule={**msg,'entity':'schedules','at':'10:00','frequency':'daily'}
  result=self.call('admin/crud',schedule,self.admin);self.assertEqual(result[0],200);sid=result[1]['id']
  self.call('admin/crud',dict(entity='schedules',action='archive',id=sid),self.admin)
  with server.db() as conn:self.assertEqual(conn.execute('SELECT active FROM schedules WHERE id=?',(sid,)).fetchone()[0],0)
  staff=dict(entity='staff',action='create',username='managed_doctor',password='Managed-password-123',name='Doctor',role='clinician',credential='Verified externally')
  result=self.call('admin/crud',staff,self.admin);self.assertEqual(result[0],200)
  self.assertEqual(self.call('admin/crud',{**staff,'action':'update','id':result[1]['id'],'name':'Updated Doctor','password':''},self.admin)[0],200)
 def test_mfa_recovery_and_sessions(self):
  secret=self.call('account',dict(action='mfa_start',password='Patient-password-123'),self.user)[1]['secret'];counter=int(time.time()/30)
  self.assertEqual(self.call('account',dict(action='mfa_confirm',code=upgrade.code_at(secret,counter)),self.user)[0],200)
  self.assertEqual(self.call('login',dict(username='patient',password='Patient-password-123'))[0],401)
  with patch('upgrade.time.time',return_value=(counter+1)*30+1):
   result=self.call('login',dict(username='patient',password='Patient-password-123',code=upgrade.code_at(secret,counter+1)));self.assertEqual(result[0],200)
   newtoken=result[1]['token']
   self.assertEqual(self.call('login',dict(username='patient',password='Patient-password-123',code=upgrade.code_at(secret,counter+1)))[0],401)
  with patch('upgrade.time.time',return_value=(counter+2)*30+1):
   r=self.call('account',dict(action='recovery',password='Patient-password-123',code=upgrade.code_at(secret,counter+2)),newtoken);self.assertEqual(r[0],200);recovery=r[1]['recovery_code']
  self.assertEqual(self.call('recover',dict(username='patient',recovery_code=recovery,new_password='Recovered-password-123'))[0],200)
  self.assertEqual(self.call('me',token=self.user)[0],401)
  self.assertEqual(self.call('recover',dict(username='patient',recovery_code=recovery,new_password='Another-password-123'))[0],403)
  self.assertEqual(self.call('login',dict(username='patient',password='Recovered-password-123'))[0],200)
 def test_upload_appointment_and_exports(self):
  cid=self.report();other=self.register('otherpatient')
  from PIL import Image
  b=io.BytesIO();Image.new('RGB',(10,10),'white').save(b,format='PNG')
  document=dict(case_id=cid,name='test.png',content=base64.b64encode(b.getvalue()).decode())
  self.assertEqual(self.call('documents',document,other)[0],403)
  self.assertEqual(self.call('documents',document,self.user)[0],200)
  self.assertEqual(self.call('documents',{**document,'content':base64.b64encode(b'<script>bad</script>').decode()},self.user)[0],400)
  docid=self.call('documents?case_id='+str(cid),token=self.user)[1]['documents'][0]['id']
  self.assertEqual(self.call('document?id='+str(docid),token=other)[0],403)
  self.assertEqual(self.call('document?id='+str(docid),token=self.user,raw=True)[0],200)
  import zipfile
  bundle=self.call('admin/export?format=bundle&purpose=Clinical-review&uid=1',token=self.admin,raw=True)
  self.assertEqual(bundle[0],200)
  with zipfile.ZipFile(io.BytesIO(bundle[1])) as z:
   self.assertIn('records.xlsx',z.namelist());self.assertIn('documents/'+str(docid)+'.jpg',z.namelist())
  self.assertEqual(self.call('admin/export?format=bundle&purpose=Review&anonymized=1',token=self.admin)[0],400)
  self.assertEqual(self.call('admin/export-columns',token=self.user)[0],403)

  at=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=2)).isoformat()
  self.assertEqual(self.call('appointments',dict(case_id=cid,at=at,notes='Review'),self.admin)[0],200)
  with server.db() as c:upgrade.tick(c)
  self.assertTrue(any(n['source']=='appointment' for n in self.call('notifications',token=self.user)[1]['notifications']))
  self.assertEqual(self.call('admin/export?format=xlsx',token=self.admin)[0],400)
  self.assertEqual(self.call('admin/export?format=xlsx&purpose=Review&anonymized=1',token=self.admin,raw=True)[0],200)
 def test_staff_mfa_gate_and_daily_schedule(self):
  os.environ['CLIMA_REQUIRE_STAFF_MFA']='1'
  self.assertTrue(self.call('me',token=self.admin)[1]['mfa_required'])
  self.assertEqual(self.call('cases',token=self.admin)[0],403)
  self.assertEqual(self.call('account',token=self.admin)[0],200)
  os.environ['CLIMA_REQUIRE_STAFF_MFA']='0'
  d=dict(id=1,title_en='Once',title_bn='একবার',body_en='Daily notice',body_bn='নোটিশ',at='09:00',frequency='once',start_date='2030-01-01',end_date='2030-01-01')
  self.assertEqual(self.call('schedule-edit',d,self.admin)[0],200)
  with server.db() as c:
   now=datetime.datetime(2030,1,1,10,tzinfo=datetime.timezone(datetime.timedelta(hours=6)));clinical.run_daily(c,now);clinical.run_daily(c,now+datetime.timedelta(days=1))
   self.assertEqual(c.execute('SELECT COUNT(*) FROM schedule_runs').fetchone()[0],1)
if __name__=='__main__':unittest.main()
