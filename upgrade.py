"""CliMa v4 account, access, appointment, document and privacy workflows."""
import os,json,time,datetime,secrets,hashlib,hmac,base64,struct,io,re
from urllib.parse import urlparse,parse_qs
import clinical as cl

def init(c):
 import push,recovery_mail,retention,admin_crud;push.init(c);recovery_mail.init(c);retention.init(c);admin_crud.init(c)
 c.executescript('''
 CREATE TABLE IF NOT EXISTS identity_sequence(name TEXT PRIMARY KEY,value INTEGER);
 CREATE TABLE IF NOT EXISTS security(uid INTEGER PRIMARY KEY,totp TEXT,enabled INTEGER DEFAULT 0,pending TEXT,recovery TEXT,last_counter INTEGER DEFAULT -1);
 CREATE TABLE IF NOT EXISTS access_grants(case_id INTEGER,staff_id INTEGER,expires REAL,reason TEXT,PRIMARY KEY(case_id,staff_id));
 CREATE TABLE IF NOT EXISTS appointments(id INTEGER PRIMARY KEY,case_id INTEGER,uid INTEGER,staff_id INTEGER,at TEXT,status TEXT DEFAULT 'scheduled',notes TEXT,reminded INTEGER DEFAULT 0,created TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS attachments(id INTEGER PRIMARY KEY,case_id INTEGER,uid INTEGER,name TEXT,mime TEXT,size INTEGER,payload TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS preferences(uid INTEGER PRIMARY KEY,quiet_start TEXT DEFAULT '22:00',quiet_end TEXT DEFAULT '08:00',daily INTEGER DEFAULT 1);
 CREATE TABLE IF NOT EXISTS privacy_requests(id INTEGER PRIMARY KEY,uid INTEGER,kind TEXT,detail TEXT,status TEXT DEFAULT 'pending',response TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS consent_events(id INTEGER PRIMARY KEY,uid INTEGER,case_id INTEGER,action TEXT,version TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS job_runs(key TEXT PRIMARY KEY,created TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS care_consent(uid INTEGER PRIMARY KEY,paused INTEGER DEFAULT 0,updated TEXT DEFAULT CURRENT_TIMESTAMP);
 CREATE TABLE IF NOT EXISTS submissions(uid INTEGER,client_id TEXT,case_id INTEGER,PRIMARY KEY(uid,client_id));
 ''')
 c.execute("INSERT INTO identity_sequence(name,value) VALUES('users',(SELECT COALESCE(MAX(id),0) FROM users)) ON CONFLICT(name) DO NOTHING")
 c.execute("INSERT INTO identity_sequence(name,value) VALUES('cases',(SELECT COALESCE(MAX(id),0) FROM cases)) ON CONFLICT(name) DO NOTHING")
 for table,column,decl in [('schedules','start_date',"TEXT DEFAULT ''"),('schedules','end_date',"TEXT DEFAULT ''"),('schedules','frequency',"TEXT DEFAULT 'daily'"),('sessions','created','REAL'),('sessions','device',"TEXT DEFAULT ''")]:
  if column not in [r['name'] for r in c.execute('PRAGMA table_info('+table+')')]:c.execute(f'ALTER TABLE {table} ADD COLUMN {column} {decl}')

def allowed(c,r,uid,role):
 if role=='admin':return True
 if role=='user':return r['uid']==uid
 if c.execute('SELECT 1 FROM care_consent WHERE uid=? AND paused=1',(r['uid'],)).fetchone():return False
 if r['assigned']==-uid:return True
 return bool(c.execute('SELECT 1 FROM access_grants WHERE case_id=? AND staff_id=? AND expires>?',(r['id'],-uid,time.time())).fetchone())
def case(c,cid,uid,role):
 r=c.execute('SELECT * FROM cases WHERE id=?',(cid,)).fetchone()
 if not r or not allowed(c,r,uid,role):raise PermissionError('Case access denied')
 return r

