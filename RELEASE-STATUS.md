Final v10 verification: all 18 PostgreSQL integration tests passed, including encrypted backup/restore, transfer ownership, scheduler and WSGI authentication checks. The local regression run passed 19 tests with 2 PostgreSQL-only tests skipped, plus the encrypted draft-queue test. Workflow YAML, Vercel JSON and new JavaScript syntax were checked. No provider deployment or Android build was performed.

# CliMa v10 status

Read START-HERE.md for the current GitHub/Vercel/Supabase deployment.
Vercel Python now uses PostgreSQL; no Oracle/Cloudflare requirement.
The existing workflow suite passed on local PGlite PostgreSQL through the wire protocol.
This does not verify actual Supabase pooler, Vercel deployment, Android compilation,
FCM/Brevo delivery, cloud backups or physical devices. Closed-app report sync and
clinical/minor-consent approval remain outstanding.

Historical notes below are retained for comparison and superseded by START-HERE.md.

# CliMa 9.0 release status

This is an updated source package, not a production deployment or a signed APK.

Version 9 removes BMD and adds a static-only Vercel project generator plus private
backend setup scripts. Read FREE-DEPLOYMENT.md. The free route requires an eligible
Vercel Hobby project and a separately provisioned Always Free VM; it is NOT a
Vercel-only backend. All historical implementation notes below are superseded
where they describe BMD availability. No other existing feature was removed.
The original orange/peach palette is restored.

| Area | Implemented | Remaining / verification boundary |
|---|---|---|
| Hosting / Android | Docker, Caddy HTTPS configuration, required real origin, Firebase integration, release signing configuration | Requires domain/server, Firebase project and signing secrets. No deployed endpoint, compiled APK or physical-phone test. |
| Push | Generic private notifications, Android permission, encrypted device tokens, persistent outbox, retries, provider acceptance status | Firebase is not configured or tested. Provider acceptance does not prove device delivery. |
| Patient access | Assigned-clinician restrictions, administrator reassignment, reasoned 60-minute exception grants, audit | Automated ownership and grant tests pass. |
| Encryption | Profile name/age, report/clinical content, advisory content, notifications, attachments, sensitive security fields; passphrase-encrypted database/key backups and isolated non-overwriting restoration | Routing metadata remains plaintext. Encrypted host storage and secure secrets operations are still required. No end-to-end encryption. |
| Accounts | Password change, TOTP with replay protection, mandatory staff enrollment through launcher, recovery-code reset, session revocation | Saved-code recovery works. Verified email setup/reset is implemented and tested with simulated delivery; live SMTP configuration is required. Email reset preserves MFA. SMS recovery is absent. |
| Staff inbox | Case/report/reply alerts, assigned staff targeting, overdue notices | In-app tested; live push pending. |
| Follow-ups | Appointments, reminders, missed status, referral completion | Scheduler must remain running. No external calendar/SMS integration. |
| Clinical records | Structured vital measurements plus clinician-authored findings/tests/plans | Not a validated diagnostic or automated prescribing system. |
| Documents | Private PDF/JPEG/PNG uploads, limits, sanitization, case access controls and download audit | Binaries can be downloaded privately or bundled with identified Excel exports. |
| Notices | Editable bilingual notices, dates, once/daily scheduling, quiet hours, daily preference | Quiet hours affect push; notices remain available in the inbox. |
| Drafts / offline | Passphrase-encrypted local draft, cold-start draft unlock, cached public form schema, automatic queued retries while open/unlocked, idempotent submit and static shell cache | Offline draft access is not server authentication. Closed-app background synchronization is not implemented. |
| Consent / privacy | Consent history, withdrawal/correction/deletion/access requests, admin response, retention review queue, minor flag and safeguarding review | Withdrawal immediately pauses clinician access; approved profile correction and live-account deletion are executable in admin. Backups/previous exports require separate handling. Approved-case scheduled retention cleanup is implemented; a legally validated guardian-consent process remains absent. |
| Exports | Date/category/district filters, section selection, purpose audit, aggregate anonymization with small-cell suppression | Individual columns can be selected; Excel plus document ZIP is supported up to 50 MB. Bundles use all columns in selected sections. Anonymous exports exclude individual/free-text data and cannot bundle documents. |
| Bengali | Improved field, category and workflow labels | Full translation audit remains; some technical/admin values may appear in English. |
| Weather | Current weather, seven-day forecast, district forecast cache and stale indicators; BMD integration removed at owner request | Open-Meteo retained; provider usage terms and availability apply. |

