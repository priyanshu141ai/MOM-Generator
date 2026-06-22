# Meetwise

Meetwise is an AI Meeting Assistant. It helps people before and after a meeting.

The app can:

- Save meeting details.
- Send meeting reminders.
- Detect when an authorized meeting ends.
- Collect a Teams transcript automatically through Microsoft Graph when company access is configured.
- Create Minutes of Meeting (MOM).
- Create a short meeting summary.
- Find decisions, risks, and action items.
- Track action items and their due dates.
- Create reminders for unfinished work.

## Important Privacy Rule

The meeting organizer chooses if the AI assistant can join.

When the assistant is **on**, the app can use the transcript and create meeting notes.

When the assistant is **off**, the app cannot use a transcript. It can only send normal meeting reminders.

## Automatic Workflow

When an authorized meeting ends, Meetwise automatically gets the transcript and creates the summary, MOM, decisions, risks, and action items. The organizer does not upload a transcript or start AI processing manually.

Demo mode creates a sample transcript. Microsoft Graph mode reads the transcript already made by Teams. Use **Meetings > Manage meetings > Simulate meeting ended** to test demo mode. The organizer can then view the read-only transcript and edit the draft in **Intelligence**. Sending is always manual.

## Production Processes

Production needs two running processes:

```powershell
# Web screen
.\.venv\Scripts\python.exe -m streamlit run prompt_ui.py

# Automatic transcript worker
.\.venv\Scripts\python.exe -m meeting_assistant.worker
```

Set `AUTOMATION_IN_UI=false` when the worker is running.

## Start the App

Open PowerShell in this folder:

```powershell
cd "C:\MOM Genreator\Langchain_prompt"
.\.venv\Scripts\Activate.ps1
streamlit run prompt_ui.py
```

The app will open at `http://localhost:8501`.

For complete setup, startup, shutdown, and troubleshooting commands, read
[RUN_GUIDE.md](RUN_GUIDE.md).

## Demo Mode

The project works without Microsoft or Azure access. It uses demo data and a simple local AI reader.

This helps you show the project to your manager before asking for company access.

## Azure OpenAI Mode

Copy `.env.example` and name the copy `.env`. Add the Azure OpenAI details given by your company.

Never share secret keys in email, chat, GitHub, or screenshots.

## Run the Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

For a full project explanation, read [PROJECT_DOCUMENTATION.md](PROJECT_DOCUMENTATION.md).

For risks, fixes, and work needed before company use, read
[PRODUCTION_READINESS.md](PRODUCTION_READINESS.md).

To open the dashboard as a personal app inside Microsoft Teams, read
[TEAMS_TESTING_GUIDE.md](TEAMS_TESTING_GUIDE.md).
