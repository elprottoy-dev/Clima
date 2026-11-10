"""Authenticated bounded scheduler suitable for an external cron invocation."""
import os,hmac,time,json

def run(db):
 import clinical,upgrade,push
 with db() as c:
  if not getattr(c,'postgres',False):raise RuntimeError('Cloud scheduling requires PostgreSQL')
  # Transaction lock serializes due-job generation; outbox sending uses its own claim.
  if not c.execute('SELECT pg_try_advisory_xact_lock(58347910) AS locked').fetchone()['locked']:return {'busy':True}
  import cloud_transport;cloud_transport.clean(c)
  clinical.run_daily(c);upgrade.tick(c)
  c.execute("INSERT INTO app_settings(key,value) VALUES('scheduler_heartbeat',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(time.time()),))
 with db() as c:push.process(c,limit=3)
 return {'ok':True}
def authorized(header):
 expected=os.getenv('CLIMA_CRON_SECRET','')
 return len(expected)>=32 and hmac.compare_digest(header,'Bearer '+expected)
