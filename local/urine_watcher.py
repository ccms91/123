"""
Station 3(a) - Urine Dipstick Analyser  (runs locally on the clinic PC)

Watches a folder for new images captured by the camera inside the urine-test
box.  When a new image appears the script:
  1. Reads the QR code → gets patient name + passport number
  2. Looks up the patient in Google Sheets → gets sex and row number
  3. Analyses the dipstick colour pads vs the reference strip in the image:
       - All patients : Protein pad, Glucose/Sugar pad  (standard dipstick)
       - Females only : Pregnancy test strip             (lateral-flow assay)
  4. Writes the results into the patient's Google Sheet row:
       Urine Protein  →  "-"  |  "+"  |  "??"
       Urine Sugar    →  "-"  |  "+"  |  "??"
       Urine Pregnancy→  "-"  |  "+"  |  "??"   (empty for males)

REQUIREMENTS  (install on clinic PC):
    pip install opencv-python pyzbar watchdog gspread google-auth numpy

USAGE:
    python urine_watcher.py

CONFIGURATION — set environment variables or edit the SETTINGS section below.

──────────────────────────────────────────────────────────────────────────────
BOX / CAMERA CALIBRATION
──────────────────────────────────────────────────────────────────────────────
The script needs to know where each strip appears in the camera image.
All coordinates are in pixels, measured from the top-left of the image (0, 0).

After setting up the box:
  1. Place a sample image in the watch folder (won't be processed yet)
  2. Run:  python urine_watcher.py --calibrate <path_to_image>
     This opens the image in a window so you can hover over strips and read
     pixel coordinates from the title bar, then set them below.

Default values assume a ~800×600 image with the following layout (top-down):
   ┌────────────────────────────────────────┐
   │  [QR code on zip-lock bag]             │
   │                                        │
   │  [Ref strip]   [Pat strip 1]           │
   │                [Pat strip 2 (female)]  │
   │                [Pregnancy strip]       │
   └────────────────────────────────────────┘
──────────────────────────────────────────────────────────────────────────────
"""

import os
import sys
import time
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime

import cv2
import numpy as np
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import gspread
from google.oauth2.service_account import Credentials

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("urine_watcher")

# ══════════════════════════════════════════════════════════════════════════════
# SETTINGS  — override via environment variables
# ══════════════════════════════════════════════════════════════════════════════

WATCH_FOLDER = os.environ.get("URINE_WATCH_FOLDER", r"C:\UrineCamImages")
LOG_FOLDER   = os.environ.get("URINE_LOG_FOLDER",   WATCH_FOLDER)
CREDS_FILE   = os.environ.get("GOOGLE_CREDS_FILE",  "credentials.json")
SHEET_NAME   = os.environ.get("GOOGLE_SHEET_NAME",  "HealthScreening")

# ── Reference strip ROI (unused/fresh strip — always negative) ─────────────
# (x, y) = top-left corner; w = width; h = height  (all in pixels)
REF_X = int(os.environ.get("REF_STRIP_X", 60))
REF_Y = int(os.environ.get("REF_STRIP_Y", 200))
REF_W = int(os.environ.get("REF_STRIP_W", 22))
REF_H = int(os.environ.get("REF_STRIP_H", 220))

# ── Patient dipstick ROI (first / only strip) ──────────────────────────────
PAT_X   = int(os.environ.get("PAT_STRIP_X",   120))
PAT_Y   = int(os.environ.get("PAT_STRIP_Y",   200))
PAT_W   = int(os.environ.get("PAT_STRIP_W",    22))
PAT_H   = int(os.environ.get("PAT_STRIP_H",   220))
# For females, a second dipstick strip sits PAT_GAP px to the right of the first
PAT_GAP = int(os.environ.get("PAT_STRIP_GAP",  30))

