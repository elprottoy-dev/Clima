"""CliMa: dependency-free development server. Put behind HTTPS for deployment."""
import clinical
import upgrade
import os,json,sqlite3,secrets,hashlib,hmac,time,re,urllib.request,urllib.parse
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
ROOT=Path(__file__).parent
DB=os.getenv('CLIMA_DB',str(ROOT/'clima.sqlite3'))
CITIES={'Dhaka':(23.8103,90.4125),'Noakhali':(22.8246,91.1017),'Rajshahi':(24.3745,88.6042)}
class SecureRow(dict):
 def __getitem__(self,key):return list(self.values())[key] if isinstance(key,int) else super().__getitem__(key)
def seal(v):
 if v is None or (isinstance(v,str) and v.startswith('enc:v1:')):return v
 return 'enc:v1:'+clinical.pack(v)
def secure_row(cursor,row):
 return SecureRow((col[0],clinical.unpack(v[7:]) if isinstance(v,str) and v.startswith('enc:v1:') else v) for col,v in zip(cursor.description,row))
def db():
 if os.getenv("CLIMA_DATABASE_URL"):
  from pg_database import Connection
  return Connection(os.environ["CLIMA_DATABASE_URL"],secure_row)
 c=sqlite3.connect(DB,timeout=20);c.execute('PRAGMA secure_delete=ON');c.row_factory=secure_row;c.create_function('seal',1,seal);return c
def init():
 with db() as c:c.executescript('''CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE,name_en TEXT,name_bn TEXT,age INTEGER,city TEXT,password TEXT,active INTEGER DEFAULT 1);CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,uid INTEGER,expires REAL);CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY,uid INTEGER,body TEXT,status TEXT DEFAULT 'open',created TEXT DEFAULT CURRENT_TIMESTAMP);CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY,uid INTEGER,city TEXT,title_en TEXT,title_bn TEXT,body_en TEXT,body_bn TEXT,priority TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP);CREATE TABLE IF NOT EXISTS reads(uid INTEGER,mid INTEGER,PRIMARY KEY(uid,mid));''')
 with db() as c:
  clinical.init(c)
  upgrade.init(c)
  import cloud_transport;cloud_transport.init(c)
  import registration;registration.init(c)
  upgrade.encrypt_columns(c)
  c.execute('CREATE TABLE IF NOT EXISTS login_limits(key TEXT PRIMARY KEY, count INTEGER, reset REAL)')
def pw(p,s=None):
 s=s or secrets.token_hex(16);return s+':'+hashlib.pbkdf2_hmac('sha256',p.encode(),s.encode(),300000).hex()
