import base64
"""Private reporting, clinical review, exports, and daily notifications."""
import upgrade
import os,json,secrets,io,csv,zipfile,threading,datetime,html,re
from pathlib import Path
from xml.sax.saxutils import escape
from cryptography.fernet import Fernet
ROOT=Path(__file__).parent
CATEGORIES={
 'sexual': ['Sexual health','যৌন স্বাস্থ্য',['Pain during sex','যৌনমিলনে ব্যথা'],['Sexual function concern','যৌন সক্ষমতা নিয়ে উদ্বেগ'],['STI or infection concern','যৌনবাহিত সংক্রমণ নিয়ে উদ্বেগ'],['Genital discomfort','যৌনাঙ্গে অস্বস্তি'],['Contraception or safer sex','জন্মনিয়ন্ত্রণ বা নিরাপদ যৌনতা'],['Unwanted sexual contact / safety','অনাকাঙ্ক্ষিত যৌন সংস্পর্শ / নিরাপত্তা']],
 'reproductive':['Reproductive health','প্রজনন স্বাস্থ্য',['Period or bleeding concern','মাসিক বা রক্তপাত নিয়ে সমস্যা'],['Pregnancy concern','গর্ভাবস্থা নিয়ে উদ্বেগ'],['Postpartum concern','প্রসব-পরবর্তী সমস্যা'],['Fertility concern','সন্তান ধারণ নিয়ে উদ্বেগ'],['Pelvic pain','তলপেটে ব্যথা'],['Menopause concern','মেনোপজ নিয়ে উদ্বেগ']],
 'salinity':['Salinity exposure','লবণাক্ততার সংস্পর্শ',['Salty drinking water','লবণাক্ত পানীয় জল'],['Salty bathing water','গোসলের পানিতে লবণাক্ততা'],['Limited fresh water','মিঠা পানির সংকট'],['Water test result','পানি পরীক্ষার ফলাফল'],['Concern about health effects','স্বাস্থ্যগত প্রভাব নিয়ে উদ্বেগ']],
 'heat':['Heat exposure','তাপের সংস্পর্শ',['Overheating','অতিরিক্ত গরম লাগা'],['Thirst or dehydration concern','তৃষ্ণা বা পানিশূন্যতার উদ্বেগ'],['Dizziness','মাথা ঘোরা'],['Outdoor work exposure','বাইরে কাজের সময় তাপের সংস্পর্শ']],
 'cold':['Cold exposure','ঠান্ডার সংস্পর্শ',['Feeling very cold','অতিরিক্ত ঠান্ডা লাগা'],['Shivering','কাঁপুনি'],['Cold-related discomfort','ঠান্ডাজনিত অস্বস্তি']],
 'water':['Water and sanitation','পানি ও স্যানিটেশন',['Unsafe drinking water','অনিরাপদ পানীয় জল'],['Diarrhoea or vomiting','ডায়রিয়া বা বমি'],['Toilet or hygiene access','শৌচাগার বা পরিচ্ছন্নতার সুবিধা']],
 'rain_flood':['Rain and flooding','বৃষ্টি ও বন্যা',['Floodwater exposure','বন্যার পানির সংস্পর্শ'],['Injury or displacement','আঘাত বা স্থানচ্যুতি'],['Mosquito exposure','মশার উপদ্রব']],
 'urinary':['Urinary health','মূত্রসংক্রান্ত স্বাস্থ্য',['Pain when urinating','প্রস্রাবে ব্যথা'],['Frequent urination','ঘন ঘন প্রস্রাব'],['Other urinary concern','অন্যান্য প্রস্রাবের সমস্যা']],
 'skin':['Skin health','ত্বকের স্বাস্থ্য',['Itching or rash','চুলকানি বা ফুসকুড়ি'],['Sores or wounds','ঘা বা ক্ষত']],
 'respiratory':['Breathing and respiratory health','শ্বাসতন্ত্রের স্বাস্থ্য',['Cough','কাশি'],['Breathing concern','শ্বাস নিয়ে সমস্যা'],['Air pollution exposure','বায়ুদূষণের সংস্পর্শ']],
 'mental':['Emotional wellbeing','মানসিক সুস্থতা',['Stress or anxiety','চাপ বা উদ্বেগ'],['Sleep concern','ঘুমের সমস্যা'],['Low mood','মন খারাপ']],
 'general':['General health','সাধারণ স্বাস্থ্য',['Pain','ব্যথা'],['Fever','জ্বর'],['Fatigue','ক্লান্তি'],['Existing condition follow-up','আগের রোগের ফলো-আপ']],
 'other':['Other concern','অন্যান্য উদ্বেগ',['Describe in your own words','নিজের ভাষায় লিখুন']]
}
PAYLOAD_FIELDS=['description','onset','duration','severity','pregnancy','water_source','water_use','salinity_value','salinity_unit','measurement_type','allergies','medicines','history','safe_contact','contact_detail','contact_time','additional']
STATUS=['submitted','in_review','awaiting_information','referred','follow_up','closed']
KEY=None

