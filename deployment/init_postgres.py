"""Run locally once with the database owner URL. Never run migration on cold starts."""
import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg,server
if not os.getenv('CLIMA_DATABASE_URL') or not os.getenv('CLIMA_DATA_KEY'):raise SystemExit('Set CLIMA_DATABASE_URL and the persistent CLIMA_DATA_KEY privately')
with psycopg.connect(os.environ['CLIMA_DATABASE_URL'],sslmode='verify-full',sslrootcert=__import__('certifi').where()) as c:
 c.execute((Path(__file__).with_name('postgres-bootstrap.sql')).read_text())
server.init()
with server.db() as c:
 c.raw.execute('REVOKE ALL ON ALL TABLES IN SCHEMA clima FROM PUBLIC, anon, authenticated')
 c.raw.execute('REVOKE ALL ON ALL SEQUENCES IN SCHEMA clima FROM PUBLIC, anon, authenticated')
 for row in c.raw.execute("SELECT tablename FROM pg_tables WHERE schemaname='clima'").fetchall():
  c.raw.execute(psycopg.sql.SQL('ALTER TABLE clima.{} ENABLE ROW LEVEL SECURITY').format(psycopg.sql.Identifier(row[0])))
print('Schema initialized. Keep clima out of exposed API schemas. Configure a restricted backend login before production.')
