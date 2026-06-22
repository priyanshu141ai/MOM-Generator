# Meetwise Project Document

## 1. Project Name

AI Meeting Intelligence and Follow-Up Assistant

The app name used in the demo is **Meetwise**.

## 2. The Problem

People spend a lot of time writing meeting notes. They may also forget tasks after a meeting.

This can cause:

- Missed work.
- Late work.
- Confusion about who owns a task.
- Different meeting note formats.
- Too many manual reminder messages.

## 3. The Solution

Meetwise helps with meeting notes and follow-up work.

It can create:

- Minutes of Meeting (MOM).
- A short summary.
- A decision list.
- An action item list.
- A risk list.
- Meeting and task reminders.

The organizer checks the notes before they are shared.

## 4. How the App Works

### Before a Meeting

1. The organizer adds the meeting.
2. The organizer adds attendees.
3. The organizer chooses if the AI assistant can join.
4. The app creates meeting reminders.

### During a Meeting

If the assistant is allowed, it can collect the transcript after Microsoft Teams access is added.

If the assistant is not allowed, it does not collect or read the transcript.

### After a Meeting

1. The app detects that the meeting ended.
2. The transcript provider collects the transcript automatically.
3. The transcript is sent to the AI engine.
4. The AI engine creates notes, decisions, risks, and tasks.
5. The organizer views the transcript and edits the draft.
6. The organizer chooses who will receive it.
7. The app adds the messages to the outbox.
8. The reminder engine follows each task until it is complete.

## 5. The Two Reminder Systems

### Meeting Reminders

These reminders work even when the AI assistant is off.

The app creates reminders:

- One day before the meeting.
- Thirty minutes before the meeting.
- Ten minutes before the meeting.

### Task Reminders

These reminders are made from action items found after a meeting.

The app creates reminders:

- Three days before the due date.
- One day before the due date.
- On the morning of the due date.
- After the task becomes overdue.

## 6. Main Parts of the Project

### User Interface

`prompt_ui.py` contains the Streamlit screens.

The screens are:

- Overview.
- Meetings.
- Intelligence.
- Action tracker.
- Notifications.
- Integrations.

### Database Service

`meeting_assistant/database.py` saves meetings, attendees, notes, tasks, and reminders in SQLite.

### AI Service

`meeting_assistant/ai_engine.py` reads the transcript.

It uses Azure OpenAI when company access is ready. It uses a simple demo reader when access is not ready.

### Automation Service

`meeting_assistant/automation.py` detects ended meetings, gets a transcript, starts AI processing, saves the draft, and schedules action reminders.

`meeting_assistant/graph_transcripts.py` reads the transcript already created by Microsoft Teams. It uses Microsoft Graph. The app does not record the meeting itself.

`meeting_assistant/worker.py` runs this work outside the web screen. This is the correct process for a hosted system.

### Reminder Service

`meeting_assistant/reminders.py` creates meeting reminders and task reminders.

### Communication Service

`meeting_assistant/communications.py` creates messages for email and Teams.

The current project uses a demo outbox. It does not send real messages yet.

## 7. Data Safety

- The organizer must turn on the assistant for each meeting.
- Meetings without the assistant do not use transcripts.
- The organizer checks AI notes before sharing them.
- Secret keys are kept in `.env` and should not be added to GitHub.
- The demo stores information on the local computer.
- The company must decide how long production data is kept.

## 8. What Works Now

- Local meeting setup.
- Optional AI permission.
- Meeting reminders.
- Automatic meeting-end detection.
- Automatic demo transcript collection.
- Automatic Microsoft Teams transcript retrieval through Microsoft Graph when tenant access is configured.
- Read-only transcript viewing for the organizer.
- Demo transcript reading.
- Azure OpenAI connection support.
- MOM, summary, decisions, risks, and action items.
- Organizer review.
- Action tracking.
- Task reminder schedules.
- Demo email and Teams outbox.
- Local SQLite storage.

## 9. What Needs Company Access

The following parts need approval from the company:

- Microsoft Entra app registration.
- Microsoft Graph permissions.
- Microsoft Teams app or meeting bot.
- Meeting transcript permission.
- Azure OpenAI details.
- An approved email sender.
- Data storage and removal rules.

## 10. Benefits to the Company

- Less time spent writing notes.
- Clear task owners.
- Fewer missed due dates.
- Better follow-up after meetings.
- One common meeting record format.
- Better control for private meetings.

## 11. Project Folder

```text
Langchain_prompt/
|-- prompt_ui.py
|-- requirements.txt
|-- README.md
|-- PROJECT_DOCUMENTATION.md
|-- .env.example
|-- meeting_assistant.db
|-- meeting_assistant/
|   |-- __init__.py
|   |-- database.py
|   |-- ai_engine.py
|   |-- automation.py
|   |-- reminders.py
|   `-- communications.py
`-- tests/
    |-- __init__.py
    |-- test_services.py
    `-- test_ui.py
```

## 12. Future Work

1. Connect Microsoft login.
2. Read calendar meetings from Microsoft Graph.
3. Add calendar meeting discovery and Graph webhook subscriptions.
4. Approve transcript access and the application access policy.
5. Send real email and Teams messages.
6. Add company data rules and audit logs.
7. Deploy the app on an approved company server.
