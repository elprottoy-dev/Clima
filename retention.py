"""Explicitly approved, delayed case retention cleanup with holds and re-review."""
import datetime
import clinical as cl

def init(c):
 c.execute('''CREATE TABLE IF NOT EXISTS retention_jobs(case_id INTEGER PRIMARY KEY,due REAL,state TEXT,version INTEGER,approved_by TEXT,reason TEXT,created TEXT DEFAULT CURRENT_TIMESTAMP,completed TEXT)''')

def schedule(c,cid,due,actor,reason,confirmation,now=None):
 now=now or datetime.datetime.now(datetime.timezone.utc)
 row=c.execute('SELECT * FROM cases WHERE id=?',(cid,)).fetchone()
 if not row or row['status']!='closed':raise ValueError('Only closed cases can be approved for retention cleanup')
 if confirmation!='DELETE CASE '+str(cid):raise ValueError('Type DELETE CASE followed by the case number')
 if len(reason.strip())<10 or len(reason)>2000:raise ValueError('Document the retention review and approval reason')
 at=datetime.datetime.fromisoformat(due)
 if not at.tzinfo or (at-now).total_seconds()<86400:raise ValueError('Schedule at least 24 hours ahead with an explicit timezone')
 if (at-now).days>3650:raise ValueError('Schedule no more than ten years ahead')
 c.execute('INSERT INTO retention_jobs(case_id,due,state,version,approved_by,reason) VALUES(?,?,?,?,?,?) ON CONFLICT(case_id) DO UPDATE SET due=excluded.due,state=excluded.state,version=excluded.version,approved_by=excluded.approved_by,reason=excluded.reason,completed=NULL',(cid,at.timestamp(),'scheduled',row['version'],cl.pack(actor),cl.pack(reason)))
 cl.audit(c,actor,'retention_scheduled',cid)

def tick(c,now=None):
 now=now or datetime.datetime.now(datetime.timezone.utc)
 for job in c.execute("SELECT * FROM retention_jobs WHERE state='scheduled' AND due<=?",(now.timestamp(),)).fetchall():
  cid=job['case_id'];row=c.execute('SELECT status,version FROM cases WHERE id=?',(cid,)).fetchone()
  if row and (row['status']!='closed' or row['version']!=job['version']):
   c.execute("UPDATE retention_jobs SET state='review_required' WHERE case_id=?",(cid,));cl.audit(c,'scheduler','retention_review_required',cid);continue
  if row:
   c.execute('DELETE FROM push_outbox WHERE notice_id IN (SELECT id FROM notices WHERE link_case=?)',(cid,))
   c.execute('DELETE FROM notice_reads WHERE nid IN (SELECT id FROM notices WHERE link_case=?)',(cid,))
   c.execute('DELETE FROM notices WHERE link_case=?',(cid,))
   for table in ['case_entries','access_grants','appointments','attachments','consent_events']:c.execute('DELETE FROM '+table+' WHERE case_id=?',(cid,))
   c.execute('DELETE FROM cases WHERE id=?',(cid,))
  c.execute("UPDATE retention_jobs SET state='completed',completed=? WHERE case_id=?",(now.isoformat(),cid));cl.audit(c,'scheduler','retention_completed',cid)

def route(h,c,d,role,actor):
 if role!='admin':raise PermissionError()
 if h.command=='POST':
  cid=int(d['case_id']);action=d.get('action');reason=cl.text(d,'reason',2000,True)
  if action=='schedule':schedule(c,cid,str(d.get('due','')),actor,reason,str(d.get('confirmation','')))
  elif action in ['hold','cancel']:
   job=c.execute('SELECT state FROM retention_jobs WHERE case_id=?',(cid,)).fetchone()
   if not job or job['state']=='completed':raise ValueError('Active retention job not found')
   c.execute('UPDATE retention_jobs SET state=?,reason=? WHERE case_id=?',('held' if action=='hold' else 'cancelled',cl.pack(reason),cid));cl.audit(c,actor,'retention_'+action,cid)
  else:raise ValueError('Invalid retention action')
 jobs=[{**dict(r),'approved_by':cl.unpack(r['approved_by']),'reason':cl.unpack(r['reason'])} for r in c.execute('SELECT * FROM retention_jobs ORDER BY due DESC LIMIT 500')]
 h.send(200,{'jobs':jobs});return True