def init(c):
 global KEY
 key=os.getenv('CLIMA_DATA_KEY')
 if not key:
  p=ROOT/'private'/'data.key';p.parent.mkdir(exist_ok=True)
  if not p.exists():
   fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
   with os.fdopen(fd,'wb') as f:f.write(Fernet.generate_key())
  key=p.read_bytes()
 KEY=Fernet(key.encode() if isinstance(key,str) else key)
 c.executescript('''
 CREATE TABLE IF NOT EXISTS app_settings(key TEXT PRIMARY KEY,value TEXT);
 CREATE TABLE IF NOT EXISTS staff(id INTEGER PRIMARY KEY,username TEXT UNIQUE,name TEXT,role TEXT,credential TEXT,password TEXT,active INTEGER DEFAULT 1);
 CREATE TABLE IF NOT EXISTS cases(id INTEGER PRIMARY KEY,uid INTEGER,categories TEXT,payload TEXT,status TEXT DEFAULT 'submitted',priority TEXT DEFAULT 'routine',assigned INTEGER,version INTEGER DEFAULT 1,consent_version TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP,updated TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS case_entries(id INTEGER PRIMARY KEY,case_id INTEGER,actor TEXT,kind TEXT,payload TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS notices(id INTEGER PRIMARY KEY,uid INTEGER,city TEXT,title_en TEXT,title_bn TEXT,body_en TEXT,body_bn TEXT,link_case INTEGER,source TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS notice_reads(uid INTEGER,nid INTEGER,PRIMARY KEY(uid,nid));
 CREATE TABLE IF NOT EXISTS schedules(id INTEGER PRIMARY KEY,title_en TEXT,title_bn TEXT,body_en TEXT,body_bn TEXT,city TEXT,at TEXT,active INTEGER DEFAULT 1,created TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS schedule_runs(schedule_id INTEGER,day TEXT,PRIMARY KEY(schedule_id,day));
 CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,actor TEXT,action TEXT,object_id TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
 ''')
 if not c.execute("SELECT value FROM app_settings WHERE key='default_daily'").fetchone():
  c.execute("INSERT INTO schedules(title_en,title_bn,body_en,body_bn,at) VALUES(?,?,?,?,?)",('Your daily CliMa check-in','আপনার দৈনিক CliMa খোঁজখবর','Check today’s weather, review your inbox, and update your care team if you have a concern.','আজকের আবহাওয়া ও ইনবক্স দেখুন। কোনো সমস্যা থাকলে সেবাদলকে জানান।','09:00'))
  c.execute("INSERT INTO app_settings VALUES('default_daily','1')")
def pack(d):return KEY.encrypt(json.dumps(d,ensure_ascii=False).encode()).decode()
def unpack(s):return json.loads(KEY.decrypt(s.encode()))
def audit(c,actor,action,obj=''):c.execute('INSERT INTO audit(actor,action,object_id) VALUES(?,?,?)',(actor,action,str(obj)))
def notice(c,uid=None,city=None,title_en='New update',title_bn='নতুন আপডেট',body_en='Sign in to view your update.',body_bn='আপডেট দেখতে সাইন ইন করুন।',case=None,source='admin'):
 cur=c.execute('INSERT INTO notices(uid,city,title_en,title_bn,body_en,body_bn,link_case,source) VALUES(?,?,?,?,?,?,?,?)',(uid,city,title_en,title_bn,body_en,body_bn,case,source))
 import push;push.enqueue(c,cur.lastrowid)
