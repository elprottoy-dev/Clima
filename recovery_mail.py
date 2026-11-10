"""Verified recovery email. SMTP delivery is configured by the operator."""
import os,re,time,secrets,hashlib,smtplib,ssl,hmac
from email.message import EmailMessage
import clinical

def init(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS recovery_contacts(uid INTEGER PRIMARY KEY,email TEXT,verified INTEGER DEFAULT 0);
 CREATE TABLE IF NOT EXISTS email_challenges(id TEXT PRIMARY KEY,uid INTEGER,kind TEXT,email TEXT,digest TEXT,expires REAL,attempts INTEGER DEFAULT 0,created REAL,used INTEGER DEFAULT 0);''')
def configured():return bool(os.getenv('BREVO_API_KEY') and os.getenv('CLIMA_SMTP_FROM') or os.getenv('CLIMA_SMTP_HOST') and os.getenv('CLIMA_SMTP_FROM'))
def deliver(address,code):
 if not configured():raise ValueError('Email recovery is not configured by the operator')
 msg=EmailMessage();msg['From']=os.environ['CLIMA_SMTP_FROM'];msg['To']=address;msg['Subject']='CliMa verification code / যাচাইকরণ কোড'
 msg.set_content('Your CliMa verification code is '+code+'. It expires in 10 minutes. Never share this code.\nআপনার CliMa যাচাইকরণ কোড: '+code+'। মেয়াদ ১০ মিনিট। কোডটি কাউকে দেবেন না।')
 if os.getenv('BREVO_API_KEY'):
  import requests
  response=requests.post('https://api.brevo.com/v3/smtp/email',headers={'api-key':os.environ['BREVO_API_KEY']},json={'sender':{'email':os.environ['CLIMA_SMTP_FROM'],'name':'CliMa'},'to':[{'email':address}],'subject':str(msg['Subject']),'textContent':msg.get_content()},timeout=10)
  if response.status_code not in (200,201,202):raise ValueError('Recovery email delivery unavailable')
  return
 with smtplib.SMTP(os.environ['CLIMA_SMTP_HOST'],int(os.getenv('CLIMA_SMTP_PORT','587')),timeout=10) as client:
  client.starttls(context=ssl.create_default_context());client.ehlo()
  if os.getenv('CLIMA_SMTP_USER'):client.login(os.environ['CLIMA_SMTP_USER'],os.environ['CLIMA_SMTP_PASSWORD'])
  client.send_message(msg)
def challenge(c,uid,kind,address):
 last=c.execute('SELECT created FROM email_challenges WHERE uid=? ORDER BY created DESC LIMIT 1',(uid,)).fetchone()
 if last and time.time()-last['created']<60:raise ValueError('Wait one minute before requesting another code')
 code=''.join(str(secrets.randbelow(10)) for _ in range(8));cid=secrets.token_urlsafe(24)
 deliver(address,code)
 c.execute('UPDATE email_challenges SET used=1 WHERE uid=? AND kind=?',(uid,kind))
 c.execute('INSERT INTO email_challenges(id,uid,kind,email,digest,expires,created) VALUES(?,?,?,?,?,?,?)',(cid,uid,kind,clinical.pack(address),hashlib.sha256((cid+code).encode()).hexdigest(),time.time()+600,time.time()))
 return cid

def check(c,cid,code,kind):
 row=c.execute('SELECT * FROM email_challenges WHERE id=? AND kind=?',(cid,kind)).fetchone()
 if not row or row['used'] or row['expires']<time.time() or row['attempts']>=5:return None
 c.execute('UPDATE email_challenges SET attempts=attempts+1 WHERE id=?',(cid,))
 if not hmac.compare_digest(row['digest'],hashlib.sha256((cid+str(code)).encode()).hexdigest()):return None
 return row

def authenticated(h,c,d,uid):
 import upgrade
 if h.command!='POST':
  contact=c.execute('SELECT verified FROM recovery_contacts WHERE uid=?',(uid,)).fetchone()
  return {'configured':configured(),'verified':bool(contact and contact['verified'])}
 action=d.get('action')
 if action=='start':
  if not upgrade.verify_password(c,uid,str(d.get('password',''))):raise PermissionError('Current password required')
  sec=c.execute('SELECT enabled FROM security WHERE uid=?',(uid,)).fetchone()
  if sec and sec['enabled'] and not upgrade.verify_totp(c,uid,str(d.get('code',''))):raise PermissionError('Current authenticator code required')
  address=str(d.get('email','')).strip()
  if len(address)>254 or not re.fullmatch(r'[^\s@\r\n]+@[^\s@\r\n]+\.[^\s@\r\n]+',address):raise ValueError('Enter a valid email address')
  return {'challenge':challenge(c,uid,'verify',address)}
 if action=='confirm':
  row=check(c,str(d.get('challenge','')),d.get('email_code',''),'verify')
  if not row or row['uid']!=uid:return {'error':'Invalid or expired verification code'}
  c.execute('INSERT INTO recovery_contacts(uid,email,verified) VALUES(?,?,1) ON CONFLICT(uid) DO UPDATE SET email=excluded.email,verified=1',(uid,row['email']))
  c.execute('UPDATE email_challenges SET used=1 WHERE id=?',(row['id'],));return {'ok':True}
 raise ValueError('Invalid email action')

def recover(h,c,d):
 import server
 action=d.get('action');key='email-recovery:'+h.client_address[0];now=time.time()
 limit=c.execute('SELECT * FROM login_limits WHERE key=?',(key,)).fetchone()
 if limit and limit['reset']>now and limit['count']>=10:return 429,{'error':'Too many attempts. Try later.'}
 c.execute('INSERT INTO login_limits(key,count,reset) VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=CASE WHEN reset<? THEN 1 ELSE count+1 END,reset=CASE WHEN reset<? THEN excluded.reset ELSE reset END',(key,now+900,now,now))
 if action=='start':
  if not configured():return 503,{'error':'Email recovery is not configured by the operator'}
  username=str(d.get('username','')).strip().lower();uid=None
  if username=='admin':uid=0
  else:
   u=c.execute('SELECT id FROM users WHERE username=? AND active=1',(username,)).fetchone()
   if u:uid=u['id']
   else:
    u=c.execute('SELECT id FROM staff WHERE username=? AND active=1',(username,)).fetchone()
    if u:uid=-u['id']
  contact=c.execute('SELECT email FROM recovery_contacts WHERE uid=? AND verified=1',(uid,)).fetchone() if uid is not None else None
  cid=secrets.token_urlsafe(24)
  if contact:
   try:cid=challenge(c,uid,'reset',clinical.unpack(contact['email']))
   except (ValueError,smtplib.SMTPException,OSError):pass
  return 200,{'challenge':cid,'message':'If a verified address is available, a code has been sent.'}
 if action=='confirm':
  password=str(d.get('new_password',''))
  if not 12<=len(password)<=256:return 400,{'error':'Use a password of 12–256 characters'}
  row=check(c,str(d.get('challenge','')),d.get('email_code',''),'reset')
  if not row:return 400,{'error':'Invalid or expired verification code'}
  uid=row['uid'];hashed=server.pw(password)
  if uid==0:c.execute("INSERT INTO app_settings(key,value) VALUES('admin_password_hash',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(hashed,))
  elif uid<0:c.execute('UPDATE staff SET password=? WHERE id=?',(hashed,-uid))
  else:c.execute('UPDATE users SET password=? WHERE id=?',(hashed,uid))
  c.execute('UPDATE email_challenges SET used=1 WHERE uid=?',(uid,));c.execute('DELETE FROM sessions WHERE uid=?',(uid,));clinical.audit(c,'email-recovery','password_reset',uid)
  # Email resets never disable MFA or reveal the enrolled address.
  return 200,{'ok':True}
 return 400,{'error':'Invalid recovery action'}
