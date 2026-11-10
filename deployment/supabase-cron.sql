-- Enable pg_cron and pg_net in Supabase first. Create two Vault secrets in the
-- dashboard: clima_origin=https://YOUR-PRODUCTION.vercel.app and clima_cron_secret
-- (the same random 32+ character secret set in Vercel CLIMA_CRON_SECRET).
SELECT cron.schedule('clima-minute','* * * * *',$job$
 SELECT net.http_post(
  url := (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name='clima_origin') || '/api/cron',
  headers := jsonb_build_object('Content-Type','application/json','Authorization','Bearer ' || (SELECT decrypted_secret FROM vault.decrypted_secrets WHERE name='clima_cron_secret')),
  body := '{}'::jsonb,
  timeout_milliseconds := 55000
 );
$job$);
