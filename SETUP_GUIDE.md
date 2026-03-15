# Health Screening Clinic - Station 1: Registration

## What This App Does

When a patient arrives at your clinic:
1. **MRZ Scanner** reads their passport → data auto-fills the web form
2. **Clinic Assistant** verifies the info on the web form and clicks **Save**
3. The app **prints 8 labels** (for urine, height/weight, BP, blood tubes, CXR, etc.)
4. The app **saves patient data to Google Sheets** (one row per patient)
5. **Signature pad** captures patient signature → auto-inserts into MOM form PDF

---

## Setup Instructions (Step by Step)

### PART A: Set Up Google Sheets (10 minutes)

#### Step 1: Create a Google Cloud Project
1. Go to https://console.cloud.google.com/
2. Click **Select a Project** → **New Project**
3. Name it: `health-clinic` → Click **Create**

#### Step 2: Enable Google Sheets API
1. In the search bar at the top, type: `Google Sheets API`
2. Click on it → Click **Enable**
3. Also search for and enable: `Google Drive API`

#### Step 3: Create a Service Account (this is like a robot user)
1. Go to **APIs & Services** → **Credentials** (left sidebar)
2. Click **+ Create Credentials** → **Service Account**
3. Name: `clinic-sheets` → Click **Create and Continue**
4. Role: Select **Editor** → Click **Continue** → **Done**
5. Click on the service account you just created
6. Go to **Keys** tab → **Add Key** → **Create new key** → **JSON** → **Create**
7. A file will download (e.g., `health-clinic-xxxx.json`). **Keep this safe!**

#### Step 4: Create and Share Your Google Sheet
1. Go to https://sheets.google.com → Create a new spreadsheet
2. Name it: `HealthScreening`
3. Click **Share** (top right)
4. Open the JSON file you downloaded → find the `"client_email"` value
5. Paste that email into the Share dialog → give it **Editor** access → **Send**

---

### PART B: Deploy the Web App on Render (10 minutes)

#### Step 1: Push Code to GitHub
1. Create a GitHub account if you don't have one: https://github.com
2. Create a new repository called `health-clinic`
3. Upload all the files from this project to that repository

#### Step 2: Deploy on Render
1. Go to https://render.com → Sign up with GitHub
2. Click **New** → **Web Service**
3. Connect your `health-clinic` GitHub repository
4. Settings:
   - **Name**: `health-clinic` (or any name)
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
5. Click **Advanced** → **Add Environment Variable**:
   - Key: `GOOGLE_CREDS_JSON`
   - Value: Open the JSON credentials file, copy ALL the text, paste it here
   - Key: `GOOGLE_SHEET_NAME`
   - Value: `HealthScreening`
6. Click **Create Web Service**
7. Wait 2-3 minutes. Your app will be live at: `https://health-clinic.onrender.com`

---

### PART C: Set Up Local Scripts on Clinic PC (15 minutes)

These scripts run on the clinic computer (not online).

#### Step 1: Install Python
1. Go to https://www.python.org/downloads/
2. Download and install Python (check **"Add to PATH"** during install!)
3. Open **Command Prompt** (search for "cmd" in Start menu)

#### Step 2: Install Required Packages
In Command Prompt, type:
```
pip install watchdog PyMuPDF
```

#### Step 3: Set Up MRZ Watcher
1. Create a folder on your PC: `C:\MRZ_Scans` (this is where the scanner saves files)
2. Edit `local/mrz_watcher.py`:
   - Change `WATCH_FOLDER` to match your scanner's output folder
   - Change `APP_URL` to your Render app URL (e.g., `https://health-clinic.onrender.com`)
3. To run: Double-click `mrz_watcher.py` or run in Command Prompt:
   ```
   python local/mrz_watcher.py
   ```

#### Step 4: Set Up Signature Watcher
1. Create folders: `C:\Signatures`, `C:\CompletedForms`, `C:\Templates`
2. Place your MOM WPCM form PDF in `C:\Templates\WPCM_form.pdf`
3. Edit `local/sig_watcher.py` to match your folder paths
4. To run:
   ```
   python local/sig_watcher.py
   ```

#### Step 5: (Optional) Auto-start on PC boot
To make the watchers start automatically when you turn on the PC:
1. Press `Win + R`, type `shell:startup`, press Enter
2. Create shortcuts to `mrz_watcher.py` and `sig_watcher.py` in that folder

---

## How to Use (Daily Workflow)

1. **Turn on PC** → MRZ watcher and Signature watcher start automatically
2. **Open browser** → Go to your app URL (bookmark it!)
3. **Patient arrives** → Scan passport with MRZ scanner
4. **Data auto-fills** in the browser form
5. **Verify details** → Adjust if needed → Click **Save & Print Labels**
6. **8 labels print** automatically
7. **Google Sheet** updates with the patient's row
8. **Get signature** → Patient signs on Huion tablet → Signature auto-saves
9. **MOM form + Pregnancy declaration** PDFs are generated in the output folder

---

## Label Layout (on A4 paper)

```
┌─────────────────┐  ┌─────────────────┐
│ [QR]  │  Urine  │  │ [QR]  │ Height  │
│       │         │  │       │ & Weight│
│ Label 1         │  │ Label 2         │
└─────────────────┘  └─────────────────┘
┌─────────────────┐  ┌─────────────────┐
│ [QR]  │  BP     │  │ [QR]  │ Tag to  │
│       │         │  │       │ Patient │
│ Label 3         │  │ Label 4         │
└─────────────────┘  └─────────────────┘
┌─────────────────┐  ┌─────────────────┐
│ Blood Tube      │  │ Blood Tube      │
│ Name, DOB, etc. │  │ (Same as 5)     │
│ Label 5         │  │ Label 6         │
└─────────────────┘  └─────────────────┘
┌─────────────────┐  ┌─────────────────┐
│ [Lab Order QR]  │  │ Name    │  CXR  │
│ Passport|MCR|.. │  │ Passport│       │
│ Label 7         │  │ Label 8         │
└─────────────────┘  └─────────────────┘
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Labels won't print | Check browser allows popups. Try downloading the PDF manually. |
| Google Sheet not updating | Check that the sheet is shared with the service account email. |
| MRZ not auto-filling | Check the MRZ watcher is running. Check the watch folder path. |
| Form fields missing | Hard refresh the browser: Ctrl + Shift + R |
