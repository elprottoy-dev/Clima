"""Authenticated encrypted temporary chunks for serverless payload limits."""
import base64,hashlib,io,json,time,secrets
from urllib.parse import parse_qs,urlparse
import server,clinical,upgrade
CHUNK=1024*1024

def init(c):
 c.execute('CREATE TABLE IF NOT EXISTS transfers(id TEXT PRIMARY KEY,uid INTEGER,path TEXT,total INTEGER,expires REAL,headers TEXT)')
 c.execute('CREATE TABLE IF NOT EXISTS transfer_parts(id TEXT,part INTEGER,payload TEXT,PRIMARY KEY(id,part))')
def clean(c):
 c.execute('DELETE FROM transfer_parts WHERE id IN (SELECT id FROM transfers WHERE expires<?)',(time.time(),))
 c.execute('DELETE FROM transfers WHERE expires<?',(time.time(),))
def identity(c,environ):
 token=environ.get('HTTP_AUTHORIZATION','').removeprefix('Bearer ')
 s=c.execute('SELECT uid FROM sessions WHERE token=? AND expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
 if not s:raise PermissionError()
 uid=s['uid'];role='admin' if uid==0 else 'user'
 if uid:
  row=c.execute('SELECT * FROM '+('users' if uid>0 else 'staff')+' WHERE id=? AND active=1',(abs(uid),)).fetchone()
  if not row:raise PermissionError()
  if uid<0:role=row['role']
 if role!='user' and __import__('os').getenv('CLIMA_REQUIRE_STAFF_MFA','0')=='1':
  sec=c.execute('SELECT enabled FROM security WHERE uid=?',(uid,)).fetchone()
  if not sec or not sec['enabled']:raise PermissionError()
 return uid,role

def respond(start,status,obj,extra=()):
 body=json.dumps(obj).encode();start(status,[('Content-Type','application/json'),('Cache-Control','no-store'),*extra]);return [body]
def incoming(environ,start):
 path=environ.get('PATH_INFO','');query=parse_qs(environ.get('QUERY_STRING',''))
 if not path.startswith('/api/transfer/'):return None
 try:
  with server.db() as c:
   uid,role=identity(c,environ);clean(c)
   if environ.get('REQUEST_METHOD')=='POST':
    n=int(environ.get('CONTENT_LENGTH',0))
    if not 0<n<1600000:raise ValueError('Chunk too large')
    d=json.loads(environ['wsgi.input'].read(n))
   else:d={}
   if path=='/api/transfer/start' and d:
    total=int(d['total'])
    if not 1<=total<=8 or d.get('path')!='documents':raise ValueError('Invalid upload')
    if c.execute('SELECT COUNT(*) FROM transfers WHERE uid=?',(uid,)).fetchone()[0]>=2:raise ValueError('Finish existing transfers or wait ten minutes')
    tid=secrets.token_urlsafe(24);c.execute('INSERT INTO transfers VALUES(?,?,?,?,?,?)',(tid,uid,'upload:documents',total,time.time()+600,''))
    return respond(start,'200 OK',{'id':tid})
   tid=str(d.get('id') or query.get('id',[''])[0]);r=c.execute('SELECT * FROM transfers WHERE id=? AND uid=? AND expires>?',(tid,uid,time.time())).fetchone()
   if not r:raise PermissionError()
   if path=='/api/transfer/part' and d:
    if r['path']!='upload:documents':raise PermissionError()
    i=int(d['part']);raw=base64.b64decode(d['content'],validate=True)
    if not 0<=i<r['total'] or len(raw)>CHUNK:raise ValueError('Invalid chunk')
    c.execute('INSERT INTO transfer_parts VALUES(?,?,?) ON CONFLICT(id,part) DO UPDATE SET payload=excluded.payload',(tid,i,clinical.pack(d['content'])))
    return respond(start,'200 OK',{'ok':True})
   if path=='/api/transfer/submit' and d:
    if r['path']!='upload:documents':raise PermissionError()
    parts=c.execute('SELECT * FROM transfer_parts WHERE id=? ORDER BY part',(tid,)).fetchall()
    if len(parts)!=r['total']:raise ValueError('Upload incomplete')
    raw=b''.join(base64.b64decode(clinical.unpack(p['payload'])) for p in parts)
    if len(raw)>7500000:raise ValueError('Upload too large')
    c.execute('DELETE FROM transfer_parts WHERE id=?',(tid,));c.execute('DELETE FROM transfers WHERE id=?',(tid,))
    environ['PATH_INFO']='/api/documents';environ['QUERY_STRING']='';environ['wsgi.input']=io.BytesIO(raw);environ['CONTENT_LENGTH']=str(len(raw));environ['CONTENT_TYPE']='application/json'
    return None
   if path=='/api/transfer/read' and environ.get('REQUEST_METHOD')=='GET':
    source=urlparse(r['path']);q=parse_qs(source.query)
    if source.path=='/api/admin/export':
     if role!='admin':raise PermissionError()
    elif source.path=='/api/document':
     a=c.execute('SELECT case_id FROM attachments WHERE id=?',(int(q['id'][0]),)).fetchone()
     if not a:raise PermissionError()
     upgrade.case(c,a['case_id'],uid,role)
    else:raise PermissionError()
    i=int(query.get('part',['-1'])[0]);part=c.execute('SELECT payload FROM transfer_parts WHERE id=? AND part=?',(tid,i)).fetchone()
    if not part:raise ValueError('Chunk missing')
    data=clinical.unpack(part['payload'])
    if i==r['total']-1:
     c.execute('DELETE FROM transfer_parts WHERE id=?',(tid,));c.execute('DELETE FROM transfers WHERE id=?',(tid,))
    return respond(start,'200 OK',{'content':data})
   raise ValueError('Invalid transfer operation')
 except PermissionError:return respond(start,'403 Forbidden',{'error':'Access denied'})
 except (ValueError,KeyError,TypeError):return respond(start,'400 Bad Request',{'error':'Invalid or incomplete transfer'})

def outgoing(environ,start,status,headers,body):
 if len(body)<=3*CHUNK or not status.startswith('200'):start(status,headers);return [body]
 source=environ.get('PATH_INFO','')
 if source not in ['/api/document','/api/admin/export'] or len(body)>80*CHUNK:
  return respond(start,'413 Payload Too Large',{'error':'Narrow the export filters'})
 with server.db() as c:
  uid,_=identity(c,environ);clean(c)
  # Replace prior unfinished downloads for this owner; upload slots remain intact.
  for row in c.execute("SELECT id FROM transfers WHERE uid=? AND path NOT LIKE 'upload:%'",(uid,)).fetchall():
   c.execute('DELETE FROM transfer_parts WHERE id=?',(row['id'],));c.execute('DELETE FROM transfers WHERE id=?',(row['id'],))
  tid=secrets.token_urlsafe(24);total=(len(body)+CHUNK-1)//CHUNK
  if environ.get('QUERY_STRING'):source+='?'+environ['QUERY_STRING']
  safe={k:v for k,v in headers if k.lower() in ['content-type','content-disposition']}
  c.execute('INSERT INTO transfers VALUES(?,?,?,?,?,?)',(tid,uid,source,total,time.time()+600,json.dumps(safe)))
  for i in range(total):c.execute('INSERT INTO transfer_parts VALUES(?,?,?)',(tid,i,clinical.pack(base64.b64encode(body[i*CHUNK:(i+1)*CHUNK]).decode())))
 return respond(start,'200 OK',{'id':tid,'total':total,'headers':safe},[('X-Clima-Transfer','1')])
