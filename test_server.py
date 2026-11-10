import unittest,tempfile,threading,json,urllib.request,urllib.error,os
import server
class Flow(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();server.DB=cls.tmp.name+'/test.db';os.environ['CLIMA_ADMIN_PASSWORD']='Test-admin-987654';server.init();cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=cls.http.serve_forever,daemon=True).start();cls.base='http://127.0.0.1:'+str(cls.http.server_port)
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.tmp.cleanup()
 def call(self,path,data=None,token=None):
  req=urllib.request.Request(self.base+'/api/'+path,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
  try:
   with urllib.request.urlopen(req) as r:return r.status,json.load(r)
  except urllib.error.HTTPError as e:return e.code,json.load(e)
 def test_full_flow(self):
  def reg(username,city):return self.call('register',dict(username=username,password='Strong-password-123',name_en='Test User',name_bn='পরীক্ষা',age=29,city=city))
  self.assertEqual(reg('admin','Dhaka')[0],400)
  a=reg('person_a','Dhaka')[1]['token'];b=reg('person_b','Rajshahi')[1]['token']
  self.assertEqual(reg('person_a','Dhaka')[0],409)
  self.assertEqual(reg('person_c','Bad city')[0],400)
  self.assertEqual(self.call('admin/data',token=a)[0],403)
  self.assertEqual(self.call('inbox')[0],401)
  admin=self.call('login',{'username':'admin','password':'Test-admin-987654'})[1]['token']
  self.assertEqual(self.call('request',{'body':'Need advice'},a)[0],200)
  data=self.call('admin/data',token=admin)[1];r=data['requests'][0];uid=r['uid']
  msg=dict(title_en='Update',title_bn='আপডেট',body_en='Team reply',body_bn='দলের উত্তর',priority='normal')
  self.assertEqual(self.call('admin/message',{**msg,'uid':uid,'request_id':r['id']},admin)[0],200)
  self.assertEqual(self.call('inbox',token=a)[1]['requests'][0]['status'],'answered')
  self.assertEqual(len(self.call('inbox',token=b)[1]['messages']),0)
  mid=self.call('inbox',token=a)[1]['messages'][0]['id']
  self.assertEqual(self.call('read',{'id':mid},b)[0],404)
  self.assertEqual(self.call('read',{'id':mid},a)[0],200)
  self.call('admin/message',{**msg,'city':'Dhaka'},admin)
  self.assertEqual(len(self.call('inbox',token=b)[1]['messages']),0)
  self.call('admin/message',msg,admin)
  self.assertEqual(len(self.call('inbox',token=b)[1]['messages']),1)
  self.assertEqual(self.call('admin/data',token=admin)[1]['messages'][-1]['read_count'],1)
  self.call('admin/user',{'id':uid,'active':False},admin)
  self.assertEqual(self.call('inbox',token=a)[0],403)
  self.call('logout',{},b)
  self.assertEqual(self.call('inbox',token=b)[0],401)
if __name__=='__main__':unittest.main()
