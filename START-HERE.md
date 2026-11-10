# CliMa v10 — GitHub + Vercel + Supabase

This version continues v9. It keeps the existing Python application on Vercel and
moves its database to Supabase PostgreSQL. No Oracle or Cloudflare account is needed.
BMD remains removed. The orange interface, bilingual registration, admin CRUD,
clinical records, permissions, reports, forecasts, uploads, exports, reminders,
privacy workflows and encrypted draft queue remain in the existing application.

## What is actually built

- PostgreSQL adapter with compatible encrypted fields; private clima schema.
- Vercel Python entry point that refuses ephemeral SQLite in cloud deployments.
- Authenticated cron endpoint invoked by Supabase Cron every minute.
- Firebase credentials supplied as a server secret; bounded outbox retry processing.
- Brevo HTTPS email delivery in addition to the existing SMTP option.
- Encrypted temporary upload/download chunks to preserve large-file operations.
- GitHub Actions workflow to compile, lint, sign and verify the APK once inputs exist.
- Android system document picker for PDF/JPEG/PNG uploads.
- In-app polling once per minute while visible, reducing free-tier requests.

This is tested source, NOT a deployed system or a compiled APK. Provider accounts
and credentials have not been supplied. Android closed-app report synchronization
is still unfinished; encrypted drafts retry while open and unlocked. Clinical
approval, minor-consent rules, comprehensive UI/device testing and independent
security review have not been completed. No clinical approval is implied.

## 1. GitHub

Create a PRIVATE repository and put the contents of CliMa at its root, including
.github/workflows. Do not upload the parent ZIP as the only repository file.
.gitignore excludes patient databases, credentials, signing keys and backups.
Do not commit .env or any connection URLs/passwords. Do not upload preview.py,
package.json (the local preview helper), public/qa.html or runtime private folders.

## 2. Supabase Free database

Create one free project. This build uses PostgreSQL with the existing application
accounts, MFA and recovery flows; it does not switch users to Supabase Auth.
Keep the clima schema OUT of the API's exposed schemas. Do not add anonymous access.

Use the SESSION POOLER connection from Connect (port 5432, IPv4-compatible), not the
transaction pooler on 6543. Short-lived application connections are closed after
requests. TLS certificates are verified. The administrator/owner URL is only for
local initialization. Install Python requirements on your computer:

    python -m pip install -r requirements.txt

Set CLIMA_DATABASE_URL privately to the owner session-pooler URL, CLIMA_DATA_KEY to
a persistent Fernet key, and CLIMA_ADMIN_PASSWORD to a strong 12+ character password.
Generate a key privately with cryptography. Never regenerate it after collecting data.

    python deployment/init_postgres.py

Set CLIMA_RUNTIME_DB_PASSWORD to a random 24+ character password, then run:

    python deployment/create_backend_role.py

Use the resulting clima_app login in the Vercel database URL, following Supabase's
session-pooler username format (typically clima_app.PROJECT_REF). URL-encode special
characters in the password. This role has no permission to migrate/drop the schema;
it has explicit policies for backend operations, while browser/API roles have none.

The database currently stores encrypted document contents too. It does NOT yet move
attachments into Supabase's separate 1 GB Storage allowance. Thus the free 500 MB
PostgreSQL quota includes encrypted uploads, notices, audit logs and temporary chunks.
20–30 light users may fit; user count alone does not guarantee quota compliance.
Keep files compact, monitor actual usage, and do not enable billing to bypass limits.
Existing 5 MB/file and 20 files/case limits are retained, not a promise all users can
fill them simultaneously on a free database.

## 3. Vercel

Import the repository. Use Framework: Other and the root vercel.json. No static-only
output directory or frontend build command is required. Do not use the older v9
prepare_vercel.py output for this deployment; it is retained for legacy installations.
Set these SERVER environment variables (production only):

