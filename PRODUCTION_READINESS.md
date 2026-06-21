# Production Readiness Check

This file explains what is protected now and what still needs company access.

## Risks Fixed in This Prototype

### Database Use

- SQLite waits when another process is writing.
- Write work uses transactions.
- The database uses WAL mode for safer local use.
- Meeting, email, date, task, and status values are checked.

### Duplicate Work

- The same meeting reminder is not added twice.
- The same approved meeting message is not added twice.
- A completed action cancels its waiting reminders.
- A completed action cannot create a new reminder message.

### AI Processing

- Empty and very large transcripts are blocked.
- Uploaded files must be UTF-8 text and under 1 MB.
- The AI prompt treats transcript text as untrusted data.
- Azure OpenAI has a timeout and three retries.
- AI JSON and action dates are checked before saving.
- AI errors shown to users do not include secret details.

### User Interface

- Database text is escaped before it is placed in custom HTML.
- Important save and send actions show safe error messages.
- The interface follows a compact Teams and Fluent style.
- Desktop and mobile pages are checked with automated tests.

## Checks That Pass

- Python compilation.
- Pyright: zero errors and zero warnings.
- Seven service and screen tests.
- Streamlit health check.

## Work Needed Before Production

These items cannot be completed without the company Microsoft tenant:

1. Register the app in Microsoft Entra.
2. Use the smallest approved Microsoft Graph permissions.
3. Add Microsoft login and check user roles.
4. Build and approve the Teams app or meeting bot.
5. Record clear consent before collecting a transcript.
6. Handle Graph rate limits and `Retry-After` responses.
7. Send messages through an approved Graph or email service.
8. Store secrets in Azure Key Vault instead of a local `.env` file.
9. Move from local SQLite to an approved managed database.
10. Add company logging, monitoring, backup, and alert rules.
11. Add data retention and deletion rules.
12. Complete security, privacy, and load testing.

## Important Limit

The current Streamlit screen looks and behaves like a Teams work tool. A true native Teams experience needs a Teams personal app or tab, a Teams manifest, Microsoft sign-in, and a hosted HTTPS address. A React interface using Fluent UI may be chosen later if the company needs exact Teams controls and single sign-on.
