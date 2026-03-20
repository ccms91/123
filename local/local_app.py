"""
Station 1 Local App (runs on the clinic PC)

Coordinates the MRZ scanner, signature pad, and label printing
in a single persistent browser tab. Replaces the "open new tab per
patient" approach with a single tab that stays open all day.

Run:
    python local/local_app.py

Then open in Chrome:
    http://localhost:5001

How it connects to the other local scripts:
    mrz_watcher.py  → POST /api/mrz        (passport scanned)
    sig_watcher.py  → GET  /api/state       (fetch patient data)
                    → POST /api/signature   (send image for preview)

Configuration (environment variables or .env file):
    STATION1_PORT       Local port (default: 5001)
    GOOGLE_CREDS_FILE   Path to Google service account JSON (default: credentials.json)
    GOOGLE_SHEET_NAME   Sheet name (default: HealthScreening)
    SIG_TEMP_FOLDER     Where signature images are cached for PDF filling
"""

import os
import sys
import base64
import threading
from io import BytesIO
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv

load_dotenv()

# Add parent directory so we can import services/
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.label_generator import generate_labels_pdf
from services.google_sheets import append_patient_to_sheet

# ── Config ──────────────────────────────────────────────────────────────────
PORT             = int(os.environ.get("STATION1_PORT", 5001))
GOOGLE_CREDS_FILE = os.environ.get("GOOGLE_CREDS_FILE", "credentials.json")
GOOGLE_SHEET_NAME = os.environ.get("GOOGLE_SHEET_NAME", "HealthScreening")
SIG_TEMP_FOLDER  = os.environ.get("SIG_TEMP_FOLDER",
                                   str(Path(__file__).parent / "sig_temp"))

# ── Flask app ────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.secret_key = os.environ.get("SECRET_KEY", "station1-local-key")

# ── In-memory patient state ──────────────────────────────────────────────────
_lock  = threading.Lock()
_state = {
    "patient":    None,   # dict: name, passport_number, sex, dob, nationality
    "sig_b64":    None,   # data-URI for <img> preview in browser
    "sig_path":   None,   # absolute path on disk (sig_watcher uses for PDF filling)
    "updated_at": None,
}


def _set_state(**kwargs):
    with _lock:
        _state.update(kwargs)
        _state["updated_at"] = datetime.now().isoformat()


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("station1_local.html")


@app.route("/api/state")
def get_state():
    """Browser polls this every 1.5 s to pick up MRZ / signature updates."""
    with _lock:
        return jsonify(dict(_state))


@app.route("/api/mrz", methods=["POST"])
def receive_mrz():
    """Called by mrz_watcher when a new passport is scanned."""
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "No data"}), 400

    with _lock:
        _state["patient"]    = data
        _state["sig_b64"]    = None   # clear previous patient's signature
        _state["sig_path"]   = None
        _state["updated_at"] = datetime.now().isoformat()

    print(f"[APP] MRZ received: {data.get('name')} ({data.get('passport_number')})")
    return jsonify({"ok": True})


@app.route("/api/signature", methods=["POST"])
def receive_signature():
    """Called by sig_watcher to push the signature image for browser preview."""
    if "file" not in request.files:
        return jsonify({"error": "No file in request"}), 400

    f         = request.files["file"]
    img_bytes = f.read()
    ext       = Path(f.filename).suffix.lower() if f.filename else ".png"
    ext       = ext if ext in (".png", ".jpg", ".jpeg", ".bmp") else ".png"
    mime      = "image/jpeg" if ext in (".jpg", ".jpeg") else f"image/{ext.lstrip('.')}"

    # Save to disk so sig_watcher can reference the path for PDF filling
    os.makedirs(SIG_TEMP_FOLDER, exist_ok=True)
    sig_path = os.path.join(SIG_TEMP_FOLDER, f"current_sig{ext}")
    with open(sig_path, "wb") as fp:
        fp.write(img_bytes)

    b64 = base64.b64encode(img_bytes).decode()
    _set_state(
        sig_b64=f"data:{mime};base64,{b64}",
        sig_path=sig_path,
    )

    print(f"[APP] Signature received ({len(img_bytes):,} bytes)")
    return jsonify({"ok": True, "sig_path": sig_path})


@app.route("/api/save", methods=["POST"])
def save_patient():
    """
    Called when staff click 'Save & Print Labels'.
    1. Appends patient row to Google Sheet
    2. Generates 8-label PDF
    3. Returns PDF for browser to print
    4. Clears state (ready for next patient)
    """
    data = request.get_json(force=True)
    if not data:
        return jsonify({"error": "No data"}), 400

    required = ["name", "passport_number", "sex", "dob", "nationality"]
    missing  = [f for f in required if not str(data.get(f, "")).strip()]
    if missing:
        return jsonify({"error": f"Missing required fields: {', '.join(missing)}"}), 400

    sheet_row = {
        "date":           datetime.now().strftime("%d/%m/%Y"),
        "name":           data["name"],
        "passport_number": data["passport_number"],
        "sex":            data["sex"],
        "dob":            data["dob"],
        "nationality":    data["nationality"],
        "test_to_order":  data.get("test_to_order", ""),
        "doctor_name":    data.get("doctor_name", ""),
        "doctor_mcr":     data.get("doctor_mcr", ""),
        "corporate_name": data.get("corporate_name", ""),
        "clinic_hci":     data.get("clinic_hci", ""),
    }

    # Save to Google Sheets (non-blocking — label printing still works if this fails)
    sheets_ok = True
    try:
        append_patient_to_sheet(
            sheet_row,
            creds_file=GOOGLE_CREDS_FILE,
            sheet_name=GOOGLE_SHEET_NAME,
        )
    except Exception as e:
        print(f"[WARN] Google Sheets error: {e}")
        sheets_ok = False

    # Generate label PDF
    try:
        pdf_bytes = generate_labels_pdf(data)
    except Exception as e:
        return jsonify({"error": f"PDF generation failed: {e}",
                        "sheets_ok": sheets_ok}), 500

    # Clear state — ready for next patient
    with _lock:
        _state["patient"]    = None
        _state["sig_b64"]    = None
        _state["sig_path"]   = None
        _state["updated_at"] = datetime.now().isoformat()

    pdf_buffer = BytesIO(pdf_bytes)
    pdf_buffer.seek(0)
    response = send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=False,
        download_name="labels.pdf",
    )
    response.headers["X-Sheets-Status"] = "ok" if sheets_ok else "error"
    return response


@app.route("/api/clear", methods=["POST"])
def clear_state():
    """Lets staff manually reset if they need to start over for a patient."""
    with _lock:
        _state["patient"]    = None
        _state["sig_b64"]    = None
        _state["sig_path"]   = None
        _state["updated_at"] = datetime.now().isoformat()
    return jsonify({"ok": True})


# ── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"[STATION1] Starting on http://localhost:{PORT}")
    print(f"[STATION1] Google Sheet : {GOOGLE_SHEET_NAME}")
    print(f"[STATION1] Sig temp dir : {SIG_TEMP_FOLDER}")
    app.run(host="localhost", port=PORT, debug=False)
