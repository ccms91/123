"""
Registration Station Flask App  –  Station 1
=============================================
Workflow:
  1. MRZ watcher (mrz_watcher.py) opens /register?<mrz params> in browser
  2. Staff confirm patient info + fill persistent clinic fields → Save
  3. Patient signs on canvas → Save Signature
  4. App writes row to Google Sheet, prints 8 labels, redirects to /done
  5. /done shows status → staff click "Next Patient" → back to /register
"""

import base64
import os
import sys
from datetime import datetime

from flask import (
    Flask,
    redirect,
    render_template,
    request,
    session,
    url_for,
    send_file,
)
from dotenv import load_dotenv

# ── path setup so we can import from project root ──────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

from services.google_sheets import append_registration
from services.label_generator import generate_labels, print_labels

# ── directories ─────────────────────────────────────────────────────────────
SIGNATURES_DIR = os.path.join(ROOT, "signatures")
LABELS_DIR = os.path.join(ROOT, "labels")
os.makedirs(SIGNATURES_DIR, exist_ok=True)
os.makedirs(LABELS_DIR, exist_ok=True)

# ── app ──────────────────────────────────────────────────────────────────────
app = Flask(
    __name__,
    template_folder=os.path.join(ROOT, "templates"),
    static_folder=os.path.join(ROOT, "static"),
)
app.secret_key = os.environ.get("SECRET_KEY", "health-screening-local-secret")
# Sessions need to hold base64 signature – bump to 8 MB cookie threshold
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# ── helpers ──────────────────────────────────────────────────────────────────

def _safe_filename(passport: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in passport)


# ── routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return redirect(url_for("register"))


@app.route("/register")
def register():
    """Show the registration form, optionally pre-filled from MRZ query params."""
    mrz = {
        "name":            request.args.get("name", ""),
        "surname":         request.args.get("surname", ""),
        "given_names":     request.args.get("given_names", ""),
        "dob":             request.args.get("dob", ""),
        "passport_number": request.args.get("passport_number", ""),
        "nationality":     request.args.get("nationality", ""),
        "gender":          request.args.get("gender", ""),
        "expiry":          request.args.get("expiry", ""),
    }
    return render_template("register.html", mrz=mrz)


@app.route("/save-registration", methods=["POST"])
def save_registration():
    """Persist form data in server session, then redirect to signature page."""
    now = datetime.now()
    session["registration"] = {
        "name":            request.form.get("name", "").strip(),
        "surname":         request.form.get("surname", "").strip(),
        "given_names":     request.form.get("given_names", "").strip(),
        "dob":             request.form.get("dob", "").strip(),
        "passport_number": request.form.get("passport_number", "").strip(),
        "nationality":     request.form.get("nationality", "").strip(),
        "gender":          request.form.get("gender", "").strip(),
        "expiry":          request.form.get("expiry", "").strip(),
        "corporation":     request.form.get("corporation", "").strip(),
        "tests_required":  request.form.get("tests_required", "").strip(),
        "vaccine_required":request.form.get("vaccine_required", "").strip(),
        "doctor_name":     request.form.get("doctor_name", "").strip(),
        "doctor_mcr":      request.form.get("doctor_mcr", "").strip(),
        "visit_date":      now.strftime("%d/%m/%Y"),
        "timestamp":       now.strftime("%Y-%m-%d %H:%M:%S"),
    }
    return redirect(url_for("signature"))


@app.route("/signature")
def signature():
    if "registration" not in session:
        return redirect(url_for("register"))
    return render_template("signature.html", patient=session["registration"])


@app.route("/save-signature", methods=["POST"])
def save_signature():
    if "registration" not in session:
        return redirect(url_for("register"))

    data = dict(session["registration"])
    sig_data = request.form.get("signature", "")

    # ── save signature image ────────────────────────────────────────────────
    sig_filename = None
    if sig_data and sig_data.startswith("data:image/png;base64,"):
        try:
            raw = base64.b64decode(sig_data.split(",", 1)[1])
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            sig_filename = f"{_safe_filename(data['passport_number'])}_{ts}.png"
            with open(os.path.join(SIGNATURES_DIR, sig_filename), "wb") as fh:
                fh.write(raw)
        except Exception as exc:
            app.logger.error("Signature save error: %s", exc)

    data["signed"] = "Yes" if sig_filename else "No"
    data["signature_file"] = sig_filename or ""

    # ── Google Sheets ───────────────────────────────────────────────────────
    sheets_ok = False
    try:
        append_registration(data)
        sheets_ok = True
    except Exception as exc:
        app.logger.error("Google Sheets error: %s", exc)

    # ── label printing ──────────────────────────────────────────────────────
    labels_ok = False
    label_pdf = None
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        label_pdf = os.path.join(
            LABELS_DIR, f"labels_{_safe_filename(data['passport_number'])}_{ts}.pdf"
        )
        generate_labels(data, label_pdf)
        labels_ok = print_labels(label_pdf)
    except Exception as exc:
        app.logger.error("Label error: %s", exc)

    # Store label path for manual-print fallback on /done page
    session.pop("registration", None)
    session["last_label_pdf"] = label_pdf

    return redirect(
        url_for("done", sheets=int(sheets_ok), labels=int(labels_ok))
    )


@app.route("/done")
def done():
    sheets_ok = request.args.get("sheets", "1") == "1"
    labels_ok = request.args.get("labels", "1") == "1"
    has_pdf = bool(session.get("last_label_pdf"))
    return render_template(
        "done.html",
        sheets_ok=sheets_ok,
        labels_ok=labels_ok,
        has_pdf=has_pdf,
    )


@app.route("/print-labels")
def print_labels_route():
    """Serve the most recent label PDF so staff can print manually."""
    pdf = session.get("last_label_pdf")
    if not pdf or not os.path.exists(pdf):
        return "No label PDF available.", 404
    return send_file(pdf, mimetype="application/pdf")


# ── run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("REGISTRATION_PORT", 5100))
    print(f"Registration app running at http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