def staff_notice(c,cid,title='Case needs attention'):
 r=c.execute('SELECT assigned FROM cases WHERE id=?',(cid,)).fetchone()
 targets={0}|{-s['id'] for s in c.execute("SELECT id FROM staff WHERE role='admin' AND active=1")}
 if r and r['assigned']:targets.add(-r['assigned'])
 for uid in targets:cl.notice(c,uid=uid,title_en=title,title_bn='কেসে মনোযোগ প্রয়োজন',case=cid,source='case')

def code_at(secret,counter):
 digest=hmac.new(base64.b32decode(secret),struct.pack('>Q',counter),hashlib.sha1).digest();i=digest[-1]&15
 return str((struct.unpack('>I',digest[i:i+4])[0]&0x7fffffff)%1000000).zfill(6)
def verify_totp(c,uid,code,secret=None,consume=True):
 s=c.execute('SELECT * FROM security WHERE uid=?',(uid,)).fetchone()
 if not secret:
  if not s or not s['enabled']:return False
  secret=cl.unpack(s['totp'])
 counter=int(time.time()/30)
 for offset in [-1,0,1]:
  n=counter+offset
  if s and n<=s['last_counter']:continue
  if hmac.compare_digest(code_at(secret,n),str(code)):
   if consume:c.execute('UPDATE security SET last_counter=? WHERE uid=?',(n,uid))
   return True
 return False

def verify_password(c,uid,password):
 from server import validpw
 if uid==0:
  stored=c.execute("SELECT value FROM app_settings WHERE key='admin_password_hash'").fetchone()
  return validpw(password,stored['value']) if stored else hmac.compare_digest(password,os.getenv('CLIMA_ADMIN_PASSWORD',''))
 table='users' if uid>0 else 'staff';r=c.execute(f'SELECT password FROM {table} WHERE id=?',(abs(uid),)).fetchone()
 return bool(r and validpw(password,r['password']))
