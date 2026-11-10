"""Administrative CRUD with audit snapshots, reversible archive and explicit purge."""
import re,json,datetime
from urllib.parse import parse_qs,urlparse
import clinical as cl
FIELDS={'users':['id','username','name_en','name_bn','age','city','active'], 'staff':['id','username','name','role','credential','active'], 'messages':['id','uid','city','title_en','title_bn','body_en','body_bn','priority','message_kind','deleted'], 'schedules':['id','title_en','title_bn','body_en','body_bn','city','at','frequency','start_date','end_date','active','deleted']}
def init(c):
 if 'message_kind' not in [r['name'] for r in c.execute('PRAGMA table_info(messages)')]:c.execute("ALTER TABLE messages ADD COLUMN message_kind TEXT DEFAULT 'advisory'")
 c.execute('CREATE TABLE IF NOT EXISTS admin_changes(id INTEGER PRIMARY KEY,entity TEXT,record_id INTEGER,actor TEXT,payload TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP)')
 for table in ['messages','schedules']:
  if 'deleted' not in [r['name'] for r in c.execute('PRAGMA table_info('+table+')')]:c.execute('ALTER TABLE '+table+' ADD COLUMN deleted INTEGER DEFAULT 0')

def route(h,c,d,uid,role,actor):
 if role!='admin':raise PermissionError()
 q=parse_qs(urlparse(h.path).query);entity=d.get('entity') if h.command=='POST' else q.get('entity',['users'])[0]
 if entity not in FIELDS:raise ValueError('Unknown administrative section')
 fields=','.join(FIELDS[entity]);action=d.get('action');rid=int(d.get('id',0));before=None
 if h.command=='POST':
  from server import pw
  import upgrade
  if action not in ['create','update','archive','restore','purge']:raise ValueError('Invalid operation')
  if action!='create':
   before=c.execute('SELECT '+fields+' FROM '+entity+' WHERE id=?',(rid,)).fetchone()
   if not before:raise ValueError('Record not found')
  if entity=='staff' and rid==-uid and (action in ['archive','purge'] or action=='update' and d.get('role')!=before['role']):raise ValueError('You cannot remove or change your own administrative role')
  if action=='purge':
   if entity!='users':raise ValueError('Use archive for records with an operational history')
   if d.get('confirmation')!='DELETE USER '+str(rid):raise ValueError('Type the exact permanent account deletion confirmation')
   reason=cl.text(d,'reason',2000,True)
   # Purge deliberately omits a recoverable copy of the deleted profile.
   upgrade.purge_user(c,rid);cl.audit(c,actor,'admin_user_purged',rid)
   c.execute('INSERT INTO admin_changes(entity,record_id,actor,payload) VALUES(?,?,?,?)',('purge_approval',rid,cl.pack(actor),cl.pack({'reason':reason})))
  elif action in ['archive','restore']:
   archived=action=='archive'
   if entity in ['users','staff']:
    c.execute('UPDATE '+entity+' SET active=? WHERE id=?',(0 if archived else 1,rid))
    identity=rid if entity=='users' else -rid
    c.execute('DELETE FROM sessions WHERE uid=?',(identity,));c.execute('UPDATE devices SET active=0 WHERE uid=?',(identity,))
   else:
    c.execute('UPDATE '+entity+' SET deleted=? WHERE id=?',(int(archived),rid))
    if entity=='schedules':c.execute('UPDATE schedules SET active=? WHERE id=?',(0 if archived else 1,rid))
  else:
   values={}
   if entity in ['users','staff']:
    username=cl.text(d,'username',40,True).lower()
    if username=='admin' or not re.fullmatch('[a-z0-9_]{3,40}',username):raise ValueError('Use a valid unique username')
    other='staff' if entity=='users' else 'users'
    if c.execute('SELECT id FROM '+other+' WHERE username=?',(username,)).fetchone():raise ValueError('Username in use')
    values['username']=username
    password=cl.text(d,'password',256,action=='create')
    if password:
     if len(password)<12:raise ValueError('Password must have at least 12 characters')
     values['password']=pw(password)
    if entity=='users':
     en=cl.text(d,'name_en',100,True);bn=cl.text(d,'name_bn',100,True);age=int(d['age']);city=d.get('city')
     if not re.search('[A-Za-z]',en) or not re.search('[\u0980-\u09ff]',bn) or not 1<=age<=120 or city not in ['Dhaka','Noakhali','Rajshahi']:raise ValueError('Check both names, age and district')
     values.update(name_en=en,name_bn=bn,age=age,city=city)
    else:
     r=d.get('role');name=cl.text(d,'name',100,True);credential=cl.text(d,'credential',200,r=='clinician')
     if r not in ['admin','clinician']:raise ValueError('Invalid staff role')
     values.update(role=r,name=name,credential=credential)
   else:
    values={k:cl.text(d,k,4000,True) for k in ['title_en','title_bn','body_en','body_bn']};city=d.get('city') or None
    if city not in [None,'Dhaka','Noakhali','Rajshahi']:raise ValueError('Invalid district')
    values['city']=city
    if entity=='messages':
     target=int(d['uid']) if d.get('uid') else None
     if target and not c.execute('SELECT id FROM users WHERE id=? AND active=1',(target,)).fetchone():raise ValueError('Unknown active recipient')
     priority=d.get('priority','normal')
     if priority not in ['normal','important','urgent']:raise ValueError('Invalid priority')
     message_kind=d.get('message_kind',(before or {}).get('message_kind','advisory'))
     if message_kind not in ['warning','advisory']:raise ValueError('Invalid message kind')
     values.update(uid=target,priority=priority,message_kind=message_kind)
    else:
     at=cl.text(d,'at');frequency=d.get('frequency','daily');start=cl.text(d,'start_date');end=cl.text(d,'end_date')
     if not re.fullmatch(r'([01]\d|2[0-3]):[0-5]\d',at) or frequency not in ['daily','once']:raise ValueError('Invalid schedule')
     for date in [start,end]:
      if date:datetime.date.fromisoformat(date)
     if frequency=='once' and not start or start and end and end<start:raise ValueError('Check schedule dates')
     values.update(at=at,frequency=frequency,start_date=start,end_date=end)
   if action=='create':
    if entity=='users':
     c.execute("UPDATE identity_sequence SET value=MAX(value,(SELECT COALESCE(MAX(id),0) FROM users))+1 WHERE name='users'")
     values['id']=c.execute("SELECT value FROM identity_sequence WHERE name='users'").fetchone()[0]
    keys=list(values);cur=c.execute('INSERT INTO '+entity+'('+','.join(keys)+') VALUES('+','.join('?' for _ in keys)+')',list(values.values()));rid=cur.lastrowid
   else:
    c.execute('UPDATE '+entity+' SET '+','.join(k+'=?' for k in values)+' WHERE id=?',(*values.values(),rid))
    if entity in ['users','staff']:
     identity=rid if entity=='users' else -rid;c.execute('DELETE FROM sessions WHERE uid=?',(identity,))
   if entity=='messages' and not (before and before.get('deleted')):cl.notice(c,uid=values['uid'],city=values['city'],title_en=values['title_en'],title_bn=values['title_bn'],body_en=values['body_en'],body_bn=values['body_bn'],source=values['message_kind'])
  if action!='purge':
   c.execute('INSERT INTO admin_changes(entity,record_id,actor,payload) VALUES(?,?,?,?)',(entity,rid,cl.pack(actor),cl.pack({'action':action,'before':dict(before) if before else None})))
   cl.audit(c,actor,entity+'_'+action,rid)
 rows=[dict(r) for r in c.execute('SELECT '+fields+' FROM '+entity+' ORDER BY id DESC LIMIT 500')]
 h.send(200,{'rows':rows,'id':rid,'limit':500});return True