def run_daily(c,now=None):
 now=now or datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=6)));day=now.date().isoformat()
 for s in c.execute('SELECT * FROM schedules WHERE active=1 AND deleted=0').fetchall():
  if now.strftime('%H:%M')<s['at']:continue
  if (s['start_date'] and day<s['start_date']) or (s['end_date'] and day>s['end_date']):continue
  if s['frequency']=='once' and s['start_date']!=day:continue
  cur=c.execute('INSERT OR IGNORE INTO schedule_runs VALUES(?,?)',(s['id'],day))
  if cur.rowcount:
   notice(c,uid=s['uid'],city=s['city'],title_en=s['title_en'],title_bn=s['title_bn'],body_en=s['body_en'],body_bn=s['body_bn'],source=s['message_kind'] or 'daily')
   if s['message_kind'] in ['warning','advisory']:
    c.execute('INSERT INTO messages(uid,city,title_en,title_bn,body_en,body_bn,priority,message_kind,start_date,end_date) VALUES(?,?,?,?,?,?,?,?,?,?)',(s['uid'],s['city'],s['title_en'],s['title_bn'],s['body_en'],s['body_bn'],s['priority'],s['message_kind'],s['start_date'],s['end_date']))
   audit(c,'scheduler','daily_notification',s['id'])
