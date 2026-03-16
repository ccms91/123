# Health Screening Clinic — Setup Guide

## What This System Does

| Station | App | What it automates |
|---------|-----|-------------------|
| **1** | Registration | MRZ passport scan → auto-fills form → saves to Google Sheet → prints 8 labels |
| **2(a)** | Height & Weight | Scan label QR → enter measurements → saves to Sheet |
| **3(a)** | Urine dipstick | Camera reads QR + analyses dipstick colours → saves Protein / Sugar / Pregnancy to Sheet |
| **3(b/c)** | BP & Snellen | Scan label QR → enter BP + vision → saves to Sheet; button reads Snellen instructions in patient's language |

---

## STEP 1 — Set Up Google Sheets (10 min, free)

### 1a. Create a Google Cloud Project
1. Go to **https://console.cloud.google.com/**
2. Click **Select a project** → **New Project** → name it `health-clinic` → **Create**

### 1b. Enable APIs
1. In the search bar type `Google Sheets API` → click it → **Enable**
2. Search for `Google Drive API` → **Enable**

### 1c. Create a Service Account
1. Left sidebar → **APIs & Services** → **Credentials**
2. **+ Create Credentials** → **Service Account**
3. Name: `clinic-sheets` → **Create and Continue** → Role: **Editor** → **Done**
4. Click the service account → **Keys** tab → **Add Key** → **Create new key** → **JSON** → **Create**
5. A file downloads (e.g. `health-clinic-abc123.json`). **Keep this safe — it's your password to the sheet.**

### 1d. Create the Google Sheet
1. Go to **https://sheets.google.com** → create a new spreadsheet
2. Rename it exactly: **`HealthScreening`**
3. Click **Share** (top-right)
4. Open the JSON file, find the `"client_email"` value (looks like `clinic-sheets@project.iam.gserviceaccount.com`)
5. Paste that email into the Share box → **Editor** → **Send**

> The sheet columns are created automatically the first time a patient is registered.

---

## STEP 2 — Choose a Deployment Option

### Option A — Local PC on clinic network (recommended)

The app runs on **one Windows PC** in your clinic. All other stations open a browser and go to that PC's IP address. No monthly cost; works even if internet goes down.

**You need:**
- Python 3.10+ (free): https://www.python.org/downloads/
  - During install tick **"Add Python to PATH"** ✅
- The project files (download the zip from GitHub or ask your IT person)
- Google credentials JSON file (from Step 1c)

**Setup:**
1. Copy the project folder to `C:\HealthClinic\` (or anywhere you like)
2. Copy `.env.example` → rename to `.env`
3. Copy `credentials.json` into the same folder
4. Open `.env` and fill in:
   ```
   GOOGLE_CREDS_FILE=credentials.json
   GOOGLE_SHEET_NAME=HealthScreening
   APP_URL=http://localhost:5000
   ```
5. Double-click **`start_server.bat`** → the console shows your local IP:
   ```
   Your local IP addresses:
     http://192.168.1.42:5000
   ```
6. On every station device, open Chrome and go to that IP.

**Station URLs (replace `192.168.1.42` with your IP):**

| Station | URL |
|---------|-----|
| 1 — Registration | `http://192.168.1.42:5000/` |
| 2(a) — Height & Weight | `http://192.168.1.42:5000/station2` |
| 3(b) — BP & Vision | `http://192.168.1.42:5000/station3b` |

---

#### Camera QR scanning on other devices (important!)

Browsers only allow camera access on `https://` pages **or** `localhost`. Plain `http://192.168.x.x` blocks the camera.

**Fix — do this once on each station device:**

1. Open Chrome on the device
2. Go to: `chrome://flags/#unsafely-treat-insecure-origin-as-secure`
3. In the text box, type your server IP: `http://192.168.1.42:5000`
4. Change the dropdown to **Enabled**
5. Click **Relaunch**

This tells Chrome to trust that one IP for camera access. It affects nothing else.

> **Alternatively:** all station apps have a USB barcode scanner / manual input fallback if you prefer not to use the camera.

---

### Option B — Cloud hosting on Render (accessible anywhere, HTTPS automatic)

Use this if you want to access the app from outside the clinic network, or don't want to keep a PC running.

**Free tier note:** Render's free plan "sleeps" the app after 15 minutes of no use. The first request of the day takes ~30 seconds to wake up. To avoid this, sign up for the **Starter plan ($7/month)** or use the UptimeRobot trick below.

**You need:**
- GitHub account: https://github.com (free)
- Render account: https://render.com (sign up with GitHub)

**Setup:**
1. Push the project code to a GitHub repository (public or private)
2. On Render → **New** → **Web Service** → connect your GitHub repo
3. Settings:
   - Runtime: **Python 3**
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app --bind 0.0.0.0:$PORT`
4. Click **Advanced** → **Add Environment Variables**:

   | Key | Value |
   |-----|-------|
   | `GOOGLE_CREDS_JSON` | Paste the **entire contents** of your credentials JSON file |
   | `GOOGLE_SHEET_NAME` | `HealthScreening` |

5. Click **Create Web Service** — wait ~3 minutes
6. Your app URL will be: `https://your-app-name.onrender.com`