def validpw(p,h):return hmac.compare_digest(pw(p,h.split(':')[0]),h)
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def send(self,status,obj):
  b=json.dumps(obj,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
 def do_GET(self):self.handle_request()
 def do_POST(self):self.handle_request()
 def handle_request(self):
  path=urllib.parse.urlparse(self.path).path
  if not path.startswith('/api/'):
   name={'/':'index.html','/admin':'index.html','/app.js':'app.js','/style.css':'style.css','/clinical.js':'clinical.js','/upgrade.js':'upgrade.js','/sw.js':'sw.js','/draft-vault.js':'draft-vault.js','/offline.js':'offline.js','/labels.js':'labels.js','/retention.js':'retention.js','/admin-crud.js':'admin-crud.js','/cloud-transport.js':'cloud-transport.js','/seasonal.js':'seasonal.js','/registration.js':'registration.js','/data-notices.js':'data-notices.js','/locations.json':'locations.json'}.get(path)
   if not name:return self.send(404,{'error':'Not found'})
   b=(ROOT/'public'/name).read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8' if name.endswith('html') else ('text/javascript; charset=utf-8' if name.endswith('js') else 'text/css'));self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(b);return
  try:
   d={}
   if self.command=='POST':
    if not self.headers.get('Content-Type','').startswith('application/json'):return self.send(415,{'error':'JSON required'})
    n=int(self.headers.get('Content-Length',0))
    if n<0 or n>7500000:raise ValueError('Request too large')
    from input_normalization import normalize_answers
    d=normalize_answers(json.loads(self.rfile.read(n)))
   with db() as c:
    if path=='/api/health' and self.command=='GET':
     heartbeat=c.execute("SELECT value FROM app_settings WHERE key='scheduler_heartbeat'").fetchone()
     healthy=bool(heartbeat and time.time()-float(heartbeat['value'])<300)
     return self.send(200 if healthy else 503,{'status':'ok' if healthy else 'scheduler_unavailable'})
    if path=='/api/recover-email' and self.command=='POST':
     import recovery_mail
     status,result=recovery_mail.recover(self,c,d);return self.send(status,result)
    if path=='/api/recover' and self.command=='POST':
     return self.send(*upgrade.recover(c,d,self.client_address[0]))
    if path in ['/api/register','/api/login'] and self.command=='POST':
     profile=None
     if path.endswith('register') and 'birth_date' in d:
      import registration
      profile,profile_age,profile_phone=registration.validate(d);d.update(username=profile_phone,age=profile_age,city=profile['district'],name_en=d.get('name_bn',''))
     username=str(d.get('username','')).strip().lower();password=str(d.get('password',''))
     if len(password)>256:raise ValueError('Password too long')
     phone_login=username.translate(str.maketrans('০১২৩৪৫৬৭৮৯','0123456789')).replace(' ','').replace('-','')
     if phone_login.startswith('+88'):phone_login=phone_login[3:]
     if re.fullmatch(r'01[3-9][0-9]{8}',phone_login):username=phone_login
     ratekey=self.client_address[0]+':'+username
     limit=c.execute('SELECT * FROM login_limits WHERE key=?',(ratekey,)).fetchone()
     if limit and limit['reset']>time.time() and limit['count']>=15:return self.send(429,{'error':'Too many attempts. Try again in 15 minutes.'})
     c.execute('INSERT INTO login_limits VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=CASE WHEN reset<? THEN 1 ELSE count+1 END,reset=CASE WHEN reset<? THEN excluded.reset ELSE reset END',(ratekey,time.time()+900,time.time(),time.time()))
     if path.endswith('register'):
      if c.execute('SELECT id FROM staff WHERE username=?',(username,)).fetchone():raise ValueError('Username in use')
      if username=='admin' or not re.fullmatch('[a-z0-9_]{3,40}',username) or len(password)<10:raise ValueError('Use a 3–40 character username and password of at least 10 characters')
      en=str(d.get('name_en','')).strip();bn=str(d.get('name_bn','')).strip();age=int(d.get('age',0));city=d.get('city')
      if profile is None and (not en or len(en)>100 or not re.search('[A-Za-z]',en) or not re.search('[\u0980-\u09ff]',bn) or len(bn)>100 or not 1<=age<=120 or city not in CITIES):raise ValueError('Enter both names, age 1–120 and a listed district')
      c.execute("UPDATE identity_sequence SET value=MAX(value,(SELECT COALESCE(MAX(id),0) FROM users))+1 WHERE name='users'")
      user_id=c.execute("SELECT value FROM identity_sequence WHERE name='users'").fetchone()[0]
      c.execute('INSERT INTO users(id,username,name_en,name_bn,age,city,password) VALUES(?,?,?,?,?,?,?)',(user_id,username,en,bn,age,city,pw(password)))
      if profile:c.execute('INSERT INTO registration_profiles(uid,payload) VALUES(?,?)',(user_id,clinical.pack(profile)))
     if username=='admin' and upgrade.verify_password(c,0,password):uid=0
     else:
      u=c.execute('SELECT * FROM users WHERE username=? AND active=1',(username,)).fetchone()
      if u and validpw(password,u['password']):uid=u['id']
      else:
       st=c.execute('SELECT * FROM staff WHERE username=? AND active=1',(username,)).fetchone()
       if not st or not validpw(password,st['password']):return self.send(401,{'error':'Invalid login'})
       uid=-st['id']
     security=c.execute('SELECT enabled FROM security WHERE uid=?',(uid,)).fetchone()
     if security and security['enabled'] and not upgrade.verify_totp(c,uid,str(d.get('code',''))):return self.send(401,{'error':'Enter the current authenticator code'})
     c.execute('DELETE FROM login_limits WHERE key=?',(ratekey,))
     token=secrets.token_urlsafe(32);c.execute('INSERT INTO sessions(token,uid,expires,created,device) VALUES(?,?,?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),uid,time.time()+86400,time.time(),self.headers.get('User-Agent','')[:160]));return self.send(200,{'token':token})
    token=self.headers.get('Authorization','').removeprefix('Bearer ');s=c.execute('SELECT uid FROM sessions WHERE token=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
    if not s:return self.send(401,{'error':'Please sign in'})
    uid=s['uid'];role='admin' if uid==0 else 'user';actor='admin' if uid==0 else 'user:'+str(uid)
    if uid<0:
     st=c.execute('SELECT * FROM staff WHERE id=? AND active=1',(-uid,)).fetchone()
     if not st:return self.send(403,{'error':'Staff account disabled'})
     role=st['role'];actor='staff:'+str(st['id'])+':'+st['name']
    admin=role=='admin'
    u=c.execute('SELECT id,username,name_en,name_bn,age,city,active FROM users WHERE id=?',(uid,)).fetchone()
    if role=='user' and (not u or not u['active']):return self.send(403,{'error':'Account disabled'})
    if path=='/api/logout':c.execute('UPDATE devices SET active=0 WHERE uid=?',(uid,));c.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(token.encode()).hexdigest(),));return self.send(200,{})
    mfa=c.execute('SELECT enabled FROM security WHERE uid=?',(uid,)).fetchone()
    required=role!='user' and os.getenv('CLIMA_REQUIRE_STAFF_MFA','0')=='1' and not (mfa and mfa['enabled'])
    if path=='/api/me':return self.send(200,{'mfa_required':required,'admin':role!='user','role':role,'actor':actor,'user':dict(u) if u else None})
    if required and path!='/api/account':return self.send(403,{'error':'Set up your authenticator in Account security before accessing staff records'})
    if upgrade.route(self,c,path,d,uid,role,actor):return
    if clinical.route(self,c,path,d,uid,role,actor):return
    if path.startswith('/api/admin/') and not admin:return self.send(403,{'error':'Admin only'})
    if path=='/api/admin/data':return self.send(200,{k:[dict(r) for r in c.execute(q)] for k,q in {'users':'SELECT id,username,name_en,name_bn,age,city,active FROM users','requests':'SELECT requests.*,users.name_en,users.city FROM requests JOIN users ON uid=users.id ORDER BY id DESC','messages':'SELECT messages.*,(SELECT COUNT(*) FROM reads WHERE mid=messages.id) AS read_count FROM messages ORDER BY id DESC'}.items()})
    if path=='/api/admin/user' and self.command=='POST':
     c.execute('UPDATE users SET active=? WHERE id=?',(1 if d.get('active') else 0,int(d['id'])));return self.send(200,{})
    if path=='/api/admin/message' and self.command=='POST':
     for k in ['title_en','title_bn','body_en','body_bn']:
      if not isinstance(d.get(k),str) or not d[k].strip() or len(d[k])>4000:raise ValueError('Both language versions are required (maximum 4000 characters)')
     target=int(d['uid']) if d.get('uid') else None;city=d.get('city') or None
     if city and city not in CITIES:raise ValueError('Invalid district')
     if target and not c.execute('SELECT id FROM users WHERE id=?',(target,)).fetchone():raise ValueError('Unknown recipient')
     message_kind=d.get('message_kind','advisory')
     if message_kind not in ['warning','advisory']:raise ValueError('Invalid message kind')
     priority=d.get('priority','normal')
     if priority not in ['normal','important','urgent']:raise ValueError('Invalid priority')
     rid=d.get('request_id')
     if rid and not c.execute('SELECT id FROM requests WHERE id=? AND uid=?',(int(rid),target)).fetchone():raise ValueError('Request does not match recipient')
     import datetime
     now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=6)))
     start=d.get('start_date') or now.date().isoformat();end=d.get('end_date') or '';at=d.get('at') or '00:00'
     datetime.date.fromisoformat(start)
     if end:datetime.date.fromisoformat(end)
     if (end and end<start) or start<now.date().isoformat() or not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d',at):raise ValueError('সঠিক প্রকাশের তারিখ ও সময় দিন')
     if start>now.date().isoformat() or at>now.strftime('%H:%M'):
      if rid:raise ValueError('অনুরোধের উত্তর এখনই পাঠান')
      c.execute('INSERT INTO schedules(uid,city,title_en,title_bn,body_en,body_bn,priority,message_kind,start_date,end_date,at,frequency) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(target,city,*[d[k].strip() for k in ['title_en','title_bn','body_en','body_bn']],priority,message_kind,start,end,at,'once'))
      clinical.audit(c,actor,'message_scheduled',start)
      return self.send(200,{'scheduled':True})
     c.execute('INSERT INTO messages(uid,city,title_en,title_bn,body_en,body_bn,priority,message_kind,start_date,end_date) VALUES(?,?,?,?,?,?,?,?,?,?)',(target,city,*[d[k].strip() for k in ['title_en','title_bn','body_en','body_bn']],priority,message_kind,start,end))
     if rid:c.execute("UPDATE requests SET status='answered' WHERE id=?",(int(rid),))
     clinical.notice(c,uid=target,city=city,title_en=d['title_en'].strip(),title_bn=d['title_bn'].strip(),body_en=d['body_en'].strip(),body_bn=d['body_bn'].strip(),source=message_kind)
     clinical.audit(c,actor,'advisory_sent',target or city or 'all')
     return self.send(200,{})
    if role!='user':return self.send(404,{'error':'Not found'})
    if path=='/api/request' and self.command=='POST':
     body=str(d.get('body','')).strip()
     if not 1<=len(body)<=2000:raise ValueError('Write a request (maximum 2000 characters)')
     c.execute('INSERT INTO requests(uid,body) VALUES(?,?)',(uid,body));return self.send(200,{})
    if path=='/api/inbox':return self.send(200,{'messages':[dict(r) for r in c.execute('SELECT messages.*, EXISTS(SELECT 1 FROM reads WHERE uid=? AND mid=messages.id) AS is_read FROM messages WHERE messages.deleted=0 AND (messages.uid=? OR (messages.uid IS NULL AND (city IS NULL OR city=?))) ORDER BY id DESC',(uid,uid,u['city']))],'requests':[dict(r) for r in c.execute('SELECT * FROM requests WHERE uid=? ORDER BY id DESC',(uid,))]})
    if path=='/api/read' and self.command=='POST':
     if not c.execute('SELECT id FROM messages WHERE deleted=0 AND id=? AND (uid=? OR (uid IS NULL AND (city IS NULL OR city=?)))',(d['id'],uid,u['city'])).fetchone():return self.send(404,{'error':'Not found'})
     c.execute('INSERT OR IGNORE INTO reads VALUES(?,?)',(uid,d['id']));return self.send(200,{})
    return self.send(404,{'error':'Not found'})
  except PermissionError:self.send(403,{'error':'Access denied'})
  except sqlite3.IntegrityError:self.send(409,{'error':'Username already exists'})
  except ValueError as error:self.send(400,{'error':str(error) if not isinstance(error,json.JSONDecodeError) else 'Invalid JSON request'})
  except (KeyError,TypeError):self.send(400,{'error':'Check all required fields and values'})
  except Exception as error:
   diagnostic=str(error)
   for name,value in os.environ.items():
    if value and (name.startswith('CLIMA_') or any(k in name for k in ['PASSWORD','SECRET','TOKEN','KEY'])):diagnostic=diagnostic.replace(value,'[redacted]')
   diagnostic=re.sub(r'postgres(?:ql)?://[^\s]+','[database connection]',diagnostic)
   print('CliMa server error:',type(error).__name__,diagnostic[:1200],flush=True)
   self.send(500,{'error':'Server error; please retry'})
if __name__=='__main__':
 init()
 if not os.getenv('CLIMA_ADMIN_PASSWORD'):raise SystemExit('Set CLIMA_ADMIN_PASSWORD to a strong password before starting.')
 clinical.start_scheduler(db)
 print('CliMa: http://localhost:8080 | Admin: /admin')
 ThreadingHTTPServer((os.getenv('CLIMA_HOST','127.0.0.1'),int(os.getenv('PORT','8080'))),Handler).serve_forever()