| Variable | Value |
|---|---|
| CLIMA_DATABASE_URL | Restricted clima_app session-pooler URL |
| CLIMA_DATA_KEY | Same persistent key used for initialization |
| CLIMA_ADMIN_PASSWORD | Your initial strong admin password |
| CLIMA_CRON_SECRET | Random secret with at least 32 characters |
| FIREBASE_PROJECT_ID | Your Firebase project ID |
| FIREBASE_CREDENTIALS_JSON | Full server service-account JSON |
| BREVO_API_KEY | Brevo API key, not SMTP password |
| CLIMA_SMTP_FROM | Verified Brevo sender email |

Use the stable production *.vercel.app address; no purchased domain is needed.
Vercel Hobby remains restricted to eligible personal/non-commercial use. A 30-user
limit does not make an organizational/commercial service eligible. Provider free
quotas and terms apply; no unlimited or permanent-free guarantee is claimed.

## 4. Scheduled reminders and notifications

Enable pg_cron and pg_net in Supabase. Add Vault secrets clima_origin (your production
HTTPS origin with no trailing slash) and clima_cron_secret (same value as Vercel).
Run deployment/supabase-cron.sql once. It calls /api/cron every minute, so Vercel's
once-daily Hobby cron restriction is not used. This consumes normal function quota.
Daily schedules use Asia/Dhaka. Overlapping generation is locked; push deliveries
have retry leases. A provider timeout can still cause a duplicate notification.
Check Supabase cron/net results and /api/health, which returns 503 for stale heartbeat.
If Supabase pauses for low activity, jobs and the backend stop until resumed.

## 5. Firebase and Brevo

Create a Firebase Android app with package bd.clima.app. Enable FCM and obtain its
Android google-services.json. Keep the SERVER service account in Vercel secrets;
never include it in the APK. Configure a verified sender and API key in Brevo.
The code keeps existing recovery verification, expiry, attempt limits and MFA rules.
Live delivery and credentials must be tested; local tests use a mocked email provider.

## 6. Signed APK through GitHub Actions

Create repository environment android-release. Add repository variable CLIMA_ORIGIN
with your stable Vercel HTTPS origin. Add environment secrets:

- FIREBASE_ANDROID_BASE64: base64 of the Android google-services.json
- KEYSTORE_BASE64: base64 of your release keystore
- CLIMA_KEYSTORE_PASSWORD, CLIMA_KEY_ALIAS, CLIMA_KEY_PASSWORD

Generate and retain your release keystore privately; future updates require the same
key. Run Actions > Build signed CliMa APK > Run workflow. A successful run uploads
CliMa-signed-apk as a private workflow artifact for seven days. The workflow checks
the signature and runs Android lint. It does not publish a public release or Play
listing. Download and install on your phones; test permissions, login, file picker,
notifications with app closed/restarted, exports and network failures. This workflow
has not been run against your accounts and no signed APK is included in this ZIP.

## 7. Backups and release checks

For PostgreSQL use pg_backup.py create FILE.climapg and verify FILE.climapg locally
with the owner connection. Snapshots include all durable tables and the encryption
key inside passphrase encryption; temporary transfer chunks are excluded. Restore
only to a freshly initialized v10 target using the SAME key and --confirm-empty-target.
A real cloud backup/restore drill is still required. The old backup.py is for SQLite.
Do not point it at PostgreSQL. Existing live SQLite data needs a separately verified
migration; do not silently start a blank cloud database and call it migrated.

Run the documented tests before release, then validate the deployed API with synthetic
accounts. Check registration, clinician isolation, admin CRUD, all export formats,
upload/download >4.5 MB, scheduler, recovery delivery and physical-phone behavior.
Free-tier capacity exhaustion must be handled as an outage, never by deleting records
without approved retention actions. Keep offline encrypted backups under your control.

## Reproduce the local verification

    python -m unittest test_server test_clinical test_upgrade test_backup test_free_deployment test_cloud -v
    node test_draft_vault.cjs
    npm ci --prefix tests
    node tests/postgres-harness.mjs

The last command starts a disposable PGlite PostgreSQL wire-protocol server on
127.0.0.1:55432, runs the HTTP workflow tests and the new cloud/backup tests, then
stops it. It creates no provider account and uses synthetic data. This checks SQL
compatibility and application behavior, not Supabase's actual network/pooler or
Vercel execution limits. Do not set CLIMA_TEST_POSTGRES to a real patient database.
