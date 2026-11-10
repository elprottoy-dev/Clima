# CliMa v12: seasonal reporting and separate updates

The current build adds separate Early warnings and Advisories dashboard panels. Admin compose and message CRUD select a message_kind (warning/advisory). Existing messages default to advisory. In-app notifications contain the same bilingual title/body; lock-screen FCM remains generic to protect privacy. Audience restrictions remain enforced.

Climate health situation opens Local climate and Local climate disasters. Local climate has nine mandatory response rows: three intensities each for heat, rain and cold. Month names and a descriptive days/dates field are required for observed conditions. Does not occur and unknown are explicit alternatives to invented observations. Disasters and reproductive health have all 12 Bengali months, multiple selections per month, exclusive none/unknown/not-applicable/prefer-not-to-answer choices, and Other details. There are 18 disaster choices and 35 symptom/concern choices (including Other). Year-specific reports require a four-digit Bengali year; otherwise records identify a typical remembered annual pattern.

The server validates the full structure and stores the versioned survey inside the existing encrypted case payload. Existing access controls, consent, case history, retention and exports apply. Admin/authorized clinician case detail displays the month-by-month answers. The survey appears as a structured seasonal field in the existing Cases exports; it is not a separately flattened statistical dataset.

The standalone HTML is an interactive sample-data demo, with no login or backend. It resets on reload. It must not be used to collect real health information. Full application source still needs the deployment and provider setup described in START-HERE.md. New forms do not yet integrate with the encrypted offline draft queue. An open form is lost when navigating away or reloading.

## Upgrade
Back up the database and key, then run deployment/init_postgres.py with the existing production key and owner connection before deploying v12 to Vercel. It adds messages.message_kind with an advisory default. Do not create a new encryption key. Local SQLite adds the column on application initialization. No live deployment or actual patient-data migration was performed here.

## Clinical content
These are self-reported symptoms/concerns, not diagnoses or an exhaustive disease catalogue. Bengali wording and research questionnaire validity require clinician/research-team review before patient use. No causal relationship between climate and reported symptoms is inferred. Severe symptoms guidance directs users to prompt care rather than waiting for an app reply.
Sources reviewed 10 November 2026:
- https://www.nhs.uk/conditions/periods/
- https://www.nhs.uk/symptoms/period-pain/
- https://www.nhs.uk/symptoms/vaginal-discharge/
- https://www.nhs.uk/conditions/menopause-and-perimenopause/symptoms/
- https://www.nhs.uk/pregnancy/common-symptoms/vaginal-bleeding/

## Verification
Fourteen local API/regression tests passed, including new survey validation, encrypted storage, cross-user access denial, and warning/advisory audience and notification content tests. Browser checks confirmed the Bengali month list, multiple symptom selection, nine climate rows, rejection of incomplete climate reports, and a demo admin warning appearing in both the user dashboard and notifications. Comprehensive Android/device testing remains outstanding.

The disposable PostgreSQL integration suite also passed all 20 tests, including the two new survey/message tests. This is local integration verification, not live Supabase deployment verification.