# ── Pad positions within a strip (% of strip height from the top) ──────────
# Standard multi-pad dipstick pad layout (Combur / Multistix style):
#   adjust percentages to match the specific brand used at your clinic.
GLUCOSE_PCT = float(os.environ.get("GLUCOSE_PAD_PCT", 0.20))   # sugar pad
PROTEIN_PCT = float(os.environ.get("PROTEIN_PAD_PCT", 0.35))   # protein pad
PAD_RADIUS  = int(os.environ.get("PAD_SAMPLE_RADIUS",   8))    # sampling circle radius

# ── Pregnancy strip ROI  (lateral-flow assay — separate from dipstick) ─────
PREG_X     = int(os.environ.get("PREG_STRIP_X",      200))
PREG_Y     = int(os.environ.get("PREG_STRIP_Y",      200))
PREG_W     = int(os.environ.get("PREG_STRIP_W",       16))
PREG_H     = int(os.environ.get("PREG_STRIP_H",      130))
PREG_C_PCT = float(os.environ.get("PREG_C_BAND_PCT",  0.72))   # control band position
PREG_T_PCT = float(os.environ.get("PREG_T_BAND_PCT",  0.38))   # test band position

# ── Colour-comparison thresholds (CIE Delta-E units) ──────────────────────
# Delta-E < NEGATIVE_DE  → pad colour matches reference (negative result)
# Delta-E > POSITIVE_DE  → clearly different from reference (positive result)
# In between            → uncertain ("??")
NEGATIVE_DE = float(os.environ.get("NEGATIVE_DELTA_E", 15))
POSITIVE_DE = float(os.environ.get("POSITIVE_DELTA_E", 30))

# ── Pregnancy band detection ───────────────────────────────────────────────
# A band is "present" when the mean pixel intensity inside the band window
# falls below this threshold (dark line on white strip).
BAND_DARK_THRESHOLD = int(os.environ.get("BAND_DARK_THRESHOLD", 160))

# ── Processing delay ───────────────────────────────────────────────────────
FILE_SETTLE_SECS = float(os.environ.get("FILE_SETTLE_SECS", 1.5))

# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE SHEETS
# ══════════════════════════════════════════════════════════════════════════════

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_sheets_client():
    creds_json = os.environ.get("GOOGLE_CREDS_JSON")
    if creds_json:
        info = json.loads(creds_json)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def get_patient_row(passport):
    """
    Return (row_index, patient_dict) for the given passport number, or None.
    row_index is 1-based (gspread convention).
    """
    client = _get_sheets_client()
    sheet = client.open(SHEET_NAME).sheet1
    all_values = sheet.get_all_values()
    if not all_values:
        return None

    headers = all_values[0]
    try:
        passport_col = headers.index("Passport No.")
    except ValueError:
        log.error("Sheet is missing 'Passport No.' header.")
        return None

    for i, row in enumerate(all_values[1:], start=2):
        if len(row) > passport_col and row[passport_col].strip().upper() == passport.strip().upper():
            return i, dict(zip(headers, row))

    return None


def write_urine_results(row_index, protein, sugar, pregnancy=None):
    """Update Urine Protein, Urine Sugar (and optionally Urine Pregnancy) cells."""
    client = _get_sheets_client()
    sheet = client.open(SHEET_NAME).sheet1
    headers = sheet.row_values(1)

    def update_col(col_name, value):
        try:
            col_idx = headers.index(col_name) + 1   # gspread is 1-indexed
            sheet.update_cell(row_index, col_idx, value)
        except ValueError:
            log.warning("Column '%s' not found in sheet — skipping.", col_name)

    update_col("Urine Protein", protein)
    update_col("Urine Sugar",   sugar)
    if pregnancy is not None:
        update_col("Urine Pregnancy", pregnancy)


# ══════════════════════════════════════════════════════════════════════════════
# IMAGE ANALYSIS HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def read_qr(image_bgr):
    """Decode the first QR code found in the image. Returns the string or None."""
    detector = cv2.QRCodeDetector()
    data, _, _ = detector.detectAndDecode(image_bgr)
    if data:
        return data
    # Try grayscale + mild sharpen if colour scan failed
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharpened = cv2.filter2D(gray, -1, kernel)
    data, _, _ = detector.detectAndDecode(sharpened)
    return data if data else None


