"""Grant a private backend login access only to CliMa's private schema."""
import os,psycopg
from psycopg import sql
password=os.environ.get('CLIMA_RUNTIME_DB_PASSWORD','')
if len(password)<24:raise SystemExit('Set CLIMA_RUNTIME_DB_PASSWORD to a random password of 24+ characters')
with psycopg.connect(os.environ['CLIMA_DATABASE_URL'],sslmode='verify-full',sslrootcert=__import__('certifi').where()) as c:
 if not c.execute("SELECT 1 FROM pg_roles WHERE rolname='clima_app'").fetchone():
  c.execute(sql.SQL('CREATE ROLE clima_app LOGIN PASSWORD {}').format(sql.Literal(password)))
 else:raise SystemExit('clima_app already exists; refusing to rotate its password implicitly')
 c.execute('GRANT USAGE ON SCHEMA clima,extensions TO clima_app')
 c.execute('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA clima TO clima_app')
 c.execute('GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA clima TO clima_app')
 c.execute('GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA clima TO clima_app')
 for (table,) in c.execute("SELECT tablename FROM pg_tables WHERE schemaname='clima'").fetchall():
  c.execute(sql.SQL('CREATE POLICY backend_only ON clima.{} FOR ALL TO clima_app USING(true) WITH CHECK(true)').format(sql.Identifier(table)))
print('Created restricted clima_app login. Use its session-pooler connection in Vercel; never expose it to the frontend.')