def start_scheduler(db):
 def loop():
  while True:
   try:
    with db() as c:
     run_daily(c);upgrade.tick(c)
     c.execute("INSERT INTO app_settings(key,value) VALUES('scheduler_heartbeat',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(__import__('time').time()),))
    import push
    with db() as c:push.process(c)
   except Exception:
    import logging;logging.exception('CliMa scheduled job failed')
   threading.Event().wait(30)
 threading.Thread(target=loop,daemon=True).start()
def text(d,k,limit=4000,required=False):
 v=d.get(k,'')
 if not isinstance(v,str) or len(v)>limit or (required and not v.strip()):raise ValueError('Invalid '+k)
 return v.strip()
def case_data(c,r):
 o=dict(r);o['categories']=json.loads(o['categories']);o['report']=unpack(o.pop('payload'));o['entries']=[];o['patient']=dict(c.execute('SELECT id,name_en,name_bn,age,city FROM users WHERE id=?',(r['uid'],)).fetchone())
 for e in c.execute('SELECT * FROM case_entries WHERE case_id=? ORDER BY id',(r['id'],)):
  entry=dict(e);entry['data']=unpack(entry.pop('payload'));o['entries'].append(entry)
 return o

def route(h,c,path,d,uid,role,actor):
 staff=role in ['admin','clinician'];admin=role=='admin';post=h.command=='POST'
 q=__import__('urllib.parse',fromlist=['parse_qs']).parse_qs(__import__('urllib.parse',fromlist=['urlparse']).urlparse(h.path).query)
 def one(k,default=''):return q.get(k,[default])[0]
 def output(obj,status=200):h.send(status,obj);return True
 def denied():return output({'error':'Access denied'},403)
 if path=='/api/schema':return output({'categories':CATEGORIES,'statuses':STATUS,'fields':PAYLOAD_FIELDS})
 if path=='/api/cases' and post:
  if staff:return denied()
  client_id=str(d.get('client_id',''))
  if client_id:
   if not re.fullmatch('[a-zA-Z0-9-]{16,80}',client_id):raise ValueError('Invalid submission ID')
   saved=c.execute('SELECT case_id FROM submissions WHERE uid=? AND client_id=?',(uid,client_id)).fetchone()
   if saved:return output({'id':saved['case_id']})
  cats=d.get('categories');sym=d.get('symptoms',{})
  if not isinstance(cats,list) or not cats or len(cats)>len(CATEGORIES) or any(x not in CATEGORIES for x in cats):raise ValueError('Choose a category')
  if d.get('consent') is not True:raise ValueError('Consent required')
  if c.execute('SELECT 1 FROM care_consent WHERE uid=? AND paused=1',(uid,)).fetchone():raise ValueError('Resume care sharing in Privacy before submitting a new report')
  if not isinstance(sym,dict) or any(k not in cats for k in sym):raise ValueError('Invalid symptoms')
  for k,values in sym.items():
   if not isinstance(values,list) or any(not isinstance(i,int) or i<0 or i>=len(CATEGORIES[k])-2 for i in values):raise ValueError('Invalid symptoms')
  p={k:text(d,k,4000,k in ['description','severity']) for k in PAYLOAD_FIELDS};p['symptoms']=sym
  if 'seasonal' in d:
   import seasonal;p['seasonal']=seasonal.validate(d['seasonal'])
  if p['severity'] not in ['mild','moderate','severe','unsure']:raise ValueError('Invalid severity')
  if p['onset']:
   date=datetime.date.fromisoformat(p['onset'])
   if date>datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=6))).date():raise ValueError('Future onset')
  if p['salinity_value']:
   if not re.fullmatch(r'\d+(\.\d+)?',p['salinity_value']) or not p['salinity_unit'] or not p['measurement_type']:raise ValueError('Measurement needs value, type and units')
  c.execute("UPDATE identity_sequence SET value=MAX(value,(SELECT COALESCE(MAX(id),0) FROM cases))+1 WHERE name='cases'")
  case_id=c.execute("SELECT value FROM identity_sequence WHERE name='cases'").fetchone()[0]
  cur=c.execute('INSERT INTO cases(id,uid,categories,payload,consent_version) VALUES(?,?,?,?,?)',(case_id,uid,json.dumps(list(dict.fromkeys(cats))),pack(p),'health-sharing-v1'))
  if client_id:c.execute('INSERT INTO submissions VALUES(?,?,?)',(uid,client_id,cur.lastrowid))
  audit(c,actor,'case_create',cur.lastrowid)
  c.execute('INSERT INTO consent_events(uid,case_id,action,version) VALUES(?,?,?,?)',(uid,cur.lastrowid,'granted','health-sharing-v1'))
  upgrade.staff_notice(c,cur.lastrowid,'New health report')
  if c.execute('SELECT age FROM users WHERE id=?',(uid,)).fetchone()['age']<18:upgrade.staff_notice(c,cur.lastrowid,'Safeguarding review needed for young user')
  notice(c,uid=uid,title_en='Report received',title_bn='রিপোর্ট গ্রহণ করা হয়েছে',case=cur.lastrowid,source='case')
  return output({'id':cur.lastrowid})
 if path=='/api/cases' and not post:
  sql='SELECT cases.*,users.name_en,users.name_bn,users.city FROM cases JOIN users ON users.id=cases.uid';args=[]
  if not staff:sql+=' WHERE uid=?';args=[uid]
  elif role=='clinician':sql+=' WHERE NOT EXISTS(SELECT 1 FROM care_consent WHERE care_consent.uid=cases.uid AND paused=1) AND (assigned=? OR EXISTS(SELECT 1 FROM access_grants WHERE case_id=cases.id AND staff_id=? AND expires>?))';args=[-uid,-uid,__import__('time').time()]
  rows=[]
  for r in c.execute(sql+' ORDER BY cases.id DESC',args):
   r=dict(r);r.pop('payload');r['categories']=json.loads(r['categories']);rows.append(r)
  return output({'cases':rows})
 if path=='/api/case':
  cid=int(d.get('id') if post else one('id'));r=c.execute('SELECT * FROM cases WHERE id=?',(cid,)).fetchone()
  if not r or not upgrade.allowed(c,r,uid,role):return denied()
  if not post:
   audit(c,actor,'case_view',cid);return output(case_data(c,r))
  kind=d.get('kind')
  if kind=='update' and not staff:
   p={'note':text(d,'note',4000,True)};kind='user_update'
  elif kind=='workflow' and staff:
   if int(d.get('version',0))!=r['version']:return output({'error':'Case changed. Refresh before saving.'},409)
   status=d.get('status');priority=d.get('priority');assigned=int(d['assigned']) if d.get('assigned') else None
   if role=='clinician' and assigned!=r['assigned']:return denied()
   if status not in STATUS or priority not in ['routine','priority','urgent']:raise ValueError('Invalid workflow')
   if assigned and not c.execute("SELECT id FROM staff WHERE id=? AND role='clinician' AND active=1",(assigned,)).fetchone():raise ValueError('Unknown clinician')
   p={'status':status,'priority':priority,'assigned':assigned,'note':text(d,'note')}
   c.execute('UPDATE cases SET status=?,priority=?,assigned=? WHERE id=?',(status,priority,assigned,cid))
  elif kind=='assessment' and role=='clinician':
   p={k:text(d,k,6000,k in ['assessment','diagnosis_status','plan']) for k in ['assessment','diagnosis','diagnosis_status','tests','plan','referral','follow_up','advice_en','advice_bn']}
   if p['diagnosis_status'] not in ['not_determined','provisional','confirmed']:raise ValueError('Invalid diagnosis status')
   if p['diagnosis_status']!='not_determined' and not p['diagnosis']:raise ValueError('Diagnosis description required')
   if p['follow_up']:datetime.date.fromisoformat(p['follow_up'])
   p['observations']=upgrade.observations(d.get('observations',{}))
   if p['follow_up']:
    at=p['follow_up']+'T10:00:00+06:00'
    if not c.execute("SELECT id FROM appointments WHERE case_id=? AND at=? AND status='scheduled'",(cid,at)).fetchone():c.execute('INSERT INTO appointments(case_id,uid,staff_id,at,notes) VALUES(?,?,?,?,?)',(cid,r['uid'],-uid,at,pack('Clinical follow-up')))
   s=c.execute('SELECT name,credential FROM staff WHERE id=?',(-uid,)).fetchone();p['clinician']=s['name'];p['credential']=s['credential']
  elif kind=='note' and staff:p={'note':text(d,'note',4000,True)}
  else:return denied()
  c.execute('INSERT INTO case_entries(case_id,actor,kind,payload) VALUES(?,?,?,?)',(cid,actor,kind,pack(p)))
  c.execute('UPDATE cases SET version=version+1,updated=CURRENT_TIMESTAMP WHERE id=?',(cid,));audit(c,actor,kind,cid)
  if not staff:upgrade.staff_notice(c,cid,'Patient added information')
  if kind=='workflow':upgrade.staff_notice(c,cid,'Case workflow updated')
  if staff:notice(c,uid=r['uid'],title_en='Your case has an update',title_bn='আপনার কেসে নতুন আপডেট আছে',case=cid,source='case')
  return output({'ok':True})
 if path=='/api/staff':
  if not staff:return denied()
  if post:
   if not admin:return denied()
   from server import pw
   username=text(d,'username',40,True).lower();password=text(d,'password',256,True);r=text(d,'role');name=text(d,'name',100,True);credential=text(d,'credential',200)
   if r not in ['admin','clinician'] or not re.fullmatch('[a-z0-9_]{3,40}',username) or username=='admin' or len(password)<12:raise ValueError('Invalid staff account')
   if r=='clinician' and not credential:raise ValueError('Clinician credential required')
   if c.execute('SELECT id FROM users WHERE username=?',(username,)).fetchone():raise ValueError('Username in use')
   cur=c.execute('INSERT INTO staff(username,name,role,credential,password) VALUES(?,?,?,?,?)',(username,name,r,credential,pw(password)));audit(c,actor,'staff_create',cur.lastrowid)
  return output({'staff':[dict(r) for r in c.execute('SELECT id,username,name,role,credential,active FROM staff')]})
 if path=='/api/staff/toggle' and post:
  if not admin:return denied()
  sid=int(d['id'])
  if -uid==sid:return output({'error':'You cannot disable your own account'},400)
  c.execute('UPDATE staff SET active=? WHERE id=?',(int(bool(d.get('active'))),sid));c.execute('DELETE FROM sessions WHERE uid=?',(-sid,));audit(c,actor,'staff_toggle',sid);return output({'ok':True})
 if path=='/api/notifications':
  if staff:
   if post:
    nid=int(d.get('id',0))
    for row in c.execute('SELECT id FROM notices WHERE uid=? AND (?=0 OR id=?)',(uid,nid,nid)):c.execute('INSERT OR IGNORE INTO notice_reads VALUES(?,?)',(uid,row['id']))
   rows=[dict(r) for r in c.execute('SELECT notices.*,EXISTS(SELECT 1 FROM notice_reads WHERE uid=? AND nid=notices.id) AS is_read FROM notices WHERE notices.uid=? ORDER BY id DESC',(uid,uid))]
   return output({'notifications':rows,'unread':sum(not x['is_read'] for x in rows)})
  u=c.execute('SELECT city FROM users WHERE id=?',(uid,)).fetchone()
  if post:
   nid=int(d.get('id',0))
   rows=c.execute('SELECT id FROM notices WHERE (uid=? OR (uid IS NULL AND (city IS NULL OR city=?))) AND (?=0 OR id=?)',(uid,u['city'],nid,nid)).fetchall()
   for r in rows:c.execute('INSERT OR IGNORE INTO notice_reads VALUES(?,?)',(uid,r['id']))
  rows=[dict(r) for r in c.execute('SELECT notices.*,EXISTS(SELECT 1 FROM notice_reads WHERE uid=? AND nid=notices.id) AS is_read FROM notices WHERE notices.uid=? OR (notices.uid IS NULL AND (city IS NULL OR city=?)) ORDER BY id DESC',(uid,uid,u['city']))]
  pref=c.execute('SELECT daily FROM preferences WHERE uid=?',(uid,)).fetchone()
  if pref and not pref['daily']:rows=[n for n in rows if n['source']!='daily']
  return output({'notifications':rows,'unread':sum(not x['is_read'] for x in rows)})
 if path=='/api/admin/schedules':
  if not admin:return denied()
  if post:
   if d.get('id'):
    c.execute('UPDATE schedules SET active=? WHERE id=?',(int(bool(d.get('active'))),int(d['id'])));audit(c,actor,'schedule_toggle',d['id'])
   else:
    p=[text(d,k,4000,True) for k in ['title_en','title_bn','body_en','body_bn']];at=text(d,'at');city=d.get('city') or None
    if not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d',at) or city not in [None,'Dhaka','Noakhali','Rajshahi']:raise ValueError('Invalid schedule')
    cur=c.execute('INSERT INTO schedules(title_en,title_bn,body_en,body_bn,city,at) VALUES(?,?,?,?,?,?)',(*p,city,at));audit(c,actor,'schedule_create',cur.lastrowid)
  return output({'schedules':[dict(r) for r in c.execute('SELECT * FROM schedules ORDER BY id DESC')]})
 if path=='/api/admin/audit':
  if not admin:return denied()
  return output({'audit':[dict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 500')]})
 if path in ['/api/admin/export','/api/admin/user-record','/api/admin/export-columns']:
  if not admin:return denied()
  target=int(one('uid','0'));users=[dict(r) for r in c.execute('SELECT id,username,name_en,name_bn,age,city,active FROM users'+(' WHERE id=?' if target else ''),[target] if target else [])]
  if target and not users:return output({'error':'User not found'},404)
  datasets=export_data(c,users)
  if path.endswith('/export-columns'):return output({'columns':{name:sorted({key for row in rows for key in row}) for name,rows in datasets.items()}})
  if path.endswith('/export'):datasets=upgrade.filter_export(c,datasets,{k:v for k,v in q.items() if k!='columns'} if one('format')=='bundle' else q,actor)
  audit(c,actor,'export_'+one('format','json'),target or 'all')
  if path.endswith('user-record'):return output(datasets)
  fmt=one('format')
  if fmt=='bundle':
   if one('anonymized')=='1':raise ValueError('Anonymous exports cannot contain private documents')
   docs=datasets.get('Documents',[])
   if sum(int(r['size']) for r in docs)>50*1024*1024:raise ValueError('Document bundle exceeds 50 MB; narrow the export filters')
   bio=io.BytesIO()
   with zipfile.ZipFile(bio,'w',zipfile.ZIP_DEFLATED) as z:
    z.writestr('records.xlsx',xlsx(datasets))
    for document in docs:
     row=c.execute('SELECT payload,mime FROM attachments WHERE id=?',(document['id'],)).fetchone()
     if not row:continue
     extension={'application/pdf':'.pdf','image/png':'.png','image/jpeg':'.jpg'}[row['mime']]
     z.writestr('documents/'+str(document['id'])+extension,base64.b64decode(unpack(row['payload'])))
    z.writestr('README.txt','Confidential export. Document filenames use their IDs from the Documents worksheet. Protect this plaintext archive after download.')
   body=bio.getvalue();mime='application/zip';ext='zip'
  elif fmt=='xlsx':body=xlsx(datasets);mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';ext='xlsx'
  elif fmt=='csv':
   bio=io.BytesIO()
   with zipfile.ZipFile(bio,'w',zipfile.ZIP_DEFLATED) as z:
    for name,rows in datasets.items():
     buf=io.StringIO();writer=csv.writer(buf);headers=list(dict.fromkeys(k for row in rows for k in row)) if rows else ['কোনো তথ্য নেই'];writer.writerow(headers)
     for row in rows:writer.writerow([csv_safe(string(row.get(k,''))) for k in headers])
     z.writestr(name+'.csv','\ufeff'+buf.getvalue())
   body=bio.getvalue();mime='application/zip';ext='zip'
  elif fmt=='pdf':body=pdf_bytes(datasets);mime='application/pdf';ext='pdf'
  else:raise ValueError('Invalid export format')
  h.send_response(200);h.send_header('Content-Type',mime);h.send_header('Cache-Control','no-store');h.send_header('X-Content-Type-Options','nosniff');h.send_header('Content-Disposition',f'inline; filename="clima-records-{target or "all"}.{ext}"');h.end_headers();h.wfile.write(body);return True
 return False

def seasonal_columns(s):
 if not isinstance(s,dict):return {}
 out={};kind=s.get('kind');labels={'heat':'গরম','rain':'বৃষ্টি','cold':'শীত'}
 out['জরিপের ধরন']={'climate':'স্থানীয় জলবায়ু','disaster':'স্থানীয় জলবায়ু দুর্যোগ','reproductive':'প্রজনন স্বাস্থ্য'}.get(kind,kind)
 for row in s.get('rows',[]):
  if kind=='climate':
   season,level=row['key'].split('_');prefix=labels[season]+' — '+['হালকা','মোটামুটি','অনেক বেশি'][int(level)]
   out[prefix+' — অবস্থা']={'observed':'পর্যবেক্ষণ করেছেন','none':'হয় না','unknown':'মনে নেই'}.get(row.get('state'),row.get('state'))
   out[prefix+' — মাস']=row.get('month','');out[prefix+' — দিন']=row.get('days','')
  else:
   prefix=row['month'];out[prefix+' — নির্বাচিত সমস্যা']='; '.join(row.get('choices',[]));out[prefix+' — অন্যান্য বিবরণ']=row.get('other','')
 return out

def export_data(c,users):
 import registration
 users=[{**u,**registration.export(c,u['id'])} for u in users]
 out={'Users':users,'Cases':[],'Case history':[],'Requests':[],'Messages':[],'Notifications':[],'Appointments':[],'Documents':[],'Consent history':[],'Privacy requests':[]}
 for u in users:
  for r in c.execute('SELECT * FROM cases WHERE uid=? ORDER BY id',(u['id'],)):
   case=case_data(c,r);entries=case.pop('entries');payload=case.pop('report');case.update(payload);case.update(seasonal_columns(payload.get('seasonal')));out['Cases'].append(case)
   for e in entries:
    data=e.pop('data');out['Case history'].append({'user_id':u['id'],**e,**{k:data.get(k,'') for k in ['note','status','priority','assigned','assessment','diagnosis','diagnosis_status','tests','plan','referral','follow_up','advice_en','advice_bn','clinician','credential','observations']}})
  out['Appointments'] += [{**dict(r),'notes':unpack(r['notes'])} for r in c.execute('SELECT * FROM appointments WHERE uid=?',(u['id'],))]
  out['Documents'] += [{**dict(r),'name':unpack(r['name'])} for r in c.execute('SELECT a.id,a.case_id,a.name,a.mime,a.size,a.created FROM attachments a JOIN cases c ON c.id=a.case_id WHERE c.uid=?',(u['id'],))]
  out['Consent history'] += [dict(r) for r in c.execute('SELECT * FROM consent_events WHERE uid=?',(u['id'],))]
  out['Privacy requests'] += [{**dict(r),'detail':unpack(r['detail']),'response':unpack(r['response']) if r['response'] else ''} for r in c.execute('SELECT * FROM privacy_requests WHERE uid=?',(u['id'],))]
  out['Requests'] += [dict(r) for r in c.execute('SELECT * FROM requests WHERE uid=?',(u['id'],))]
  out['Messages'] += [{'recipient_id':u['id'],**dict(r)} for r in c.execute('SELECT messages.*,EXISTS(SELECT 1 FROM reads WHERE uid=? AND mid=messages.id) AS is_read FROM messages WHERE uid=? OR (uid IS NULL AND (city IS NULL OR city=?))',(u['id'],u['id'],u['city']))]
  out['Notifications'] += [{'recipient_id':u['id'],**dict(r)} for r in c.execute('SELECT notices.*,EXISTS(SELECT 1 FROM notice_reads WHERE uid=? AND nid=notices.id) AS is_read FROM notices WHERE uid=? OR (uid IS NULL AND (city IS NULL OR city=?))',(u['id'],u['id'],u['city']))]
 return out

def string(v):return json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else str(v) if v is not None else ''
def csv_safe(s):return "'"+s if s.lstrip().startswith(('=','+','-','@')) or s.startswith(('\t','\r','\n')) else s

def xlsx(data):
 """Portable OOXML export; all values use inline strings, never formulas."""
 out=io.BytesIO();ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
 def col(i):
  s=''
  while i:i,r=divmod(i-1,26);s=chr(65+r)+s
  return s
 def clean(s):return ''.join(ch for ch in s if ch in '\n\r\t' or ord(ch)>=32)
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  overrides=''
  for i,(name,rows) in enumerate(data.items(),1):
   headers=list(dict.fromkeys(k for row in rows for k in row)) if rows else ['কোনো তথ্য নেই'];matrix=[headers]+[[string(r.get(k,'')) for k in headers] for r in rows]
   xml=f'<worksheet xmlns="{ns}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="{len(headers)}" width="24" customWidth="1"/></cols><sheetData>'
   for ri,row in enumerate(matrix,1):
    xml+=f'<row r="{ri}">'+''.join(f'<c r="{col(ci)}{ri}" t="inlineStr"><is><t xml:space="preserve">{escape(clean(string(v)))}</t></is></c>' for ci,v in enumerate(row,1))+'</row>'
   xml+=f'</sheetData><autoFilter ref="A1:{col(len(headers))}{len(matrix)}"/></worksheet>';z.writestr(f'xl/worksheets/sheet{i}.xml',xml)
   overrides+=f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
  z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'+overrides+'</Types>')
  z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
  z.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>' for i,name in enumerate(data,1))+'</sheets></workbook>')
  z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(data)+1))+'</Relationships>')
 return out.getvalue()