def set_password(c,uid,password):
 from server import pw
 if not isinstance(password,str) or not 12<=len(password)<=256:raise ValueError('Use a password of 12–256 characters')
 if uid==0:c.execute("INSERT INTO app_settings VALUES('admin_password_hash',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(pw(password),))
 else:c.execute('UPDATE '+('users' if uid>0 else 'staff')+' SET password=? WHERE id=?',(pw(password),abs(uid)))
 c.execute('DELETE FROM sessions WHERE uid=?',(uid,))

def tick(c,now=None):
 import retention;retention.tick(c,now)
 c.execute('DELETE FROM email_challenges WHERE expires<?',(time.time()-86400,))
 now=now or datetime.datetime.now(datetime.timezone.utc);utc=now.astimezone(datetime.timezone.utc).isoformat(timespec='minutes')
 for r in c.execute("SELECT * FROM appointments WHERE status='scheduled'").fetchall():
  at=datetime.datetime.fromisoformat(r['at']);delta=(at-now).total_seconds()
  if 0<=delta<=86400 and not r['reminded']:
   cl.notice(c,uid=r['uid'],title_en='Upcoming appointment',title_bn='আসন্ন সাক্ষাৎ',case=r['case_id'],source='appointment')
   staff_notice(c,r['case_id'],'Upcoming appointment');c.execute('UPDATE appointments SET reminded=1 WHERE id=?',(r['id'],))
  if delta < -86400:
   c.execute("UPDATE appointments SET status='missed' WHERE id=?",(r['id'],));staff_notice(c,r['case_id'],'Missed appointment: follow-up needed')
 day=now.date().isoformat()
 for r in c.execute("SELECT id FROM cases WHERE status='submitted' AND created<datetime('now','-24 hours')"):
  if c.execute('INSERT OR IGNORE INTO job_runs(key) VALUES(?)',(f'overdue:{r["id"]}:{day}',)).rowcount:staff_notice(c,r['id'],'Report overdue for review')

def route(h,c,path,d,uid,role,actor):
 q=parse_qs(urlparse(h.path).query);get=lambda k,default='':q.get(k,[default])[0];post=h.command=='POST'
 def send(data,status=200):h.send(status,data);return True
 if path=='/api/admin/crud':
  import admin_crud
  return admin_crud.route(h,c,d,uid,role,actor)
 if path=='/api/retention':
  import retention
  return retention.route(h,c,d,role,actor)
 if path=='/api/device' and post:
  if role=='user' and c.execute('SELECT 1 FROM care_consent WHERE uid=? AND paused=1',(uid,)).fetchone():return send({'ok':True,'paused':True})
  value=cl.text(d,'token',4096,True);digest=hashlib.sha256(value.encode()).hexdigest()
  previous=c.execute('SELECT id,uid FROM devices WHERE token_hash=?',(digest,)).fetchone()
  if previous and previous['uid']!=uid:c.execute('DELETE FROM push_outbox WHERE device_id=?',(previous['id'],))
  c.execute('INSERT INTO devices(uid,token,token_hash) VALUES(?,?,?) ON CONFLICT(token_hash) DO UPDATE SET uid=excluded.uid,token=excluded.token,active=1',(uid,cl.pack(value),digest));return send({'ok':True})
 if path=='/api/push-status':
  if role!='admin':raise PermissionError()
  return send({'configured':bool(os.getenv('FIREBASE_PROJECT_ID') and (os.getenv('GOOGLE_APPLICATION_CREDENTIALS') or os.getenv('FIREBASE_CREDENTIALS_JSON'))),'jobs':[dict(r) for r in c.execute('SELECT id,notice_id,status,attempts,next_try,provider_id,last_error FROM push_outbox ORDER BY id DESC LIMIT 200')]})
 if path=='/api/recovery-email':
  import recovery_mail
  result=recovery_mail.authenticated(h,c,d,uid);return send(result,400 if 'error' in result else 200)
 if path=='/api/account':
  if post:
   action=d.get('action')
   if action in ['password','mfa_start','recovery'] and not verify_password(c,uid,str(d.get('password',''))):return send({'error':'Current password is incorrect'},403)
   sec=c.execute('SELECT enabled FROM security WHERE uid=?',(uid,)).fetchone()
   if action in ['mfa_start','recovery'] and sec and sec['enabled'] and not verify_totp(c,uid,str(d.get('code',''))):return send({'error':'Current authenticator code required'},403)
   if action=='password':
    s=c.execute('SELECT enabled FROM security WHERE uid=?',(uid,)).fetchone()
    if s and s['enabled'] and not verify_totp(c,uid,str(d.get('code',''))):return send({'error':'Authenticator code required'},403)
    set_password(c,uid,d.get('new_password'));cl.audit(c,actor,'password_changed');return send({'sign_out':True})
   if action=='mfa_start':
    secret=base64.b32encode(secrets.token_bytes(20)).decode();c.execute('INSERT INTO security(uid,pending) VALUES(?,?) ON CONFLICT(uid) DO UPDATE SET pending=excluded.pending',(uid,cl.pack(secret)));return send({'secret':secret,'uri':'otpauth://totp/CliMa:'+str(uid)+'?secret='+secret+'&issuer=CliMa'})
   if action=='mfa_confirm':
    s=c.execute('SELECT pending FROM security WHERE uid=?',(uid,)).fetchone()
    if not s or not s['pending'] or not verify_totp(c,uid,str(d.get('code','')),cl.unpack(s['pending'])):return send({'error':'Authenticator code is invalid'},400)
    c.execute('UPDATE security SET totp=pending,pending=NULL,enabled=1 WHERE uid=?',(uid,));cl.audit(c,actor,'mfa_enabled');return send({'ok':True})
   if action=='recovery':
    recovery=secrets.token_urlsafe(32);c.execute('INSERT INTO security(uid,recovery) VALUES(?,?) ON CONFLICT(uid) DO UPDATE SET recovery=excluded.recovery',(uid,hashlib.sha256(recovery.encode()).hexdigest()));return send({'recovery_code':recovery})
   if action=='revoke_sessions':
    current=hashlib.sha256(h.headers.get('Authorization','').removeprefix('Bearer ').encode()).hexdigest();c.execute('DELETE FROM sessions WHERE uid=? AND token<>?',(uid,current));cl.audit(c,actor,'sessions_revoked')
  s=c.execute('SELECT enabled FROM security WHERE uid=?',(uid,)).fetchone()
  return send({'mfa_enabled':bool(s and s['enabled']),'sessions':[{'created':r['created'],'expires':r['expires'],'device':r['device']} for r in c.execute('SELECT * FROM sessions WHERE uid=? AND expires>?',(uid,time.time()))]})
 if path=='/api/data-policy':
  if role!='admin':raise PermissionError()
  if post:
   days=int(d.get('retention_days',0));policy=cl.text(d,'minor_policy',3000,True)
   if days<0 or days>36500:raise ValueError('Invalid retention period')
   for k,v in [('retention_days',str(days)),('minor_policy',cl.pack(policy))]:c.execute('INSERT INTO app_settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,v))
   cl.audit(c,actor,'data_policy_updated')
  days=c.execute("SELECT value FROM app_settings WHERE key='retention_days'").fetchone();policy=c.execute("SELECT value FROM app_settings WHERE key='minor_policy'").fetchone();days=int(days['value']) if days else 0
  due=[dict(r) for r in c.execute("SELECT id,uid,status,updated FROM cases WHERE status='closed' AND updated<datetime('now',?)",('-'+str(days)+' days',))] if days else []
  return send({'retention_days':days,'minor_policy':cl.unpack(policy['value']) if policy else 'Requires local clinical and safeguarding approval before use with minors. Do not contact a guardian automatically.','review_due':due})
 if path=='/api/safeguarding' and post:
  if role!='admin':raise PermissionError()
  cid=int(d['case_id']);case(c,cid,uid,role);note=cl.text(d,'note',3000,True)
  c.execute('INSERT INTO case_entries(case_id,actor,kind,payload) VALUES(?,?,?,?)',(cid,actor,'safeguarding_review',cl.pack({'note':note})));c.execute('UPDATE cases SET version=version+1,updated=CURRENT_TIMESTAMP WHERE id=?',(cid,));cl.audit(c,actor,'safeguarding_review',cid);return send({'ok':True})
 if path=='/api/preferences':
  if post:
   a=d.get('quiet_start','22:00');b=d.get('quiet_end','08:00')
   if not all(re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d',v) for v in [a,b]):raise ValueError('Invalid quiet hours')
   c.execute('INSERT INTO preferences VALUES(?,?,?,?) ON CONFLICT(uid) DO UPDATE SET quiet_start=excluded.quiet_start,quiet_end=excluded.quiet_end,daily=excluded.daily',(uid,a,b,int(bool(d.get('daily')))))
  r=c.execute('SELECT * FROM preferences WHERE uid=?',(uid,)).fetchone();return send(dict(r) if r else {'quiet_start':'22:00','quiet_end':'08:00','daily':1})
 if path=='/api/access-grant' and post:
  if role!='admin':raise PermissionError()
  cid=int(d['case_id']);sid=int(d['staff_id']);reason=cl.text(d,'reason',1000,True)
  if not c.execute("SELECT 1 FROM staff WHERE id=? AND role='clinician' AND active=1",(sid,)).fetchone():raise ValueError('Invalid clinician')
  c.execute('INSERT INTO access_grants VALUES(?,?,?,?) ON CONFLICT(case_id,staff_id) DO UPDATE SET expires=excluded.expires,reason=excluded.reason',(cid,sid,time.time()+3600,cl.pack(reason)));cl.audit(c,actor,'temporary_access_granted',str(cid)+':'+str(sid));return send({'ok':True,'expires_in_minutes':60})
 if path=='/api/appointments':
  cid=int(d.get('case_id') if post else get('case_id'));r=case(c,cid,uid,role)
  if post:
   if role=='user':raise PermissionError()
   if d.get('id'):
    status=d.get('status')
    if status not in ['scheduled','completed','cancelled','missed','referral_completed']:raise ValueError('Invalid appointment status')
    c.execute('UPDATE appointments SET status=? WHERE id=? AND case_id=?',(status,int(d['id']),cid))
   else:
    at=datetime.datetime.fromisoformat(d['at'])
    if at.tzinfo is None:at=at.replace(tzinfo=datetime.timezone(datetime.timedelta(hours=6)))
    if at<datetime.datetime.now(datetime.timezone.utc):raise ValueError('Choose a future appointment time')
    c.execute('INSERT INTO appointments(case_id,uid,staff_id,at,notes) VALUES(?,?,?,?,?)',(cid,r['uid'],r['assigned'],at.isoformat(),cl.pack(cl.text(d,'notes'))))
   c.execute('UPDATE cases SET version=version+1,updated=CURRENT_TIMESTAMP WHERE id=?',(cid,))
   cl.audit(c,actor,'appointment_update',cid);cl.notice(c,uid=r['uid'],title_en='Appointment updated',title_bn='সাক্ষাতের তথ্য হালনাগাদ',case=cid)
  return send({'appointments':[{**dict(x),'notes':cl.unpack(x['notes'])} for x in c.execute('SELECT * FROM appointments WHERE case_id=? ORDER BY at DESC',(cid,))]})
 if path=='/api/documents':
  cid=int(d.get('case_id') if post else get('case_id'));case(c,cid,uid,role)
  if post:
   raw=base64.b64decode(d.get('content',''),validate=True)
   if not 1<=len(raw)<=5*1024*1024:raise ValueError('File must be between 1 byte and 5 MB')
   name=cl.text(d,'name',150,True);mime=''
   if raw.startswith(b'%PDF-'):
    import pymupdf
    with open_pdf(raw) as doc:
     if doc.is_encrypted or len(doc)>100 or doc.embfile_count():raise ValueError('Unsupported PDF')
     # Render-only copy strips scripts, links, forms and embedded attachments.
     safe=pymupdf.open()
     for page in doc:
      target=safe.new_page(width=page.rect.width,height=page.rect.height);target.show_pdf_page(target.rect,doc,page.number)
     raw=safe.tobytes(garbage=4,deflate=True);safe.close()
    mime='application/pdf'
   else:
    from PIL import Image
    with open_image(raw) as im:
     if im.format not in ['PNG','JPEG'] or im.width*im.height>20000000:raise ValueError('Only PNG, JPEG and PDF are supported')
     im.load();out=io.BytesIO();im.convert('RGB').save(out,format='JPEG',quality=90);raw=out.getvalue();mime='image/jpeg'
   if c.execute('SELECT COUNT(*) FROM attachments WHERE case_id=?',(cid,)).fetchone()[0]>=20:raise ValueError('Maximum 20 documents per case')
   c.execute('INSERT INTO attachments(case_id,uid,name,mime,size,payload) VALUES(?,?,?,?,?,?)',(cid,uid,cl.pack(name),mime,len(raw),cl.pack(base64.b64encode(raw).decode())));c.execute('UPDATE cases SET version=version+1,updated=CURRENT_TIMESTAMP WHERE id=?',(cid,));cl.audit(c,actor,'document_upload',cid);staff_notice(c,cid,'Case document uploaded')
  return send({'documents':[{**dict(x),'name':cl.unpack(x['name'])} for x in c.execute('SELECT id,name,mime,size,created FROM attachments WHERE case_id=?',(cid,))]})
 if path=='/api/document':
  r=c.execute('SELECT * FROM attachments WHERE id=?',(int(get('id')),)).fetchone()
  if not r:raise PermissionError()
  case(c,r['case_id'],uid,role);cl.audit(c,actor,'document_download',r['id']);body=base64.b64decode(cl.unpack(r['payload']));h.send_response(200);h.send_header('Content-Type',r['mime']);h.send_header('Content-Disposition','attachment; filename="case-document.'+('pdf' if r['mime']=='application/pdf' else 'jpg')+'"');h.send_header('Cache-Control','no-store');h.end_headers();h.wfile.write(body);return True
 if path=='/api/consent' and post:
  if role!='user':raise PermissionError()
  if d.get('resume') is not True:raise ValueError('Explicit consent required')
  c.execute('INSERT INTO care_consent(uid,paused) VALUES(?,0) ON CONFLICT(uid) DO UPDATE SET paused=0,updated=CURRENT_TIMESTAMP',(uid,))
  c.execute("INSERT INTO consent_events(uid,action,version) VALUES(?,'resumed','health-sharing-v1')",(uid,));cl.audit(c,actor,'consent_resumed',uid)
  return send({'ok':True})
 if path=='/api/privacy-fulfill' and post:
  if role!='admin':raise PermissionError()
  request=c.execute('SELECT * FROM privacy_requests WHERE id=?',(int(d['id']),)).fetchone()
  if not request or request['status']=='fulfilled':raise ValueError('Pending request not found')
  reason=cl.text(d,'response',2000,True)
  if request['kind']=='correction':
   en=cl.text(d,'name_en',100,True);bn=cl.text(d,'name_bn',100,True);age=int(d['age']);city=d['city']
   if not re.search('[A-Za-z]',en) or not re.search('[\u0980-\u09ff]',bn) or not 1<=age<=120 or city not in ['Dhaka','Noakhali','Rajshahi']:raise ValueError('Invalid corrected profile')
   c.execute('UPDATE users SET name_en=?,name_bn=?,age=?,city=? WHERE id=?',(en,bn,age,city,request['uid']))
  elif request['kind']=='delete':
   if d.get('confirmation')!='DELETE USER '+str(request['uid']):raise ValueError('Type the exact account deletion confirmation')
   purge_user(c,request['uid']);cl.audit(c,actor,'privacy_deletion_completed',request['id'])
   return send({'ok':True,'deleted':True})
  else:raise ValueError('This action supports profile correction and approved account deletion')
  c.execute("UPDATE privacy_requests SET status='fulfilled',response=? WHERE id=?",(cl.pack(reason),request['id']));cl.audit(c,actor,'privacy_fulfilled',request['id'])
  return send({'ok':True})
 if path=='/api/privacy':
  if post:
   if role=='user':
    kind=d.get('kind')
    if kind not in ['withdraw_consent','correction','delete','access']:raise ValueError('Invalid privacy request')
    if kind=='withdraw_consent':
     c.execute('INSERT INTO care_consent(uid,paused) VALUES(?,1) ON CONFLICT(uid) DO UPDATE SET paused=1,updated=CURRENT_TIMESTAMP',(uid,))
     c.execute("INSERT INTO consent_events(uid,action,version) VALUES(?,'withdrawn','health-sharing-v1')",(uid,))
     c.execute('UPDATE devices SET active=0 WHERE uid=?',(uid,))
    c.execute('INSERT INTO privacy_requests(uid,kind,detail) VALUES(?,?,?)',(uid,kind,cl.pack(cl.text(d,'detail',2000,True))));cl.audit(c,actor,'privacy_request',kind)
   elif role=='admin':
    status=d.get('status')
    if status not in ['pending','in_review','fulfilled','declined']:raise ValueError('Invalid request status')
    response=cl.text(d,'response',2000,True);c.execute('UPDATE privacy_requests SET status=?,response=? WHERE id=?',(status,cl.pack(response),int(d['id'])));cl.audit(c,actor,'privacy_response',d['id'])
   else:raise PermissionError()
  if role=='clinician':raise PermissionError()
  rows=c.execute('SELECT * FROM privacy_requests'+(' WHERE uid=?' if role=='user' else '')+' ORDER BY id DESC',(uid,) if role=='user' else ())
  return send({'care_paused':bool(c.execute('SELECT 1 FROM care_consent WHERE uid=? AND paused=1',(uid,)).fetchone()),'requests':[{**dict(x),'detail':cl.unpack(x['detail']),'response':cl.unpack(x['response']) if x['response'] else ''} for x in rows]})
 if path=='/api/schedule-edit' and post:
  if role!='admin':raise PermissionError()
  sid=int(d['id']);freq=d.get('frequency','daily');start=cl.text(d,'start_date');end=cl.text(d,'end_date');at=cl.text(d,'at')
  if freq not in ['daily','once'] or not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d',at):raise ValueError('Invalid schedule')
  for value in [start,end]:
   if value:datetime.date.fromisoformat(value)
  if freq=='once' and not start:raise ValueError('One-time notices need a date')
  if start and end and end<start:raise ValueError('End date before start date')
  p=[cl.text(d,k,4000,True) for k in ['title_en','title_bn','body_en','body_bn']]
  c.execute('UPDATE schedules SET title_en=?,title_bn=?,body_en=?,body_bn=?,at=?,start_date=?,end_date=?,frequency=? WHERE id=?',(*p,at,start,end,freq,sid));cl.audit(c,actor,'schedule_edited',sid);return send({'ok':True})
 return False

def encrypt_columns(c):
 """Idempotent field-encryption migration. Search/routing identifiers stay indexed."""
 fields={'users':['name_en','name_bn','age'],'staff':['name','credential'],'requests':['body'],'messages':['title_en','title_bn','body_en','body_bn'],'notices':['title_en','title_bn','body_en','body_bn'],'schedules':['title_en','title_bn','body_en','body_bn'],'audit':['actor','object_id']}
 if getattr(c,"postgres",False):return c.encryption(fields)
 for table,columns in fields.items():
  assignments=','.join(k+'=seal('+k+')' for k in columns)
  for event in ['INSERT','UPDATE']:
   c.execute(f'CREATE TRIGGER IF NOT EXISTS encrypt_{table}_{event} AFTER {event} ON {table} BEGIN UPDATE {table} SET {assignments} WHERE rowid=NEW.rowid; END')
  c.execute(f'UPDATE {table} SET {assignments}')

def recover(c,d,ip):
 from server import pw
 username=str(d.get('username','')).lower().strip();key='recovery:'+ip
 row=c.execute('SELECT * FROM login_limits WHERE key=?',(key,)).fetchone()
 if row and row['reset']>time.time() and row['count']>=8:return 429,{'error':'Try again in 15 minutes'}
 c.execute('INSERT INTO login_limits VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=CASE WHEN reset<? THEN 1 ELSE count+1 END,reset=CASE WHEN reset<? THEN excluded.reset ELSE reset END',(key,time.time()+900,time.time(),time.time()))
 uid=0 if username=='admin' else None
 for table,sign in [('users',1),('staff',-1)]:
  r=c.execute(f'SELECT id FROM {table} WHERE username=? AND active=1',(username,)).fetchone()
  if r:uid=sign*r['id'];break
 r=c.execute('SELECT recovery FROM security WHERE uid=?',(uid,)).fetchone()
 digest=hashlib.sha256(str(d.get('recovery_code','')).encode()).hexdigest()
 if not r or not r['recovery'] or not hmac.compare_digest(r['recovery'],digest):return 403,{'error':'Recovery details could not be verified'}
 set_password(c,uid,d.get('new_password'));c.execute('UPDATE security SET recovery=NULL,enabled=0,totp=NULL,pending=NULL WHERE uid=?',(uid,));cl.audit(c,'recovery:'+str(uid),'account_recovered');return 200,{'ok':True}

def observations(d):
 if not isinstance(d,dict):raise ValueError('Invalid observations')
 specs={'temperature_c':(20,50),'systolic_mmhg':(40,300),'diastolic_mmhg':(20,200),'pulse_bpm':(20,250),'spo2_percent':(0,100),'weight_kg':(1,500)};out={}
 for key,(lo,hi) in specs.items():
  if d.get(key) not in ['',None]:
   value=float(d[key])
   if not lo<=value<=hi:raise ValueError('Check measurement: '+key)
   out[key]=value
 return out

def filter_export(c,data,q,actor):
 one=lambda k,default='':q.get(k,[default])[0]
 purpose=one('purpose').strip()
 if not 3<=len(purpose)<=300:raise ValueError('Provide an export purpose')
 district=one('district');category=one('category');start=one('from');end=one('to')
 for date in [start,end]:
  if date:datetime.date.fromisoformat(date)
 users=[u for u in data['Users'] if not district or u['city']==district];uids={u['id'] for u in users}
 cases=[r for r in data['Cases'] if r['uid'] in uids and (not category or category in r['categories']) and (not start or r['created'][:10]>=start) and (not end or r['created'][:10]<=end)]
 ids={r['id'] for r in cases};data['Users']=users;data['Cases']=cases;data['Case history']=[r for r in data['Case history'] if r['case_id'] in ids]
 for name in ['Requests','Messages','Notifications']:
  data[name]=[r for r in data[name] if r.get('uid',r.get('recipient_id')) in uids or r.get('recipient_id') in uids]
 for section in ['Appointments','Documents','Consent history']:
  if section in data:data[section]=[r for r in data[section] if r.get('case_id') in ids]
 if 'Privacy requests' in data:data['Privacy requests']=[r for r in data['Privacy requests'] if r['uid'] in uids]
 if category or start or end:
  data['Users']=[u for u in users if u['id'] in {r['uid'] for r in cases}]
  # Unrelated communications are not included in a case-filtered report.
  data={k:v for k,v in data.items() if k in ['Users','Cases','Case history','Appointments','Documents','Consent history']}
 if one('anonymized')=='1':
  # No free text, names, IDs, exact dates or contact details in this aggregate view.
  counts={}
  for r in cases:
   for cat in r['categories']:counts[(cat,r['status'])]=counts.get((cat,r['status']),0)+1
  data={'Aggregate counts':[{'category':cat,'status':status,'count':n if n>=5 else 'Suppressed (<5)'} for (cat,status),n in counts.items()]}
 selected=set(filter(None,one('sections').split(',')))
 if selected and one('anonymized')!='1':data={k:v for k,v in data.items() if k in selected}
 if one('columns') and one('anonymized')!='1':
  try:columns=json.loads(one('columns'))
  except (ValueError,TypeError):raise ValueError('Invalid export column selection')
  if not isinstance(columns,dict):raise ValueError('Column selection must map sections to column lists')
  for section,keys in columns.items():
   if not isinstance(keys,list) or not keys or not all(isinstance(k,str) for k in keys):raise ValueError('Select at least one column per included section')
   if section in data:
    known={k for row in data[section] for k in row}
    if known and any(k not in known for k in keys):raise ValueError('Unknown export column')
    data[section]=[{k:row.get(k,'') for k in dict.fromkeys(keys)} for row in data[section]]
 cl.audit(c,actor,'export_purpose',purpose)
 return data


def open_image(raw):
 from PIL import Image
 try:return Image.open(io.BytesIO(raw))
 except Exception as e:raise ValueError('Invalid image file') from e
def open_pdf(raw):
 import pymupdf
 try:return pymupdf.open(stream=raw,filetype='pdf')
 except Exception as e:raise ValueError('Invalid PDF file') from e

def purge_user(c,uid):
 """Apply an explicitly approved deletion request; retain non-content audit events."""
 cases=[r['id'] for r in c.execute('SELECT id FROM cases WHERE uid=?',(uid,))]
 for cid in cases:
  for table in ['case_entries','access_grants','appointments','attachments','submissions']:
   c.execute('DELETE FROM '+table+' WHERE case_id=?',(cid,))
 c.execute('DELETE FROM push_outbox WHERE device_id IN (SELECT id FROM devices WHERE uid=?)',(uid,))
 c.execute('DELETE FROM notice_reads WHERE nid IN (SELECT id FROM notices WHERE uid=?)',(uid,))
 c.execute('DELETE FROM reads WHERE mid IN (SELECT id FROM messages WHERE uid=?)',(uid,))
 for table in ['registration_profiles','cases','consent_events','privacy_requests','care_consent','requests','messages','notices','reads','notice_reads','devices','security','preferences','sessions','submissions','recovery_contacts','email_challenges']:
  c.execute('DELETE FROM '+table+' WHERE uid=?',(uid,))
 c.execute("DELETE FROM admin_changes WHERE entity='users' AND record_id=?",(uid,))
 c.execute('DELETE FROM users WHERE id=?',(uid,))
