# Test Meetwise in Your Microsoft Teams

## First Check Your Account

Open Microsoft Teams and go to **Apps** and then **Manage your apps**.

Look for **Upload an app**.

- If you can see it, continue with this guide.
- If you cannot see it, your account or tenant does not allow custom app upload.
- A personal Outlook or Hotmail account may not have this option.
- Microsoft 365 Family is also a personal plan. It is not a company tenant.
- You may need a Microsoft 365 work, school, or developer tenant.

## What This Test Will Do

This test opens the Meetwise dashboard as a personal tab inside Teams.

It does not yet add a bot to meetings. It does not collect real Teams transcripts. Those features need Microsoft Graph and Teams bot approval.

## Step 1: Start Meetwise

```powershell
cd "C:\MOM Genreator\Langchain_prompt"
.\.venv\Scripts\Activate.ps1
streamlit run prompt_ui.py
```

Keep this PowerShell window open.

## Step 2: Create a Public HTTPS Address

Teams cannot open `localhost`. It needs a public HTTPS address.

One simple choice is VS Code Port Forwarding:

1. Open the **Ports** panel in VS Code.
2. Choose **Forward a Port**.
3. Enter `8501`.
4. Sign in when VS Code asks.
5. Set the port visibility to **Public** for this short demo.
6. Copy the HTTPS address.

Do not use real or private meeting data while the port is public. Stop port forwarding after the test.

## Step 3: Build the Teams ZIP

Replace the sample URL with your public HTTPS address:

```powershell
.\scripts\build_teams_package.ps1 -PublicUrl "https://your-address.example.com"
```

The script creates:

`teams\build\meetwise-teams.zip`

## Step 4: Upload to Teams

1. Open Teams with the same account.
2. Open **Apps**.
3. Open **Manage your apps**.
4. Choose **Upload an app**.
5. Choose **Upload a custom app**.
6. Select `teams\build\meetwise-teams.zip`.
7. Choose **Add**.

Meetwise should open as a personal Teams app.

## If Upload an App Is Missing

You cannot fix this inside the Meetwise code. The Teams account or tenant must allow custom apps.

For a company account, ask the Teams administrator to allow custom app upload for your account. For a personal Outlook or Hotmail account, use a Microsoft 365 tenant account that supports Teams app development.

## After the Test

1. Stop the public port forwarding.
2. Stop Streamlit with `Ctrl+C`.
3. Remove the custom app from Teams if it is no longer needed.