def print_html(data):
 body=''
 for name,rows in data.items():
  body+=f'<section><h2>{html.escape(name)}</h2>'
  for row in rows:
   body+='<article>'+''.join(f'<div class="field"><b>{html.escape(k)}</b><div>{html.escape(string(v))}</div></div>' for k,v in row.items())+'</article>'
  if not rows:body+='<p>No records / কোনো তথ্য নেই</p>'
  body+='</section>'
 return '''<!doctype html><html><head><meta charset="utf-8"><title>CliMa confidential case records</title><style>@page{size:A4;margin:18mm}body{font:12px/1.6 system-ui,'Noto Sans Bengali',sans-serif;color:#173c35;max-width:850px;margin:25px auto}h1{font-size:26px}h2{border-bottom:2px solid #174e45;padding-bottom:8px}article{border-bottom:1px solid #b9c9c0;padding:15px 0}.field{display:grid;grid-template-columns:170px 1fr;gap:20px;padding:5px 0;break-inside:avoid}.field div{white-space:pre-wrap;overflow-wrap:anywhere}h2{break-after:avoid}section{break-before:page}section:first-of-type{break-before:auto}button{padding:12px;background:#174e45;color:white;border:0;border-radius:8px}@media print{button,.hint{display:none}body{margin:0}section{break-before:page}}</style></head><body><button onclick="window.print()">Print / Save as PDF · PDF হিসেবে সংরক্ষণ</button><p class="hint">Select “Save as PDF” in the print dialog. Contains private health records; share only with authorized care staff.</p><h1>CliMa · Confidential records</h1><p>Patient-reported data and clinician-authored assessments. Not an automated diagnosis.</p>'''+body+'</body></html>'

