# Carevender Bot — Setup Guide

This bot automatically reads patient data from a Google Sheet every 5 minutes and submits it to the Carevender web form. Follow every step below carefully.

---

## Requirements

- A Windows PC running Windows 10 or 11
- An internet connection
- A Google account with access to the patient Google Sheet
- A Carevender account

---

## Step 1 — Install Python 3

1. Open your web browser and go to: **https://www.python.org/downloads/**
2. Click the big yellow **"Download Python 3.x.x"** button.
3. Run the installer.
4. **IMPORTANT:** On the first screen of the installer, tick the box that says **"Add Python to PATH"** before clicking Install Now.
5. Click **Install Now** and wait for it to finish.
6. To verify, open a Command Prompt (press `Win + R`, type `cmd`, press Enter) and type:
   ```
   python --version
   ```
   You should see something like `Python 3.12.0`.

---

## Step 2 — Download the Bot Files

Place all the bot files in a folder on your PC. For example: `C:\carevender_bot\`

The folder should contain:
- `carevender_bot.py`
- `config.json`
- `requirements.txt`
- `run.bat`
- `README.md` (this file)

---

## Step 3 — Create a Virtual Environment

1. Open a Command Prompt (press `Win + R`, type `cmd`, press Enter).
2. Navigate to the bot folder. For example:
   ```
   cd C:\carevender_bot
   ```
3. Run:
   ```
   python -m venv venv
   ```
   This creates a `venv` folder inside the bot folder.

---

## Step 4 — Install Required Packages

In the same Command Prompt window, run:

```
venv\Scripts\pip install playwright gspread google-auth schedule
```

Wait for all packages to download and install. This may take a few minutes.

---

## Step 5 — Install the Chromium Browser

In the same Command Prompt window, run:

```
venv\Scripts\python -m playwright install chromium
```

This downloads a special version of the Chrome browser that the bot uses. It is about 150 MB.

---

## Step 6 — Set Up Google Cloud Service Account

The bot needs permission to read and write your Google Sheet. Follow these steps:

### 6a — Create a Google Cloud Project

1. Go to: **https://console.cloud.google.com/**
2. Sign in with your Google account.
3. At the top of the page, click **"Select a project"** then **"New Project"**.
4. Give it any name (e.g. "Carevender Bot") and click **Create**.

### 6b — Enable the Google Sheets and Drive APIs

1. In the left menu, go to **APIs & Services → Library**.
2. Search for **"Google Sheets API"**, click it, then click **Enable**.
3. Go back to the library, search for **"Google Drive API"**, click it, then click **Enable**.

### 6c — Create a Service Account

1. In the left menu, go to **APIs & Services → Credentials**.
2. Click **"+ Create Credentials"** → **"Service Account"**.
3. Enter any name (e.g. "carevender-bot") and click **Create and Continue**.
4. Skip the optional steps and click **Done**.

### 6d — Download the credentials file

1. On the Credentials page, click on the service account you just created.
2. Go to the **Keys** tab.
3. Click **Add Key** → **Create new key** → choose **JSON** → click **Create**.
4. A file called something like `carevender-bot-xxxx.json` will download.
5. **Rename this file to `credentials.json`** and copy it into your bot folder (e.g. `C:\carevender_bot\credentials.json`).

### 6e — Note the service account email

On the service account details page, copy the **email address** — it looks like:
`carevender-bot@your-project.iam.gserviceaccount.com`

You will need this in the next step.

---

## Step 7 — Share Your Google Sheet with the Bot

1. Open your Google Sheet in a browser.
2. Click the **Share** button (top right).
3. In the "Add people and groups" box, paste the service account email from Step 6e.
4. Set the permission to **Editor** (so the bot can write the Status column).
5. Click **Send** (or **Share**).

---

## Step 8 — Edit config.json

Open `config.json` in Notepad (right-click → Open with → Notepad).

Change the following values to match your setup:

| Setting | What to change |
|---|---|
| `spreadsheet_name` | The exact name of your Google Sheet (as it appears in Google Drive) |
| `worksheet_name` | The tab name inside the sheet (default: "Sheet1") |
| `columns` | The exact column header names in your sheet. Only change these if your column headers differ from the defaults. |
| `check_interval_minutes` | How often (in minutes) the bot checks for new patients. Default is 5. |
| `browser_profile_dir` | Where to save the browser login session. Default `C:\carevender_profile` is fine. |

**Do not change** `carevender_url`, `google_credentials_file`, or `headless` unless instructed.

---

## Step 9 — First Run and Login

1. Double-click **`run.bat`** to start the bot.
2. A browser window will open and navigate to the Carevender login page.
3. **Log in to Carevender manually** in that browser window.
4. Once you are logged in and can see the Carevender dashboard, go back to the black Command Prompt window and press **Enter**.
5. The bot will confirm your login and begin running.

> **You only need to do this login step once.** The bot saves your session in the `C:\carevender_profile` folder. On future runs it will stay logged in automatically.

---

## Step 10 — Running the Bot Daily

Every day, simply double-click **`run.bat`**. The bot will:

1. Open the browser (you should already be logged in).
2. Check the Google Sheet immediately for any unprocessed patients.
3. Submit the web form for each new patient.
4. Write "Done" in the Status column for each successful submission.
5. Continue checking every 5 minutes automatically.

To stop the bot, close the Command Prompt window or press **Ctrl + C** inside it.

---

## Troubleshooting

**"python is not recognized"**
Python was not added to PATH during installation. Re-run the Python installer, tick "Add Python to PATH", and try again.

**"ModuleNotFoundError: No module named 'playwright'"**
Make sure you ran Step 4 correctly and that `venv\Scripts\pip install` succeeded.

**Bot says "Failed to access Google Sheet"**
Check that (a) `credentials.json` is in the bot folder, (b) the sheet name in `config.json` exactly matches your Google Sheet name, and (c) you shared the sheet with the service account email (Step 7).

**Bot submits wrong data or skips fields**
Check the column names in `config.json`. They must exactly match the column headers in your Google Sheet (including capitalisation and spaces).

**Bot logs an error for a patient**
The Status column will show `Error: [message]`. Check `bot.log` in the bot folder for full details.

---

## Log File

The bot writes detailed logs to **`bot.log`** in the bot folder. If anything goes wrong, open this file in Notepad to see exactly what happened and when.