## Run and verify

Follow README.txt. Staff first enroll a TOTP authenticator. Save a recovery code securely.
Run `python -m unittest test_server test_clinical test_upgrade test_backup test_free_deployment -v`.
Sixteen automated tests pass, covering access isolation, grants, encryption, MFA,
recovery, sessions, uploads, scheduling, appointments, exports, privacy fulfillment, recovery email and backup restoration. JavaScript syntax
is checked. These tests do not replace deployment, security or real-device testing.

## Deployment inputs

Set CLIMA_DOMAIN to a real domain pointing at your server. Supply CLIMA_ADMIN_PASSWORD
and a persistent CLIMA_DATA_KEY through secure environment configuration. Add the
Firebase service account as secrets/firebase-service-account.json for the compose mount and
set FIREBASE_PROJECT_ID. Do not place secrets in the source repository or share them
in chat. Run one application instance; this package uses SQLite.

Android requires JDK 17, SDK 35 and compatible Gradle. Supply CLIMA_ORIGIN, Firebase
Android configuration, and release keystore environment variables documented in
README.txt. No Gradle wrapper binary is shipped. Build and verify on real phones,
including denied permissions, killed-app notifications and unreliable connectivity.

## Backups and recovery

`python backup.py create /secure/path/backup.clima` creates an encrypted consistent
SQLite snapshot with its encryption key. Use a unique passphrase of at least 16
characters and keep it separately. `python backup.py verify /secure/path/backup.clima`
checks integrity. Run `python backup.py restore /secure/path/backup.clima --destination /new/isolated-directory`. The directory must not already exist. This restores the matching database/key pair. A trusted operator must verify the restored service before switching production. Do not overwrite a live
DB or rotate its key without a migration. Retain a pre-upgrade backup.

## Source package hygiene

No patient database, runtime data key, Firebase credentials, release keystore,
preview fixtures or compiled APK is included. Dependencies retain upstream licenses;
review PyMuPDF AGPL/commercial terms for the intended distribution.

## Version 5 changes and verification limits

- Live account deletion uses a reviewed request, mandatory reason, and an exact account confirmation. User IDs are never reused after deletion.
- Consent withdrawal prevents clinician list/detail access even with an existing access grant. Administrators retain access to fulfill requests.
- Changing a device registration to another account clears queued notifications belonging to its previous account.
- Recovery email requires current-password verification and an authenticator code when enabled; address verification and reset codes expire after ten minutes, are single-use, and have attempt/rate limits.
- SMTP requires CLIMA_SMTP_HOST, CLIMA_SMTP_PORT (587 default), CLIMA_SMTP_FROM, and optionally CLIMA_SMTP_USER / CLIMA_SMTP_PASSWORD. STARTTLS and certificate verification are mandatory. No live email was sent or verified.
- Browser visual testing was attempted but the browser service timed out. JavaScript syntax passed; this release does not claim complete click-through or mobile visual testing.
- BMD CAP publication was found, but a reliable machine-readable warning feed could not be verified. Automatic official-warning ingestion remains blocked.
- No overnight job, external deployment, independent security audit, clinical approval, physical-phone test or signed APK has been completed.

## Version 6 implementation and verification

- Up to 50 independently encrypted drafts/reports per browser profile, with a queue screen, explicit locking, owner-filtered synchronization, failed-send retention and stable submission IDs.
- Existing v5 drafts migrate after successful passphrase verification, preserving the submission ID; the old ciphertext is removed only after the new encrypted copy saves.
- Retries require an open app, an unlocked vault and a valid session for the same patient. This is not closed-app background synchronization. Browser storage limits still apply.
- Added Bengali export section/column labels, privacy statuses, footer and common error messages. Full translation certification is not claimed.
- Browser checks succeeded using synthetic fixtures: reporting categories, salinity conditional fields, preserved selection on Bengali toggle, account/privacy screens and admin export controls. Orange/peach styling was visually checked. This is not full mobile or live-backend interface coverage.
- Ten Python integration tests passed. `node test_draft_vault.cjs` passed encryption, multi-draft, owner isolation, retry retention and cleanup checks. JavaScript syntax checks passed.
- `python preflight.py` checks configuration without printing secret values. On this environment it correctly reports missing live origin, production credentials, Firebase, SMTP, signing settings and some production dependencies. Run `pip install -r requirements.txt` on the deployment host.
- The owner confirmed no hosting is available. No live deployment, APK build/signing, real push/email test, official-warning feed integration, automatic retention purge, independent audit or approved clinical/minor-consent process was completed in this release.

