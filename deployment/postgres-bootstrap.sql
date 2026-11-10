-- Run once using the Supabase SQL editor, before the private migration command.
CREATE SCHEMA IF NOT EXISTS clima;
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;
REVOKE ALL ON SCHEMA clima FROM PUBLIC, anon, authenticated;
-- A dedicated login is provisioned by deployment/init_postgres.py, not this file.
CREATE OR REPLACE FUNCTION clima.seal_json(value jsonb) RETURNS text
LANGUAGE plpgsql SET search_path=clima,extensions,pg_catalog AS $$
DECLARE k bytea; iv bytea; payload bytea;
BEGIN
 IF value IS NULL OR value='null'::jsonb THEN RETURN NULL; END IF;
 IF jsonb_typeof(value)='string' AND left(value#>>'{}',7)='enc:v1:' THEN RETURN value#>>'{}'; END IF;
 k=decode(current_setting('clima.data_key'),'hex');
 IF length(k)<>32 THEN RAISE EXCEPTION 'Invalid encryption key'; END IF;
 iv=gen_random_bytes(16);
 payload=decode('80','hex') || int8send(extract(epoch FROM clock_timestamp())::bigint) || iv || encrypt_iv(convert_to(value::text,'UTF8'),substring(k FROM 17 FOR 16),iv,'aes-cbc/pad:pkcs');
 RETURN 'enc:v1:' || translate(replace(encode(payload || hmac(payload,substring(k FROM 1 FOR 16),'sha256'),'base64'),E'\n',''),'+/','-_');
END $$;
CREATE OR REPLACE FUNCTION clima.encrypt_fields() RETURNS trigger
LANGUAGE plpgsql SET search_path=clima,extensions,pg_catalog AS $$
DECLARE rowdata jsonb; col text; val jsonb;
BEGIN
 rowdata=to_jsonb(NEW);
 FOREACH col IN ARRAY TG_ARGV LOOP
  val=rowdata->col;
  IF col='age' AND val IS NOT NULL AND left(val#>>'{}',7)<>'enc:v1:' THEN val=to_jsonb((val#>>'{}')::integer); END IF;
  rowdata=jsonb_set(rowdata,ARRAY[col],coalesce(to_jsonb(clima.seal_json(val)),'null'::jsonb));
 END LOOP;
 NEW=jsonb_populate_record(NEW,rowdata); RETURN NEW;
END $$;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA clima FROM PUBLIC,anon,authenticated;