def pdf_bytes(data):
 """Generate a paginated UTF-8 PDF with complex-script shaping."""
 import pymupdf
 parts=['<h1>CliMa | Confidential care records</h1><p>Patient-reported information and clinician-authored assessments. Not an automated diagnosis.</p>']
 for name,rows in data.items():
  parts.append('<h2>'+html.escape(name)+'</h2>')
  if not rows:parts.append('<p>No records / কোনো তথ্য নেই</p>')
  for n,row in enumerate(rows,1):
   parts.append('<h3>Record '+str(n)+'</h3>')
   for key,value in row.items():
    val=html.escape(string(value)).replace('\n','<br>')
    parts.append('<p><b>'+html.escape(key.replace('_',' '))+'</b><br>'+val+'</p>')
 css='body{font-family:sans-serif;font-size:10pt;color:#203d34}h1{font-size:22pt;color:#174e45}h2{font-size:16pt;border-bottom:1pt solid #174e45;margin-top:20pt}h3{font-size:11pt;color:#62776a}p{margin:5pt 0 10pt;line-height:1.45}b{font-size:9pt;color:#577062}'
 story=pymupdf.Story(html=''.join(parts),user_css=css);buf=io.BytesIO();writer=pymupdf.DocumentWriter(buf)
 page=pymupdf.Rect(0,0,595,842);rect=pymupdf.Rect(45,48,550,795);more=True
 while more:
  dev=writer.begin_page(page);more,_=story.place(rect);story.draw(dev);writer.end_page()
 writer.close()
 doc=pymupdf.open(stream=buf.getvalue(),filetype='pdf')
 for i,p in enumerate(doc):p.insert_text((45,820),f'CONFIDENTIAL | CliMa | Page {i+1} of {len(doc)}',fontsize=8,color=(.4,.45,.4))
 result=doc.tobytes(garbage=4,deflate=True);doc.close();return result
