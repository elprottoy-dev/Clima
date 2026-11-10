CLIMA CARE 10.0 — Read START-HERE.md first.
GitHub + Vercel Python + Supabase PostgreSQL + Firebase + Brevo.
Legacy local instructions follow; the v9 VM guide is superseded for cloud use.

FREE-TIER SETUP: Read FREE-DEPLOYMENT.md. Vercel frontend + separately hosted persistent backend. BMD removed; other existing features retained.

CLIMA CARE 9.0 — SOURCE RELEASE
Read RELEASE-STATUS.md for implemented features and remaining release blockers.
Connected health reporting, clinician review, admin exports and daily notifications

RUN ON WINDOWS
1. Install Python 3.10 or newer from python.org with PATH enabled.
2. Extract the ZIP. Double-click START-WINDOWS.bat.
3. The launcher creates a virtual environment and installs requirements (internet needed on first setup).
4. Enter an admin password of at least 12 characters in the terminal. Password input is hidden.
5. Open http://localhost:8080. Admin sign-in: /admin, username admin.
Keep the terminal running. Use the same admin password on later starts, or set CLIMA_ADMIN_PASSWORD as an environment secret.

RUN ON MAC / LINUX
python3 -m venv .venv
Activate the virtual environment for your shell, then:
python -m pip install -r requirements.txt
python launch.py

WHAT IS IMPLEMENTED
- Bilingual registration: English/Bengali names, age, Dhaka/Noakhali/Rajshahi, unique username, password.
- Live Open-Meteo weather integration, optional foreground GPS, district fallback and explicit network-failure state.
- Private multi-category reporting: sexual health; reproductive health; salinity exposure; heat; cold; water/sanitation; rain/flood; urinary; skin; respiratory; emotional wellbeing; general health; other concerns.
- Category-specific selectable concerns; free-text symptoms; onset, duration, self-reported severity; optional pregnancy/postpartum details; medicines, allergies and relevant history.
- Optional water source/use and measured TDS, sodium, chloride, salinity or conductivity with units. No conversion or automatic disease attribution.
- Safe contact preferences and explicit consent to authorized review and confidential exports.
- Case history with patient updates, care-team notes, status, priority, assigned clinician, clinical findings, diagnostic certainty, tests, care plan, referral and follow-up date.
- Separate administrator and clinician accounts. Clinicians author clinical assessments; administrators manage operations and exports. Patient reports do not become diagnoses automatically.
- Care-team directory, account activation/deactivation, case filters and individual user records.
- Advisory requests, individual replies, all-district/district broadcasts, message read counts.
- Notification bell, unread badge, individual read state, case-update notices, advisory notices and daily notices. Refreshes every 15 seconds while the app is open and when returning to the app.
- Default general daily check-in at 09:00 Asia/Dhaka. Admin can pause it and create additional schedules. Notices can be edited with date ranges and daily/one-time schedules.
- Daily scheduler runs every 30 seconds. Each schedule sends at most once per Bangladesh calendar day. Restart after delivery time sends today's notice once; missed prior days are not replayed.
- All notifications remain stored for offline users to see later. Firebase background-push integration is included but requires configuration and device verification. No email, SMS or automatic phone calls.

EXPORTS
Admin > User records & exports:
- Per user or all users.
- CSV: UTF-8 BOM, separate normalized tables in one ZIP, formula-injection protection.
- Excel: real .xlsx workbook with Users, Cases, Case history, Requests, Messages and Notifications worksheets; frozen header rows and filters. Values are strings to preserve entered information and avoid spreadsheet formula execution.
- PDF: actual server-generated paginated PDF with Bengali script shaping and page numbers.
Exports include collected profile/case/communication data and read states; passwords, session tokens and encryption keys are never exported. GPS coordinates are not stored. Diagnostic findings are only those entered by a clinician.
Exports are confidential plaintext files after download. Store and share them appropriately.

ROLES AND WORKFLOW
1. User registers and submits a private report with consent.
2. Administrator reviews the queue and assigns a clinician.
3. Clinician signs in using the staff account, reviews the report, records findings and a care plan, and sets follow-up/referral as appropriate.
4. The user receives a generic notification and can read the case record or add information.
5. Administrator exports the individual record or dataset.
Clinicians can access assigned cases or a logged, time-limited grant authorized by an administrator. Administrators can view/export reports but cannot submit clinical assessments. Verify professional credentials before granting clinician access; the system records credentials but does not verify registration with a professional body.
All case notes and clinical entries are visible to the user. Do not use them for hidden staff-only notes. Corrections are appended, retaining prior entries.

