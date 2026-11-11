import unittest,sqlite3,os
from test_upgrade import UpgradeFlow
import seasonal,server
from input_normalization import normalize_answers
class SeasonalFlow(UpgradeFlow):
 def test_scheduled_warning_permissions_and_once_delivery(self):
  import datetime,clinical
  day=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=6))).date()+datetime.timedelta(days=1)
  msg=dict(message_kind='warning',title_en='Scheduled warning',title_bn='আগাম সতর্কতা',body_en='Notice',body_bn='বার্তা',start_date=day.isoformat(),end_date=day.isoformat(),at='09:00')
  self.assertEqual(self.call('admin/message',msg,self.user)[0],403)
  self.assertEqual(self.call('admin/schedules',token=self.user)[0],403)
  self.assertEqual(self.call('admin/data',token=self.user)[0],403)
  status,result=self.call('admin/message',msg,self.admin)
  self.assertEqual(status,200,result);self.assertTrue(result['scheduled'])
  self.assertEqual(self.call('inbox',token=self.user)[1]['messages'],[])
  with server.db() as c:
   early=datetime.datetime.combine(day,datetime.time(8,59))
   clinical.run_daily(c,early)
   self.assertEqual(c.execute('SELECT COUNT(*) FROM messages').fetchone()[0],0)
   due=early.replace(hour=9,minute=0)
   clinical.run_daily(c,due);clinical.run_daily(c,due)
   self.assertEqual(c.execute('SELECT COUNT(*) FROM messages').fetchone()[0],1)
  self.assertEqual(self.call('inbox',token=self.user)[1]['messages'][0]['message_kind'],'warning')
 def test_surveys(self):
  for kind in ['climate','disaster','reproductive']:
   rows=([dict(key=k+'_'+str(i),state='observed',month='বৈশাখ',days='১০ দিন') for k in ['heat','rain','cold'] for i in range(3)] if kind=='climate' else [dict(month=m,choices=['কোনোটিই নয়'],other='') for m in seasonal.MONTHS])
   data=dict(version=1,kind=kind,basis='year',year='১৪৩৩',rows=rows)
   status,res=self.call('cases',dict(categories=['other'],description='Seasonal report',severity='unsure',consent=True,seasonal=data),self.user);self.assertEqual(status,200,res)
   self.assertEqual(self.call('case?id='+str(res['id']),token=self.user)[1]['report']['seasonal'],normalize_answers(data))
   with (__import__('psycopg').connect(os.environ['CLIMA_TEST_POSTGRES'],sslmode='disable',options='-c search_path=clima,public') if os.getenv('CLIMA_TEST_POSTGRES') else sqlite3.connect(server.DB)) as c:self.assertNotIn('বৈশাখ',c.execute('SELECT payload FROM cases WHERE id='+str(int(res['id']))).fetchone()[0])
   other=self.register('other_'+kind);self.assertEqual(self.call('case?id='+str(res['id']),token=other)[0],403)
   data['rows'].pop();self.assertRaises(ValueError,seasonal.validate,data)
  data=dict(version=1,kind='disaster',basis='typical',rows=[dict(month=m,choices=['কোনোটিই নয়','বন্যা']) for m in seasonal.MONTHS]);self.assertRaises(ValueError,seasonal.validate,data)
 def test_messages(self):
  remote=self.call('register',dict(username='remote_user',password='Patient-password-123',name_en='Remote',name_bn='নমুনা',age=30,city='Rajshahi'))[1]['token']
  for kind in ['warning','advisory']:
   msg=dict(message_kind=kind,title_en='Test '+kind,title_bn='নমুনা '+kind,body_en='Sample body',body_bn='নমুনা বার্তা',city='Dhaka',priority='important')
   self.assertEqual(self.call('admin/message',msg,self.user)[0],403)
   self.assertEqual(self.call('admin/message',msg,self.admin)[0],200)
   self.assertEqual(self.call('inbox',token=self.user)[1]['messages'][0]['message_kind'],kind)
   n=self.call('notifications',token=self.user)[1]['notifications'][0];self.assertEqual(n['source'],kind);self.assertEqual(n['body_bn'],msg['body_bn'])
   self.assertEqual(self.call('inbox',token=remote)[1]['messages'],[])
  self.assertEqual(self.call('admin/message',dict(msg,message_kind='invalid'),self.admin)[0],400)
