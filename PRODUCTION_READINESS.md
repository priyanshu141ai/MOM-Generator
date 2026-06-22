# Production Readiness Check

This file explains what works now and what must be completed before company use.

## What the App Does Now

- The organizer chooses if AI is allowed for each meeting.
- Meetings without AI still get normal calendar reminders.
- The worker detects ended meetings.
- Demo mode creates a sample transcript.
- Microsoft Graph mode reads the transcript created by Teams.
- The worker creates the summary, MOM, decisions, risks, and action items.
- The organizer can read the transcript and edit the draft.
- Sending remains manual and needs organizer approval.
- Action reminders are created after AI processing.

## Production Design

A hosted system should use these parts:

1. A Teams personal app or tab for the user screen.
2. Microsoft Entra sign-in and role checks.
3. A web service for the screen and API.
4. A separate worker for transcript and AI jobs.
5. Microsoft Graph for calendar, meeting, transcript, and message data.
6. Azure OpenAI for meeting intelligence.
7. Azure SQL or PostgreSQL for shared data.
8. Azure Key Vault for secrets.
9. Application Insights for logs, errors, and alerts.

Do not run many app copies with the current SQLite file. SQLite is only for local demo use.

## Microsoft Setup Needed

- A Microsoft 365 work or school tenant.
- An Entra app registration.
- Admin consent for `OnlineMeetingTranscript.Read.All`.
- The approved online meeting permissions needed to find meetings.
- A cloud communications application access policy.
- Teams transcription enabled for the meeting.
- A Graph change notification subscription created before transcription starts.
- Subscription renewal because Graph subscriptions expire.

The current code can read a linked Teams meeting transcript. It does not yet discover every calendar meeting or create and renew Graph webhook subscriptions. These are required for a fully automatic company rollout.

## Failure Handling Added

- Graph throttling and server errors use retry and backoff.
- `Retry-After` is followed for Graph throttling.
- A transcript that is not ready is checked again later.
- Permission, meeting link, and size errors move to **Needs attention**.
- Unexpected errors stop retrying after the retry limit.
- An atomic database claim prevents two workers from processing one meeting at the same time.
- Reminder and outbox records use duplicate protection.

## Security Work Before Launch

1. Add Microsoft sign-in and check access for every meeting.
2. Use certificate login or a managed identity instead of a client secret where possible.
3. Store secrets in Azure Key Vault, not `.env`.
4. Encrypt stored meeting data and backups.
5. Add audit logs for transcript access, edits, approval, and sending.
6. Add data retention and deletion rules.
7. Remove private data from application logs.
8. Run privacy, security, and penetration tests.

## Operations Work Before Launch

1. Move SQLite data to Azure SQL or PostgreSQL.
2. Run the web app and worker as separate services.
3. Add health checks for the web app, worker, database, Graph, and Azure OpenAI.
4. Add alerts for failed jobs, old waiting jobs, Graph permission errors, and outbox failures.
5. Add database backup and restore tests.
6. Add load tests with long transcripts and many meetings ending together.
7. Add a dead-letter job screen for **Needs attention** items.
8. Add calendar sync and Graph webhook subscription renewal.

## Current Verification

- Pyright reports zero errors and zero warnings.
- Automated service, Graph, retry, and screen tests pass.
- Installed Python packages have no broken dependencies.

## Release Decision

The project is ready for a local demo and for Graph testing inside a company test tenant. It is not ready for real company data until sign-in, managed storage, Graph subscription management, monitoring, and privacy controls are complete.
