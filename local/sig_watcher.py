"""
Signature Folder Watcher + PDF Form Filler (runs locally on the clinic PC)

Watches a folder for new signature images (from Huion 420 tablet).
When a new signature is detected:
1. Inserts the signature into the MOM WPCM medical form PDF
2. Inserts the signature into the pregnancy declaration document
3. Saves the completed PDFs to an output folder

USAGE:
    python sig_watcher.py

CONFIGURATION:
    Edit the settings below or set environment variables.
"""

import os
import sys
import time
import json
import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

try:
    import fitz  # PyMuPDF
except ImportError:
    print("ERROR: PyMuPDF is required. Install with: pip install PyMuPDF")
    sys.exit(1)

# ── Settings ───────────────────────────────────────────────────────────────
# Folder where the Huion tablet saves signature images
SIG_WATCH_FOLDER = os.environ.get("SIG_WATCH_FOLDER", r"C:\Signatures")

# Output folder for completed PDFs
OUTPUT_FOLDER = os.environ.get("SIG_OUTPUT_FOLDER", r"C:\CompletedForms")

# Template PDF files (the blank forms)
MOM_FORM_TEMPLATE = os.environ.get("MOM_FORM_TEMPLATE", r"C:\Templates\WPCM_form.pdf")
PREGNANCY_DECL_TEMPLATE = os.environ.get("PREGNANCY_DECL_TEMPLATE", r"C:\Templates\pregnancy_declaration.pdf")

# URL of the local Station 1 app (local_app.py)
LOCAL_APP_URL = os.environ.get("LOCAL_APP_URL", "http://localhost:5001")

# ── Signature position on the MOM WPCM form ───────────────────────────────
# These are approximate coordinates (x, y, width, height) in points
# for the "Signature of Foreign Worker" box on the MOM form.
# You may need to adjust these based on your exact PDF template.
# Page 1, near "Signature of Foreign Worker" field
MOM_SIG_RECT = fitz.Rect(72, 458, 300, 498)  # (x0, y0, x1, y1) in points
MOM_SIG_PAGE = 0  # First page (0-indexed)

# Pregnancy declaration signature position
PREG_SIG_RECT = fitz.Rect(72, 600, 300, 640)
PREG_SIG_PAGE = 0


def get_current_patient_data():
    """Fetch the current patient data from the local Station 1 app."""
    try:
        resp = requests.get(f"{LOCAL_APP_URL}/api/state", timeout=3)
        resp.raise_for_status()
        patient = resp.json().get("patient") or {}
        if not patient:
            print(f"[SIG] Warning: No patient in local app — proceeding with empty data")
        return patient
    except Exception as e:
        print(f"[SIG] Warning: Could not reach local app ({e}) — proceeding with empty data")
        return {}


def send_signature_preview(sig_image_path):
    """Push the signature image to the local app so the browser tab shows a preview."""
    try:
        with open(sig_image_path, "rb") as f:
            resp = requests.post(
                f"{LOCAL_APP_URL}/api/signature",
                files={"file": (os.path.basename(sig_image_path), f)},
                timeout=5,
            )
        resp.raise_for_status()
        print(f"[SIG] Signature preview sent to local app")
    except Exception as e:
        print(f"[SIG] Warning: Could not send preview to local app ({e})")