## Version 7: admin CRUD, retention and monitoring

The Manage records button is visible to administrators after required MFA enrollment.
It provides create, view, edit, archive/delete and restore for users, staff, advisories
and notification schedules. User purge is separate, requires the exact user ID and
a review reason, and deletes live account data. Staff cannot demote/archive themselves.
Passwords are never returned in the management API. Changes have encrypted audit
snapshots. Purged profile snapshots are removed; a minimal approval record remains.
The screen lists the latest 500 records per section and searches that loaded set.
Clinical assessments continue to use clinician-only authoring and appended corrections;
this release does not silently overwrite clinical history through admin CRUD.

Retention automation is now available under Account > Scheduled retention cleanup.
An administrator approves a specific closed case with a reason and time at least
24 hours ahead. Jobs can be held/cancelled. Reopened or revised cases stop for review.
Case updates, uploads, appointments and safeguarding notes invalidate the prior
approval. Cleanup deletes the live case, documents and associated notifications;
patient profiles, backups and previously downloaded exports are outside this job.
Case IDs are not reused. Automatic blanket deletion based solely on age is not enabled.

/api/health returns 200 only when the database can be read and the scheduler heartbeat
is less than five minutes old; otherwise it returns 503. Compose includes a healthcheck.
This is a monitoring signal, not a configured external alerting service.

The Android source version is 7.0; it has not been compiled or signed. No domain,
hosting, Firebase, SMTP or keystore has been provided. Live integration tests, independent
security review, closed-app synchronization, official warning ingestion and approved
clinical/minor-consent processes remain outstanding. The new CRUD/retention frontend
passed JavaScript syntax checks; complete visual and real-phone testing is still required.

Version 7 final verification: all 13 Python tests passed, as did the JavaScript queue test and new frontend syntax checks.

## Version 8: official BMD warning ingestion

The official BMD CAP listing publishes https://cap.bmd.gov.bd/api/cap/rss.xml.
The RSS and a linked CAP document were retrieved successfully during development.
The retrieved bilingual warning was expired and is correctly excluded from active alerts.
A separate worker refreshes the feed every 15 minutes without holding a database
transaction during network requests. Only Actual/Public CAP 1.2 messages are accepted.
Updates/cancellations supersede referenced records; active notices are deduplicated.
HTTPS requests and redirects are restricted to cap.bmd.gov.bd, with size/time limits
and rejection of XML entity declarations. Cached warnings retain their original expiry.
The patient dashboard shows source, affected area, original text, expiry and stale state.
Generic new-warning notifications ask recipients to check the affected area. These
are nationwide feed notices, not personalized district risk assessments. No current
warning in the retrieved feed is explicitly not an all-clear. Earlier version notes
about missing warning ingestion are superseded by this section.

Three new tests cover expiry, test-message exclusion, deduplication, cancellation,
feed failure, source restrictions and XML declarations. This is source verification,
not a continuously operated production feed or a comprehensive security review.

Remaining release gates: provision HTTPS hosting/domain and secrets; configure
Firebase and SMTP; compile/sign/install the Android app; implement and verify
closed-app synchronization; obtain qualified clinical/minor-consent approval;
complete real-device, interface, independent security and deployment recovery tests.
No credentials, clinical approval or physical-device evidence were supplied.

## Version 9 validation

13 existing Python regression tests plus 3 deployment tests pass. Deployment tests
check static-only packaging, private API cache headers, upstream validation, BMD
removal and non-overwriting private configuration. Provider deployment, real SMTP/FCM,
large-export proxy limits and device behavior have not been verified.
