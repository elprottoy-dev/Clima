> Superseded for the requested cloud setup: read START-HERE.md (v10). This file documents the optional legacy v9 VM deployment only.

# CliMa v9: free-tier deployment route

This is a deployment preparation package, not an already hosted service. Vercel
alone cannot run the current persistent SQLite database and background scheduler.
This route uses Vercel Hobby for static files and API forwarding, an Oracle Always
Free VM for the existing Python backend, and Firebase Cloud Messaging for push.
No existing feature is intentionally removed except BMD warnings and BMD links.
Open-Meteo current weather/forecasts, orange theme, Bengali, admin CRUD, encrypted
records, documents, exports, scheduling, retention, email recovery and draft queues remain.
Previously unfinished closed-app sync, APK compilation and clinical/device/security
validation are still unfinished; a hosting configuration does not complete them.

## Free-plan conditions

- Vercel Hobby is limited to personal, non-commercial use. Do not use it for an
  ineligible organizational/commercial service. The backend can serve the same
  interface directly if Vercel Hobby is unsuitable; no interface features are lost.
- Oracle requires identity/card verification for most signups. Only choose resources
  labeled Always Free in the home region, not trial-only resources. Capacity may
  be unavailable and idle resources can be reclaimed. Do not upgrade billing to
  solve a capacity problem if your requirement is strictly zero spend.
- Free-tier limits are not unlimited hosting or an uptime commitment. Keep a separate
  encrypted backup and matching key; the provider's disk is not your only backup.
- FCM itself is no-cost. You still need a Firebase project and Android configuration.
- Email recovery needs a working SMTP provider/account. Use an existing provider's
  free allowance if permitted; no unlimited free SMTP account is bundled.
- Open-Meteo's free API is for permitted non-commercial usage. Review its terms if
  this becomes an organizational/commercial deployment.

## 1. Backend VM

Create an eligible Always Free Ubuntu VM with persistent boot storage. Install Docker
Engine and the Compose plugin using Docker's official instructions. Allow inbound
80/443 and restrict SSH to your administrator's address. Do not expose port 8080.
Use a DNS hostname you control (a free DNS hostname can work) pointing to the VM;
the generated Vercel hostname cannot serve as the backend hostname.

Copy the source to the VM, excluding patient data and secrets from Git. In CliMa:

    python3 -m pip install cryptography
    python3 deployment/prepare_server.py --domain YOUR_BACKEND_HOSTNAME

This creates .env with a random administrator password and persistent encryption
key. View/edit it privately on your own server, never paste it into chat or Git.
The script refuses to overwrite existing configuration. Save the key separately.

For push: put the Firebase service account at secrets/firebase-service-account.json
and set FIREBASE_PROJECT_ID in .env. The container's application user must be able
to read the directory/file. After building, obtain its UID with:

    docker compose build
    docker compose run --rm --no-deps --entrypoint id app -u

Set secrets directory and file ownership to that UID (sudo chown), permissions 700
for the directory and 600 for the file. Keep the service account out of the Vercel
project. With no Firebase project configured, the backend starts but push is pending.

Set CLIMA_SMTP_HOST, PORT, FROM, USER and PASSWORD in .env using your provider's
STARTTLS credentials. Do not assume an ordinary mailbox password is accepted.

    docker compose up -d --build

Verify https://YOUR_BACKEND_HOSTNAME/api/health returns 200, then sign in and enroll
staff MFA. Persist the Docker volume; do not run docker compose down -v. The backend
scheduler handles daily messages, appointments, retention and push retries every
30 seconds without Vercel cron. If the VM stops, those jobs stop too.

## 2. Prepare the Vercel-only project

On your development computer, in CliMa:

    python deployment/prepare_vercel.py --backend https://YOUR_BACKEND_HOSTNAME --output vercel-site

Use the real HTTPS backend hostname. This creates a NEW directory and refuses to
replace existing files. It copies an explicit list of public assets only: no patient
DB, Python source, Android credentials, environment file or backup. Never select
the entire CliMa source directory as the Vercel static output directory.

Put the generated vercel-site directory in its own GitHub repository and import
that repository into Vercel. Framework: Other; Output Directory: public; no build
command. vercel.json forwards /api/* to the backend and maps /admin to the interface.
API caching is disabled. Login, uploads, exports and administration use the same
browser origin, so no broad CORS permission is introduced. Vercel proxy transfer
and timeout quotas still apply. If a large export hits a proxy limit, access the
same admin interface directly on the backend HTTPS hostname to download it.

No Vercel Functions or Vercel cron jobs are needed. Do not add database or Firebase
service-account secrets to Vercel. Use a stable production hostname in the Android
CLIMA_ORIGIN build setting, not an expiring preview deployment.

## 3. Validate before collecting real records

Use synthetic accounts: register, authenticate, enroll staff MFA, create/assign a
case, reply, upload a document, download CSV/XLSX/PDF, edit/archive/restore admin
records, check scheduled notices and encrypted backup restoration. Test quota/error
responses without losing draft content. Then configure/build/sign Android and test
FCM while closed, denied permissions, restart and intermittent connectivity. Free
hosting does not provide clinical approval or independent security review.

## Reference documentation (checked 7 November 2026)

https://vercel.com/docs/plans/hobby
https://vercel.com/docs/routing/rewrites
https://vercel.com/kb/guide/is-sqlite-supported-in-vercel
https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm
https://www.oracle.com/cloud/free/faq/
https://firebase.google.com/pricing
https://open-meteo.com/en/terms