def sample_lab_colour(image_bgr, cx, cy, radius):
    """
    Sample the dominant colour in a circle of the given radius around (cx, cy).
    Returns a 3-element array in CIE LAB colour space.
    """
    h, w = image_bgr.shape[:2]
    # Build a circular mask
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(mask, (cx, cy), radius, 255, -1)
    # Crop to bounding box for efficiency
    x1 = max(0, cx - radius)
    y1 = max(0, cy - radius)
    x2 = min(w, cx + radius)
    y2 = min(h, cy + radius)
    roi    = image_bgr[y1:y2, x1:x2]
    mask_c = mask[y1:y2, x1:x2]
    if roi.size == 0 or mask_c.sum() == 0:
        return np.array([50.0, 0.0, 0.0])   # neutral grey fallback
    # Convert to LAB
    roi_lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB).astype(np.float32)
    pixels  = roi_lab[mask_c == 255]
    return pixels.mean(axis=0)


def delta_e(lab1, lab2):
    """
    CIE76 colour difference between two LAB triplets.
    Simple Euclidean distance in LAB space — good enough for controlled lighting.
    """
    return float(np.linalg.norm(lab1 - lab2))


def classify(de_value):
    """Map a Delta-E value to a result string."""
    if de_value < NEGATIVE_DE:
        return "-"
    if de_value > POSITIVE_DE:
        return "+"
    return "??"


def pad_centre(strip_x, strip_y, strip_h, pad_pct):
    """Return the (cx, cy) pixel coordinate of a pad inside a strip ROI."""
    cx = strip_x + PAD_RADIUS + 1          # horizontally centred in the strip
    cy = strip_y + int(strip_h * pad_pct)
    return cx, cy


def analyse_dipstick(image_bgr, strip_x, strip_y):
    """
    Analyse one dipstick strip at the given ROI origin, comparing to the
    reference strip.  Returns (protein_result, sugar_result).
    """
    # Reference pad centres
    ref_glucose_c = pad_centre(REF_X, REF_Y, REF_H, GLUCOSE_PCT)
    ref_protein_c = pad_centre(REF_X, REF_Y, REF_H, PROTEIN_PCT)

    # Patient pad centres
    pat_glucose_c = pad_centre(strip_x, strip_y, PAT_H, GLUCOSE_PCT)
    pat_protein_c = pad_centre(strip_x, strip_y, PAT_H, PROTEIN_PCT)

    # Sample colours
    ref_glu  = sample_lab_colour(image_bgr, *ref_glucose_c, PAD_RADIUS)
    ref_prot = sample_lab_colour(image_bgr, *ref_protein_c, PAD_RADIUS)
    pat_glu  = sample_lab_colour(image_bgr, *pat_glucose_c, PAD_RADIUS)
    pat_prot = sample_lab_colour(image_bgr, *pat_protein_c, PAD_RADIUS)

    de_glu  = delta_e(pat_glu,  ref_glu)
    de_prot = delta_e(pat_prot, ref_prot)

    sugar   = classify(de_glu)
    protein = classify(de_prot)

    log.info("  Glucose  ΔE=%.1f → %s", de_glu,  sugar)
    log.info("  Protein  ΔE=%.1f → %s", de_prot, protein)

    return protein, sugar