def fill_mom_form(sig_image_path, patient_data, output_path):
    """
    Fill the MOM WPCM medical examination form with:
    - Patient details (Part I)
    - Patient signature

    patient_data should contain:
        name, passport_number, sex, dob, nationality, clinic_hci,
        doctor_name, height, weight, systolic_bp, diastolic_bp, etc.
    """
    if not os.path.exists(MOM_FORM_TEMPLATE):
        print(f"[SIG] ERROR: MOM form template not found: {MOM_FORM_TEMPLATE}")
        return False

    doc = fitz.open(MOM_FORM_TEMPLATE)
    page = doc[MOM_SIG_PAGE]

    # ── Insert signature image ────────────────────────────────────────────
    if os.path.exists(sig_image_path):
        page.insert_image(MOM_SIG_RECT, filename=sig_image_path)
        print(f"[SIG] Signature inserted into MOM form")

    # ── Fill text fields (Part I) ─────────────────────────────────────────
    # These positions are approximate for the standard WPCM 015 form.
    # Adjust coordinates if your template differs.
    text_insertions = []

    if patient_data.get("name"):
        text_insertions.append({
            "pos": fitz.Point(120, 85),  # Name field
            "text": patient_data["name"],
            "fontsize": 10,
        })
    if patient_data.get("passport_number"):
        text_insertions.append({
            "pos": fitz.Point(370, 85),  # Travel Document No.
            "text": patient_data["passport_number"],
            "fontsize": 10,
        })
    if patient_data.get("sex"):
        text_insertions.append({
            "pos": fitz.Point(500, 85),  # Sex
            "text": patient_data["sex"],
            "fontsize": 10,
        })
    if patient_data.get("dob"):
        text_insertions.append({
            "pos": fitz.Point(200, 100),  # Date of Birth
            "text": patient_data["dob"],
            "fontsize": 10,
        })
    if patient_data.get("nationality"):
        text_insertions.append({
            "pos": fitz.Point(370, 100),  # Nationality
            "text": patient_data["nationality"],
            "fontsize": 10,
        })
    if patient_data.get("height"):
        text_insertions.append({
            "pos": fitz.Point(530, 85),  # Height
            "text": str(patient_data["height"]),
            "fontsize": 10,
        })
    if patient_data.get("weight"):
        text_insertions.append({
            "pos": fitz.Point(530, 100),  # Weight
            "text": str(patient_data["weight"]),
            "fontsize": 10,
        })

    for item in text_insertions:
        page.insert_text(
            item["pos"],
            item["text"],
            fontsize=item["fontsize"],
            fontname="helv",
        )

    # ── Add date next to signature ────────────────────────────────────────
    from datetime import datetime
    today = datetime.now().strftime("%d/%m/%Y")
    page.insert_text(
        fitz.Point(MOM_SIG_RECT.x1 + 50, MOM_SIG_RECT.y1 - 10),
        today,
        fontsize=10,
        fontname="helv",
    )

    doc.save(output_path)
    doc.close()
    print(f"[SIG] MOM form saved: {output_path}")
    return True


def fill_pregnancy_declaration(sig_image_path, patient_data, output_path):
    """
    Fill the pregnancy declaration document with patient signature.
    This is a simple one-paragraph declaration that the patient is not pregnant.
    """
    if not os.path.exists(PREGNANCY_DECL_TEMPLATE):
        # If no template exists, generate a simple declaration
        print(f"[SIG] Pregnancy declaration template not found, generating one...")
        _generate_pregnancy_declaration(sig_image_path, patient_data, output_path)
        return True

    doc = fitz.open(PREGNANCY_DECL_TEMPLATE)
    page = doc[PREG_SIG_PAGE]

    # Insert signature
    if os.path.exists(sig_image_path):
        page.insert_image(PREG_SIG_RECT, filename=sig_image_path)

    # Insert patient name if there's a name field
    if patient_data.get("name"):
        page.insert_text(
            fitz.Point(150, PREG_SIG_RECT.y0 - 20),
            patient_data["name"],
            fontsize=10,
            fontname="helv",
        )

    from datetime import datetime
    today = datetime.now().strftime("%d/%m/%Y")
    page.insert_text(
        fitz.Point(PREG_SIG_RECT.x1 + 50, PREG_SIG_RECT.y1 - 10),
        today,
        fontsize=10,
        fontname="helv",
    )

    doc.save(output_path)
    doc.close()
    print(f"[SIG] Pregnancy declaration saved: {output_path}")
    return True


