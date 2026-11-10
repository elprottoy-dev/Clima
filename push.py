"""FCM outbox. No medical details are placed in notification payloads."""
import os,time,json,datetime
import clinical

def init(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS devices(id INTEGER PRIMARY KEY,uid INTEGER,token TEXT,token_hash TEXT UNIQUE,active INTEGER DEFAULT 1);CREATE TABLE IF NOT EXISTS push_outbox(id INTEGER PRIMARY KEY,device_id INTEGER,notice_id INTEGER,status TEXT DEFAULT 'pending',attempts INTEGER DEFAULT 0,next_try REAL DEFAULT 0,provider_id TEXT,last_error TEXT,UNIQUE(device_id,notice_id));''')
def enqueue(c,notice_id):
 n=c.execute('SELECT * FROM notices WHERE id=?',(notice_id,)).fetchone()
 for d in c.execute('SELECT * FROM devices WHERE active=1').fetchall():
  matched=n['uid']==d['uid']
  if n['uid'] is None and d['uid']>0:
   u=c.execute('SELECT city,active FROM users WHERE id=?',(d['uid'],)).fetchone();matched=bool(u and u['active'] and (not n['city'] or n['city']==u['city']))
  if matched:c.execute('INSERT OR IGNORE INTO push_outbox(device_id,notice_id) VALUES(?,?)',(d['id'],notice_id))
def process(c,limit=20):
 project=os.getenv('FIREBASE_PROJECT_ID')
 if not project or not (os.getenv('GOOGLE_APPLICATION_CREDENTIALS') or os.getenv('FIREBASE_CREDENTIALS_JSON')):return
 import google.auth
 from google.auth.transport.requests import AuthorizedSession
 if os.getenv('FIREBASE_CREDENTIALS_JSON'):
  from google.oauth2.service_account import Credentials
  credentials=Credentials.from_service_account_info(json.loads(os.environ['FIREBASE_CREDENTIALS_JSON']),scopes=['https://www.googleapis.com/auth/firebase.messaging'])
 else:credentials,_=google.auth.default(scopes=['https://www.googleapis.com/auth/firebase.messaging'])
 session=AuthorizedSession(credentials)
 for job in c.execute("SELECT p.*,d.uid,d.token FROM push_outbox p JOIN devices d ON p.device_id=d.id WHERE p.status IN ('pending','retry') AND p.next_try<=? AND d.active=1 LIMIT ?",(time.time(),limit)).fetchall():
  pref=c.execute('SELECT * FROM preferences WHERE uid=?',(job['uid'],)).fetchone();now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=6))).strftime('%H:%M')
  if pref:
   a,b=pref['quiet_start'],pref['quiet_end'];quiet=(a<=now<b) if a<b else (now>=a or now<b) if a!=b else False
   if quiet:continue
   n=c.execute('SELECT source FROM notices WHERE id=?',(job['notice_id'],)).fetchone()
   if not pref['daily'] and n and n['source']=='daily':c.execute("UPDATE push_outbox SET status='suppressed' WHERE id=?",(job['id'],));continue
  claim=c.execute("UPDATE push_outbox SET next_try=? WHERE id=? AND next_try<=? AND status IN ('pending','retry')",(time.time()+120,job['id'],time.time()))
  c.commit()
  if not claim.rowcount:continue
  attempts=job['attempts']+1
  try:
   token=clinical.unpack(job['token']);r=session.post(f'https://fcm.googleapis.com/v1/projects/{project}/messages:send',json={'message':{'token':token,'notification':{'title':'CliMa','body':'You have an update. Open CliMa to view it. / আপনার নতুন আপডেট আছে।'},'data':{'notice_id':str(job['notice_id'])},'android':{'notification':{'channel_id':'clima_updates'}}}},timeout=8)
   if r.ok:
    c.execute("UPDATE push_outbox SET status='accepted_by_provider',attempts=?,provider_id=?,last_error=NULL WHERE id=?",(attempts,r.json().get('name'),job['id']))
   else:
    failure=str(r.status_code);retry=r.status_code in [429,500,502,503,504] and attempts<6
    c.execute('UPDATE push_outbox SET status=?,attempts=?,next_try=?,last_error=? WHERE id=?',('retry' if retry else 'failed',attempts,time.time()+min(3600,30*2**attempts),failure,job['id']))
  except Exception:
   c.execute('UPDATE push_outbox SET status=?,attempts=?,next_try=?,last_error=? WHERE id=?',('retry' if attempts<6 else 'failed',attempts,time.time()+min(3600,30*2**attempts),'Network/provider unavailable',job['id']))
  c.commit()
 session.close()