SECURITY AND OPERATIONS
Health report bodies and case-history entries are encrypted using Fernet. The first run creates private/data.key unless CLIMA_DATA_KEY supplies a persistent key. Back up this key separately and securely; losing it makes those records unreadable. Never replace the key during upgrades.
Names, ages, advisory content, messages and notification contents are additionally encrypted. Usernames, district and routing/category/status metadata remain ordinary database fields. Use encrypted storage and encrypted backups for the whole deployment. This is not end-to-end encryption.
Passwords use PBKDF2 hashes. Sessions expire after 24 hours. Login throttling, server-enforced roles, patient ownership checks, account disabling and activity/export logs are included. The access log shows the latest 500 events; the database retains earlier events.
The launcher uses Waitress WSGI rather than Python's development HTTP server. For public use, deploy behind HTTPS with restricted network access, monitored backups and a health-data security review. Names and ages already collected in v2 remain intact when using the same database.
A Dockerfile is included. Mount a persistent /data volume for the database, and provide persistent CLIMA_DATA_KEY and CLIMA_ADMIN_PASSWORD secrets. Without a persistent encryption key, replacing a container can lose access to encrypted records. Do not publish an HTTP service carrying real health records.
App data belongs in clima.sqlite3 (or CLIMA_DB). Upgrade by backing up the database and encryption key, replacing source files, reinstalling requirements, and restarting. Tables are added without dropping existing records.
For multiple simultaneous server instances, use a single shared database appropriate to the deployment; this package is designed for one service instance with SQLite. Scheduler deduplication is database-backed.

ANDROID
The android directory contains project source, not a compiled/signed APK. Supply -PCLIMA_ORIGIN=https://your-real-host and add your Firebase android/app/google-services.json. Release signing uses CLIMA_KEYSTORE, CLIMA_KEYSTORE_PASSWORD, CLIMA_KEY_ALIAS and CLIMA_KEY_PASSWORD environment secrets. Open in Android Studio with JDK 17, Android SDK 35 and Gradle 8.9, sync/build, then generate a signed APK/AAB. The Gradle wrapper binary is not included.
Foreground location permission is requested after registration. Approximate location is accepted; users can decline and use district weather. GPS must be enabled by the user in device settings. App-private storage does not need a broad storage permission.
Use a desktop browser for administration and exports. This delivery does not claim Android installation/device QA or background push delivery. There is no live hosted URL in this ZIP.

IMPORTANT LIMITS
- This is a working case-management implementation, not a clinically validated diagnostic device or an emergency service.
- No AI diagnosis, automatic prescriptions, or automatic salinity-health risk classification.
- Private validated PDF/JPEG/PNG uploads and structured observations are included; diagnostic interpretation remains clinician-authored.
- Password changes, saved recovery-code reset, session revocation and staff TOTP MFA are included. Automatic record deletion, staff-only clinical notes and electronic prescribing are not included.
- It has not been independently security-audited, clinically validated, or certified for regulated healthcare use. Set a local clinical governance and safeguarding process before collecting real patient records, including an appropriate process for minors.
- Open-Meteo's public endpoint is for non-commercial use and has limits. Commercial use needs an appropriate plan and a server-side key proxy.
- Dependencies retain their upstream licenses. PyMuPDF offers AGPL/commercial licensing; review its license before proprietary distribution or hosting.

VERIFICATION
Run: python -m unittest test_server test_clinical test_upgrade test_backup -v
Tests exercise registration, login/role separation, encrypted report storage, patient isolation, clinician-only assessment, optimistic conflict detection, case history, notifications/read counts, daily deduplication and next-day delivery, district targeting, account disable/logout, exports, Unicode and formula protection.
JavaScript syntax checked. Synthetic browser QA checked dashboard, bell drawer, categories, conditional symptoms/salinity fields, and admin daily-schedule screens. A sample Bengali PDF was rendered and visually checked. Live weather availability, physical Android behavior and production deployment remain unverified.

SOURCES / REFERENCE
https://www.who.int/health-topics/sexual-and-reproductive-health-and-rights
https://www.who.int/teams/environment-climate-change-and-health/water-sanitation-and-health/water-safety-and-quality/drinking-water-quality-guidelines
https://open-meteo.com/en/docs
https://open-meteo.com/en/pricing
https://developer.android.com/training/data-storage/app-specific
https://pymupdf.readthedocs.io/en/latest/recipes-text.html

VERSION 5 OPERATIONS
Read RELEASE-STATUS.md before deployment. This release adds isolated backup restoration,
verified email recovery with operator SMTP, privacy fulfillment, consent access suspension,
non-reused patient IDs, column selection, document export bundles, and unlocked-draft retries.
No production service or signed APK is included. The new interface changes still need visual QA.

VERSION 6
Use All saved drafts / queue in the report form for multiple encrypted reports.
Keep the app open and unlock the queue to retry submissions. Closing the app stops
synchronization. Protect your draft passphrase; it is not stored or recoverable.
Run node test_draft_vault.cjs for offline queue tests and python preflight.py for
configuration checks. Read RELEASE-STATUS.md for the actual verification limits.

VERSION 7 ADMINISTRATION
After admin login and MFA setup, choose Manage records for user/staff/advisory/schedule
CRUD. Delete archives; Restore reverses it. Permanent user deletion has a separate
confirmation and must follow the operator's approved retention process.
Account > Scheduled retention cleanup supports delayed case deletion, holds and
cancellation. The service must stay running. Check RELEASE-STATUS.md before use.