def _generate_pregnancy_declaration(sig_image_path, patient_data, output_path):
    """Generate a simple pregnancy declaration PDF from scratch."""
    doc = fitz.open()
    page = doc.new_page()

    name = patient_data.get("name", "_______________")
    passport = patient_data.get("passport_number", "_______________")

    from datetime import datetime
    today = datetime.now().strftime("%d/%m/%Y")

    # Title
    page.insert_text(fitz.Point(72, 100), "DECLARATION", fontsize=16, fontname="helv")

    # Body
    declaration_text = (
        f"I, {name} (Passport No: {passport}), hereby declare that "
        f"I am NOT pregnant at the time of this medical examination.\n\n"
        f"I understand that if I am found to be pregnant, the medical examination "
        f"results may be affected and I may need to be re-examined.\n\n"
        f"Date: {today}"
    )

    text_rect = fitz.Rect(72, 140, 540, 400)
    page.insert_textbox(text_rect, declaration_text, fontsize=12, fontname="helv")

    # Signature line
    page.insert_text(fitz.Point(72, 440), "Signature:", fontsize=12, fontname="helv")
    page.draw_line(fitz.Point(150, 442), fitz.Point(350, 442))

    # Insert signature image
    if os.path.exists(sig_image_path):
        sig_rect = fitz.Rect(150, 410, 350, 450)
        page.insert_image(sig_rect, filename=sig_image_path)

    # Name line
    page.insert_text(fitz.Point(72, 470), f"Name: {name}", fontsize=12, fontname="helv")

    doc.save(output_path)
    doc.close()
    print(f"[SIG] Generated pregnancy declaration: {output_path}")


# ── File Watcher ───────────────────────────────────────────────────────────

class SignatureFileHandler(FileSystemEventHandler):
    """Watch for new signature image files."""

    SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".bmp", ".tiff")

    def on_created(self, event):
        if event.is_directory:
            return
        if not event.src_path.lower().endswith(self.SUPPORTED_EXTENSIONS):
            return

        print(f"\n[SIG] New signature detected: {event.src_path}")

        # Wait for file to be fully written
        time.sleep(1)

        # Push image to local app for browser preview
        send_signature_preview(event.src_path)

        # Get current patient data from local app
        patient_data = get_current_patient_data()
        patient_name = patient_data.get("name", "Unknown")
        patient_passport = patient_data.get("passport_number", "Unknown")

        print(f"[SIG] Processing for patient: {patient_name} ({patient_passport})")

        # Create output folder if needed
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

        # Generate safe filename
        safe_name = "".join(c if c.isalnum() else "_" for c in patient_name)
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        # Fill MOM form
        mom_output = os.path.join(OUTPUT_FOLDER, f"MOM_Form_{safe_name}_{timestamp}.pdf")
        fill_mom_form(event.src_path, patient_data, mom_output)

        # Fill pregnancy declaration (only if patient is female)
        if patient_data.get("sex", "").upper() == "F":
            preg_output = os.path.join(OUTPUT_FOLDER, f"PregnancyDecl_{safe_name}_{timestamp}.pdf")
            fill_pregnancy_declaration(event.src_path, patient_data, preg_output)
        else:
            print(f"[SIG] Patient is male - skipping pregnancy declaration")

        print(f"[SIG] Done processing signature for {patient_name}")


def main():
    # Create folders if they don't exist
    os.makedirs(SIG_WATCH_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    print(f"[SIG] Watching folder: {SIG_WATCH_FOLDER}")
    print(f"[SIG] Output folder:   {OUTPUT_FOLDER}")
    print(f"[SIG] MOM form:        {MOM_FORM_TEMPLATE}")
    print(f"[SIG] Local app:       {LOCAL_APP_URL}")
    print(f"[SIG] Waiting for signatures...")
    print(f"[SIG] Press Ctrl+C to stop.\n")

    observer = Observer()
    observer.schedule(SignatureFileHandler(), SIG_WATCH_FOLDER, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SIG] Stopping watcher...")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
