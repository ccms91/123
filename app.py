"""
Health Screening Clinic - Station 1: Registration
Main Flask application
"""

import os
import json
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from services.label_generator import generate_labels_pdf
from services.google_sheets import append_patient_to_sheet, update_patient_in_sheet

app = Flask(__name__)

# ── Configuration ──────────────────────────────────────────────────────────
# Google Sheets credentials file path (set via environment variable)
app.config["GOOGLE_CREDS_FILE"] = os.environ.get("GOOGLE_CREDS_FILE", "credentials.json")
app.config["GOOGLE_SHEET_NAME"] = os.environ.get("GOOGLE_SHEET_NAME", "HealthScreening")

# ── Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the registration form."""
    return render_template("registration.html")


@app.route("/api/save", methods=["POST"])
def save_patient():
    """
    Save patient data:
    1. Generate label PDF (8 labels)
    2. Append row to Google Sheet
    Returns the label PDF for printing.
    """
    data = request.get_json()

    # Validate required fields
    required = ["name", "passport_number", "sex", "dob", "nationality"]
    missing = [f for f in required if not data.get(f, "").strip()]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    # ── 1(c): Append to Google Sheet ──────────────────────────────────────
    try:
        sheet_row = {
            "date": datetime.now().strftime("%d/%m/%Y"),
            "name": data["name"],
            "passport_number": data["passport_number"],
            "sex": data["sex"],
            "dob": data["dob"],
            "nationality": data["nationality"],
            "test_to_order": data.get("test_to_order", ""),
            "doctor_name": data.get("doctor_name", ""),
            "doctor_mcr": data.get("doctor_mcr", ""),
            "corporate_name": data.get("corporate_name", ""),
            "clinic_hci": data.get("clinic_hci", ""),
        }
        append_patient_to_sheet(
            sheet_row,
            creds_file=app.config["GOOGLE_CREDS_FILE"],
            sheet_name=app.config["GOOGLE_SHEET_NAME"],
        )
        sheets_ok = True
    except Exception as e:
        # Don't block label printing if Sheets fails
        print(f"[WARN] Google Sheets error: {e}")
        sheets_ok = False

    # ── 1(b): Generate label PDF ──────────────────────────────────────────
    pdf_bytes = generate_labels_pdf(data)

    # Return PDF as downloadable file (browser will auto-print via JS)
    from io import BytesIO
    pdf_buffer = BytesIO(pdf_bytes)
    pdf_buffer.seek(0)

    response = send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=False,
        download_name="labels.pdf",
    )
    # Add header to tell frontend if sheets succeeded
    response.headers["X-Sheets-Status"] = "ok" if sheets_ok else "error"
    return response


@app.route("/station2")
def station2():
    return render_template("station2.html")


@app.route("/api/station2/save", methods=["POST"])
def station2_save():
    """Update Height and Weight for a patient in Google Sheet."""
    data = request.get_json()
    passport = data.get("passport_number", "").strip()
    if not passport:
        return jsonify({"error": "No passport number provided"}), 400

    updates = {}
    if data.get("height"):
        updates["Height"] = data["height"]
    if data.get("weight"):
        updates["Weight"] = data["weight"]

    if not updates:
        return jsonify({"error": "No measurements provided"}), 400

    try:
        found = update_patient_in_sheet(
            passport,
            updates,
            creds_file=app.config["GOOGLE_CREDS_FILE"],
            sheet_name=app.config["GOOGLE_SHEET_NAME"],
        )
        if not found:
            return jsonify({"error": f"Patient '{passport}' not found in sheet. Register first at Station 1."}), 404
        return jsonify({"status": "ok"})
    except Exception as e:
        print(f"[ERROR] Station 2 save: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/mrz", methods=["POST"])
def receive_mrz():
    """
    Receive parsed MRZ data from the local watcher script.
    Returns the parsed fields as JSON.
    """
    data = request.get_json()
    # The local MRZ watcher sends parsed passport data here
    return jsonify({"status": "ok", "data": data})


# ── Run ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
