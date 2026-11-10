import unittest,tempfile,threading,json,urllib.request,urllib.error,os,datetime,io,zipfile,xml.etree.ElementTree as ET
import server,clinical
from cryptography.fernet import Fernet
class ClinicalFlow(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();server.DB=cls.tmp.name+'/test.db';os.environ['CLIMA_ADMIN_PASSWORD']='Test-admin-987654';os.environ['CLIMA_DATA_KEY']=Fernet.generate_key().decode();server.init();cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=cls.http.serve_forever,daemon=True).start();cls.base='http://127.0.0.1:'+str(cls.http.server_port)
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.tmp.cleanup()
 def call(self,path,data=None,token=None,raw=False):
  req=urllib.request.Request(self.base+'/api/'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
  try:
   with urllib.request.urlopen(req) as r:return r.status,r.read() if raw else json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def test_care_export_notification_workflow(self):
  def reg(name,city):return self.call('register',dict(username=name,password='Strong-password-123',name_en='Test User',name_bn='পরীক্ষা ব্যবহারকারী',age=29,city=city))[1]['token']
  a=reg('health_a','Dhaka');b=reg('health_b','Rajshahi');admin=self.call('login',{'username':'admin','password':'Test-admin-987654'})[1]['token']
  self.assertEqual(self.call('staff',{'username':'doctor','password':'Doctor-password-123','role':'clinician','name':'Test clinician','credential':'TEST ONLY'},admin)[0],200)
  doctor=self.call('login',{'username':'doctor','password':'Doctor-password-123'})[1]['token']
  self.assertEqual(self.call('me',token=doctor)[1]['role'],'clinician')
  report=dict(categories=['sexual','salinity'],symptoms={'sexual':[0],'salinity':[0]},description='Private concern =1+1 বাংলা',severity='moderate',consent=True)
  self.assertEqual(self.call('cases',{**report,'consent':False},a)[0],400)
  self.assertEqual(self.call('cases',{**report,'categories':['madeup']},a)[0],400)
  self.assertEqual(self.call('cases',{**report,'symptoms':{'sexual':[999]}},a)[0],400)
  cid=self.call('cases',report,a)[1]['id']
  self.assertEqual(self.call('case?id='+str(cid),token=b)[0],403)
  self.assertEqual(len(self.call('cases',token=b)[1]['cases']),0)
  self.assertEqual(self.call('case?id='+str(cid),token=doctor)[0],403)
  c=self.call('case?id='+str(cid),token=admin)[1]
  self.assertEqual(c['report']['description'],report['description'])
  with server.db() as conn:
   self.assertNotIn('Private concern',conn.execute('SELECT payload FROM cases WHERE id=?',(cid,)).fetchone()['payload'])
  workflow=dict(id=cid,kind='workflow',version=c['version'],status='in_review',priority='priority',assigned=1,note='Review scheduled')
  self.assertEqual(self.call('case',workflow,admin)[0],200)
  self.assertEqual(self.call('case',workflow,admin)[0],409)
  assessment=dict(id=cid,kind='assessment',assessment='Example review only',diagnosis_status='not_determined',plan='Arrange consultation',advice_bn='পরামর্শের সময় ঠিক করুন')
  self.assertEqual(self.call('case',assessment,admin)[0],403)
  self.assertEqual(self.call('case',assessment,a)[0],403)
  self.assertEqual(self.call('case',assessment,doctor)[0],200)
  self.assertEqual(self.call('case',{'id':cid,'kind':'update','note':'Additional information'},a)[0],200)
  self.assertEqual(len(self.call('case?id='+str(cid),token=a)[1]['entries']),3)
  notices=self.call('notifications',token=a)[1]
  self.assertGreaterEqual(notices['unread'],3)
  self.assertNotIn('Private concern',json.dumps(notices))
  self.call('notifications',{'id':0},a)
  self.assertEqual(self.call('notifications',token=a)[1]['unread'],0)
  self.assertEqual(self.call('notifications',token=b)[1]['unread'],0)
  schedule=dict(title_en='Daily check-in',title_bn='দৈনিক খবর',body_en='View your dashboard',body_bn='ড্যাশবোর্ড দেখুন',city='Dhaka',at='09:00')
  self.assertEqual(self.call('admin/schedules',schedule,admin)[0],200)
  with server.db() as conn:
   now=datetime.datetime(2026,11,6,10,tzinfo=datetime.timezone(datetime.timedelta(hours=6)))
   clinical.run_daily(conn,now);clinical.run_daily(conn,now)
   self.assertEqual(conn.execute('SELECT COUNT(*) FROM schedule_runs').fetchone()[0],2)
  self.assertEqual(self.call('notifications',token=a)[1]['unread'],2)
  self.assertEqual(self.call('notifications',token=b)[1]['unread'],1)
  with server.db() as conn:clinical.run_daily(conn,now+datetime.timedelta(days=1))
  self.assertEqual(self.call('notifications',token=a)[1]['unread'],4)
  self.assertEqual(self.call('admin/export?format=xlsx',token=a)[0],403)
  self.assertEqual(self.call('admin/export?format=xlsx',token=doctor)[0],403)
  status,raw=self.call('admin/export?format=xlsx&uid=1&purpose=Clinical-review',token=admin,raw=True)
  self.assertEqual(status,200)
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   for name in z.namelist():ET.fromstring(z.read(name))
   self.assertIn('বাংলা',z.read('xl/worksheets/sheet2.xml').decode())
   self.assertNotIn('<f>',z.read('xl/worksheets/sheet2.xml').decode())
  status,raw=self.call('admin/export?format=csv&uid=1&purpose=Clinical-review',token=admin,raw=True)
  with zipfile.ZipFile(io.BytesIO(raw)) as z:self.assertTrue(z.read('Cases.csv').startswith(b'\xef\xbb\xbf'))
  status,raw=self.call('admin/export?format=pdf&uid=1&purpose=Clinical-review',token=admin,raw=True)
  self.assertEqual(status,200);self.assertTrue(raw.startswith(b'%PDF-'))
  data=self.call('admin/user-record?uid=1',token=admin)[1]
  self.assertNotIn('password',data['Users'][0]);self.assertEqual(len(data['Cases']),1)
  self.assertEqual(self.call('admin/user-record?uid=2',token=admin)[1]['Cases'],[])
  self.assertTrue(self.call('admin/audit',token=admin)[1]['audit'])
  self.call('staff/toggle',{'id':1,'active':False},admin)
  self.assertEqual(self.call('cases',token=doctor)[0],401)
 def test_csv_formula_escape(self):
  for value in ['=1+1',' +SUM(A1)','@SUM(A1)','\t=cmd']:
   self.assertTrue(clinical.csv_safe(value).startswith("'"))
if __name__=='__main__':unittest.main()