**Keep the free tier awake (optional):**
1. Sign up at https://uptimerobot.com (free)
2. Add a new HTTP monitor for your Render URL
3. Set check interval to **5 minutes**
This pings your app before it sleeps, keeping it always warm.

---

## STEP 3 — Set Up Local Watcher Scripts on Clinic PCs

These run on specific clinic PCs alongside the hardware they serve.

### Station 1 — MRZ passport scanner watcher

Runs on the PC connected to the passport/ID scanner.

1. Make sure Python is installed (Step 2, Option A)
2. Create folder: `C:\MRZ_Scans`  (or set `MRZ_WATCH_FOLDER` in `.env` to wherever your scanner saves files)
3. Double-click **`local/start_mrz_watcher.bat`**

When the scanner reads a passport, the browser opens automatically with the patient's details pre-filled.

---

### Station 1 — Signature pad watcher

Runs on the PC connected to the Huion signature tablet.

1. Create folders: `C:\Signatures`, `C:\CompletedForms`, `C:\Templates`
2. Place your MOM WPCM form PDF at `C:\Templates\WPCM_form.pdf`
3. Set these in your `.env`:
   ```
   SIG_WATCH_FOLDER=C:\Signatures
   SIG_OUTPUT_FOLDER=C:\CompletedForms
   MOM_FORM_TEMPLATE=C:\Templates\WPCM_form.pdf
   ```
4. Double-click **`local/start_sig_watcher.bat`**

---

### Station 3(a) — Urine dipstick camera watcher

Runs on the PC connected to the camera inside the urine-test box.

**First-time install** (done automatically by the bat file, needs internet once):
```
pip install opencv-python pyzbar numpy
```

**Setup:**
1. Set in `.env`:
   ```
   URINE_WATCH_FOLDER=C:\UrineCamImages
   URINE_LOG_FOLDER=C:\UrineCamImages\debug
   GOOGLE_CREDS_FILE=credentials.json   (or GOOGLE_CREDS_JSON= if using cloud)
   ```
2. Double-click **`local/start_urine_watcher.bat`**

**Calibrate the strip positions (important — do this once per box setup):**

The script needs to know where each dipstick strip appears in the camera image.

1. Take one sample photo with the box set up as normal and save it somewhere
2. Run:
   ```
   python local/urine_watcher.py --calibrate C:\path\to\sample_photo.jpg
   ```
3. A window opens — hover your mouse over:
   - The reference strip → note `x, y, w, h`
   - The patient strip → note `x, y, w, h`
   - The pregnancy strip → note `x, y, w, h`
4. Add these to your `.env`:
   ```
   REF_STRIP_X=60
   REF_STRIP_Y=200
   REF_STRIP_W=22
   REF_STRIP_H=220
   PAT_STRIP_X=120
   PAT_STRIP_Y=200
   ...
   ```
5. Restart the watcher

Debug images with ROI boxes drawn are saved to `URINE_LOG_FOLDER` after each analysis — use these to verify the calibration is correct.

---

## STEP 4 — Auto-start on PC boot (optional)

To make the watchers start automatically every morning:

1. Press **Win + R**, type `shell:startup`, press Enter
2. Copy shortcuts to the relevant `.bat` files into that folder

---

## Daily Workflow

```
Morning:
  1. Turn on server PC → double-click start_server.bat
  2. Turn on station PCs → watchers auto-start (if set up above)
  3. Open Chrome on each station → go to the station URL

Per patient:
  1. Scan passport (MRZ) → browser auto-opens with details filled
  2. Verify → Save & Print → 8 labels print
  3. Station 2(a): scan label, enter height/weight
  4. Station 3(a): place urine sample in box → dipstick results auto-fill sheet
  5. Station 3(b): scan label, enter BP + Snellen → press 🔊 for patient instructions
```

---

## Station URLs (quick reference)

| Page | URL |
|------|-----|
| Station 1 — Registration | `/` |
| Station 2(a) — Height & Weight | `/station2` |
| Station 3(b) — BP & Vision | `/station3b` |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| **Camera button does nothing** | On LAN: apply the Chrome flag fix (see Step 2, Option A). On Render: already HTTPS, should work. |
| **App takes 30+ sec to load** | Render free tier cold start. Set up UptimeRobot or upgrade to Starter $7/month. |
| **Google Sheet not updating** | Confirm sheet is shared with the service account email. Confirm sheet name matches `GOOGLE_SHEET_NAME`. |
| **MRZ scanner not auto-filling** | Check `start_mrz_watcher.bat` console for errors. Check `MRZ_WATCH_FOLDER` path matches scanner output. |
| **Urine watcher shows wrong results** | Run `--calibrate` mode to re-check strip pixel positions. Check debug images in `URINE_LOG_FOLDER`. |
| **Labels not printing** | Allow popups in browser. Try downloading the PDF manually if popup is blocked. |
| **"Patient not found" error at Station 2/3** | Patient wasn't registered at Station 1 yet, or passport number doesn't match. |
| **`pip` not recognised** | Python wasn't added to PATH. Re-install Python and tick "Add to PATH". |
| **Port 5000 blocked** | Windows Firewall may block it. Open: Windows Firewall → Advanced → Inbound Rules → New Rule → Port 5000 → Allow. |