def analyse_pregnancy_strip(image_bgr):
    """
    Detect whether the pregnancy (hCG) lateral-flow strip shows 1 or 2 bands.

    Strategy:
      - Convert the strip ROI to grayscale.
      - Check pixel intensity at the C (control) and T (test) band positions.
      - A band is dark (line printed on white backing).
      - C band must always be present (strip validity check).
    Returns "+" / "-" / "??"
    """
    h_img, w_img = image_bgr.shape[:2]

    x1 = max(0, PREG_X)
    y1 = max(0, PREG_Y)
    x2 = min(w_img, PREG_X + PREG_W)
    y2 = min(h_img, PREG_Y + PREG_H)

    roi = image_bgr[y1:y2, x1:x2]
    if roi.size == 0:
        log.warning("  Pregnancy strip ROI is empty — returning ??")
        return "??"

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    roi_h = gray.shape[0]
    band_half = max(4, PREG_W // 3)   # sample window half-height

    def band_intensity(pct):
        cy = int(roi_h * pct)
        y1b = max(0, cy - band_half)
        y2b = min(roi_h, cy + band_half)
        strip = gray[y1b:y2b, :]
        return float(strip.mean()) if strip.size > 0 else 255.0

    c_intensity = band_intensity(PREG_C_PCT)
    t_intensity = band_intensity(PREG_T_PCT)

    c_present = c_intensity < BAND_DARK_THRESHOLD
    t_present = t_intensity < BAND_DARK_THRESHOLD

    log.info("  Pregnancy C-band intensity=%.0f (present=%s)", c_intensity, c_present)
    log.info("  Pregnancy T-band intensity=%.0f (present=%s)", t_intensity, t_present)

    if not c_present:
        log.warning("  Control band not detected — strip may be invalid → ??")
        return "??"
    return "+" if t_present else "-"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN PROCESSING
# ══════════════════════════════════════════════════════════════════════════════

def save_debug_image(image_bgr, image_path, protein, sugar, pregnancy):
    """Save an annotated copy of the image for auditing."""
    annotated = image_bgr.copy()
    label = f"Protein:{protein}  Sugar:{sugar}"
    if pregnancy:
        label += f"  Preg:{pregnancy}"
    cv2.putText(annotated, label, (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    # Draw ROI rectangles
    for (x, y, w, h, colour) in [
        (REF_X, REF_Y, REF_W, REF_H, (255, 200, 0)),
        (PAT_X, PAT_Y, PAT_W, PAT_H, (0, 200, 255)),
        (PREG_X, PREG_Y, PREG_W, PREG_H, (0, 180, 0)),
    ]:
        cv2.rectangle(annotated, (x, y), (x + w, y + h), colour, 2)

    stem = Path(image_path).stem
    ts   = datetime.now().strftime("%H%M%S")
    out  = str(Path(LOG_FOLDER) / f"debug_{stem}_{ts}.jpg")
    cv2.imwrite(out, annotated)
    log.info("  Debug image saved → %s", out)


def process_image(image_path):
    log.info("Processing: %s", image_path)
    image_bgr = cv2.imread(image_path)
    if image_bgr is None:
        log.error("  Could not read image (skipping).")
        return

    # ── 1. Read QR code ────────────────────────────────────────────────────
    qr_raw = read_qr(image_bgr)
    if not qr_raw:
        log.error("  No QR code found — skipping.")
        return

    parts = qr_raw.strip().split("|")
    if len(parts) < 2:
        log.error("  QR format not recognised ('%s') — skipping.", qr_raw)
        return

    name     = parts[0].strip()
    passport = parts[1].strip()
    log.info("  Patient: %s | %s", name, passport)

    # ── 2. Look up patient in Google Sheets ────────────────────────────────
    result = get_patient_row(passport)
    if result is None:
        log.error("  Patient '%s' not found in sheet — skipping.", passport)
        return

    row_index, patient = result
    sex = patient.get("Sex", "").strip().upper()
    is_female = sex == "F"
    log.info("  Sex: %s  →  pregnancy test: %s", sex, is_female)

    # ── 3. Analyse standard dipstick (protein + sugar) ────────────────────
    protein, sugar = analyse_dipstick(image_bgr, PAT_X, PAT_Y)

    # ── 4. Analyse pregnancy strip (females only) ─────────────────────────
    pregnancy = None
    if is_female:
        pregnancy = analyse_pregnancy_strip(image_bgr)

    log.info("  RESULTS  Protein=%s  Sugar=%s  Pregnancy=%s",
             protein, sugar, pregnancy or "N/A")

    # ── 5. Write to Google Sheets ──────────────────────────────────────────
    write_urine_results(row_index, protein, sugar, pregnancy)
    log.info("  Sheet row %d updated.", row_index)

    # ── 6. Save annotated debug image ─────────────────────────────────────
    try:
        save_debug_image(image_bgr, image_path, protein, sugar, pregnancy)
    except Exception as e:
        log.warning("  Debug image save failed: %s", e)


# ══════════════════════════════════════════════════════════════════════════════
# FILE WATCHER
# ══════════════════════════════════════════════════════════════════════════════

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}


class UrineImageHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        path = event.src_path
        if Path(path).suffix.lower() not in IMAGE_EXTENSIONS:
            return
        # Skip debug images we saved ourselves
        if Path(path).name.startswith("debug_"):
            return

        # Wait for the camera software to finish writing the file
        time.sleep(FILE_SETTLE_SECS)
        try:
            process_image(path)
        except Exception as e:
            log.exception("Unhandled error processing %s: %s", path, e)


# ══════════════════════════════════════════════════════════════════════════════
# CALIBRATION HELPER
# ══════════════════════════════════════════════════════════════════════════════

def calibrate(image_path):
    """
    Open the image in an OpenCV window.  Hover the mouse to read pixel
    coordinates from the window title bar, then close with any key.
    """
    img = cv2.imread(image_path)
    if img is None:
        print(f"Cannot open: {image_path}")
        return

    def on_mouse(event, x, y, flags, param):
        b, g, r = img[y, x] if 0 <= y < img.shape[0] and 0 <= x < img.shape[1] else (0,0,0)
        cv2.setWindowTitle("calibrate", f"x={x}  y={y}   BGR=({b},{g},{r})")

    cv2.namedWindow("calibrate", cv2.WINDOW_NORMAL)
    cv2.setMouseCallback("calibrate", on_mouse)

    # Draw current ROIs so you can see where they land
    annotated = img.copy()
    for (x, y, w, h, colour, lbl) in [
        (REF_X,  REF_Y,  REF_W,  REF_H,  (255, 200,   0), "REF"),
        (PAT_X,  PAT_Y,  PAT_W,  PAT_H,  (  0, 200, 255), "PAT"),
        (PREG_X, PREG_Y, PREG_W, PREG_H, (  0, 180,   0), "PREG"),
    ]:
        cv2.rectangle(annotated, (x, y), (x+w, y+h), colour, 2)
        cv2.putText(annotated, lbl, (x, y-5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, colour, 2)

    cv2.imshow("calibrate", annotated)
    print("\nCalibration mode — hover mouse over strips to read coordinates.")
    print("Close the window (press any key) when done, then update env vars.\n")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Urine dipstick watcher")
    parser.add_argument("--calibrate", metavar="IMAGE",
                        help="Open an image in calibration mode and exit")
    args = parser.parse_args()

    if args.calibrate:
        calibrate(args.calibrate)
        return

    os.makedirs(WATCH_FOLDER, exist_ok=True)
    os.makedirs(LOG_FOLDER,   exist_ok=True)

    log.info("Station 3(a) Urine Dipstick Watcher")
    log.info("Watching folder : %s", WATCH_FOLDER)
    log.info("Google Sheet    : %s", SHEET_NAME)
    log.info("Ref strip ROI   : x=%d y=%d w=%d h=%d", REF_X, REF_Y, REF_W, REF_H)
    log.info("Pat strip ROI   : x=%d y=%d w=%d h=%d", PAT_X, PAT_Y, PAT_W, PAT_H)
    log.info("Preg strip ROI  : x=%d y=%d w=%d h=%d", PREG_X, PREG_Y, PREG_W, PREG_H)
    log.info("Waiting for images...  (Ctrl+C to stop)\n")

    observer = Observer()
    observer.schedule(UrineImageHandler(), WATCH_FOLDER, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log.info("Stopping watcher...")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
