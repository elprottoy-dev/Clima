"""Vercel entry point. The full application stays in Python."""
import os
if not os.getenv('CLIMA_DATABASE_URL'):raise RuntimeError('Supabase PostgreSQL connection is required; ephemeral SQLite is forbidden')
os.environ['CLIMA_SERVERLESS']='1'
os.environ['CLIMA_REQUIRE_STAFF_MFA']='1'
from wsgi import application as app
