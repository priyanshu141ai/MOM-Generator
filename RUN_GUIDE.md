# Run Meetwise

## Requirements

- Windows with Python 3.11 or newer.
- PowerShell.
- Internet access only when installing packages or using Azure OpenAI.

The project already contains a virtual environment at `.venv` on the current development computer.

## Start the App

Open PowerShell and run:

```powershell
cd "C:\MOM Genreator\Langchain_prompt"
.\.venv\Scripts\python.exe -m streamlit run prompt_ui.py
```

Open this address in a browser:

`http://localhost:8501`

Keep the PowerShell window open while using the app.

## Stop the App

Return to the PowerShell window and press:

`Ctrl+C`

## Create the Environment on Another Computer

Do not copy `.venv` between computers. Create a new environment:

```powershell
cd "C:\MOM Genreator\Langchain_prompt"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Then start the app with the command in the **Start the App** section.

## Optional Azure OpenAI Setup

The app works in demo mode without Azure.

To use Azure OpenAI:

1. Copy `.env.example` to `.env`.
2. Add the Azure endpoint, key, deployment name, and API version.
3. Restart the app.

Do not commit `.env` to GitHub.

## Automatic Teams Transcript Setup

The app does not record the meeting. It reads the transcript made by Microsoft Teams.

This needs a Microsoft 365 work or school tenant. A personal Outlook account is not enough for the required application permissions.

1. Register an app in Microsoft Entra ID.
2. Ask an admin to approve `OnlineMeetingTranscript.Read.All`.
3. Add the required online meeting permission and application access policy.
4. Put the tenant ID, client ID, and client secret in `.env`.
5. Set `TRANSCRIPT_PROVIDER=microsoft_graph`.
6. Set `AUTOMATION_IN_UI=false`.
7. Start the web app and worker in separate terminals.

```powershell
.\.venv\Scripts\python.exe -m streamlit run prompt_ui.py
.\.venv\Scripts\python.exe -m meeting_assistant.worker
```

The Teams online meeting ID and organizer Entra user ID must be linked to each meeting. The current screen allows this link to be entered. Automatic calendar discovery and Graph webhook subscription management are still production work.

The worker gets the transcript and creates a review draft. It does not send the draft. The organizer must review and approve it first.

## Run Checks

Run the automated tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run the type checker:

```powershell
.\.venv\Scripts\pyright.exe
```

Check installed packages:

```powershell
.\.venv\Scripts\python.exe -m pip check
```

## Common Problems

### `streamlit` Is Not Recognized

Use the full environment command:

```powershell
.\.venv\Scripts\python.exe -m streamlit run prompt_ui.py
```

### Port 8501 Is Already Used

Use another port:

```powershell
.\.venv\Scripts\python.exe -m streamlit run prompt_ui.py --server.port 8502
```

Then open `http://localhost:8502`.

### Imports Show Errors in VS Code

Select this interpreter:

`C:\MOM Genreator\Langchain_prompt\.venv\Scripts\python.exe`

Then reload the VS Code window.

### The Interface Uses Old Colors

Restart Streamlit and refresh the browser with `Ctrl+F5`.

### Reset Demo Data

Stop the app, remove `meeting_assistant.db`, and start the app again. This deletes local demo and user data, so only do it when a reset is intended.
