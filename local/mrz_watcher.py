"""
MRZ Scanner Folder Watcher  –  Station 1
=========================================
Watches a folder for new .txt files dropped by the MRZ passport scanner,
parses the two-line ICAO TD-3 MRZ, then opens the registration app in the
browser with patient details pre-filled as query parameters.

Usage:
    python local/mrz_watcher.py

Environment variables (set in .env or system):
    MRZ_WATCH_FOLDER    Folder the scanner drops .txt files into
                        Default: C:\\MRZ_Scanner\\Output  (Windows)
                                 /tmp/mrz_scanner          (Linux/Mac)
    REGISTRATION_URL    Base URL of the registration Flask app
                        Default: http://localhost:5100
    MRZ_DELETE_AFTER    Delete the .txt file after processing (true/false)
                        Default: false
"""

import os
import sys
import time
import urllib.parse
import webbrowser
from datetime import datetime

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from dotenv import load_dotenv

# ── path setup ───────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
load_dotenv(os.path.join(ROOT, ".env"))

# ── config ───────────────────────────────────────────────────────────────────
DEFAULT_FOLDER = (
    r"C:\MRZ_Scanner\Output" if sys.platform == "win32" else "/tmp/mrz_scanner"
)
WATCH_FOLDER = os.environ.get("MRZ_WATCH_FOLDER", DEFAULT_FOLDER)
APP_URL = os.environ.get("REGISTRATION_URL", "http://localhost:5100")
DELETE_AFTER = os.environ.get("MRZ_DELETE_AFTER", "false").lower() == "true"


# ── MRZ parser ────────────────────────────────────────────────────────────────

def _format_date(yymmdd: str) -> str:
    """Convert YYMMDD → DD/MM/YYYY.  Cutoff year: >= 30 → 19xx, else 20xx."""
    if len(yymmdd) != 6 or not yymmdd.isdigit():
        return yymmdd
    yy, mm, dd = int(yymmdd[:2]), yymmdd[2:4], yymmdd[4:6]
    year = 1900 + yy if yy >= 30 else 2000 + yy
    return f"{dd}/{mm}/{year}"


def _clean(s: str) -> str:
    """Replace filler '<' with spaces and strip."""
    return s.replace("<", " ").strip()


def parse_mrz(text: str) -> dict:
    """
    Parse a two-line ICAO TD-3 MRZ (passport).
    Returns a dict with keys matching the registration form fields.
    Returns an empty dict if the text doesn't look like a valid MRZ.
    """
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]

    # Allow files that contain more than 2 lines – grab the MRZ lines
    mrz_lines = [ln for ln in lines if len(ln) >= 44 and "<" in ln]
    if len(mrz_lines) < 2:
        print(f"[mrz_watcher] Could not find 2 MRZ lines in file. Lines: {lines}")
        return {}

    line1 = mrz_lines[0].ljust(44)[:44]
    line2 = mrz_lines[1].ljust(44)[:44]

    # ── Line 1: P<ISS SURNAME<<GIVEN<NAMES ────────────────────────────────
    names_raw = line1[5:44]
    # Double '<' separates surname from given names
    if "<<" in names_raw:
        surname_raw, given_raw = names_raw.split("<<", 1)
        surname = _clean(surname_raw).title()
        given_names = _clean(given_raw.replace("<", " ")).title()
    else:
        surname = _clean(names_raw).title()
        given_names = ""

    full_name = f"{given_names} {surname}".strip()

    # ── Line 2 ─────────────────────────────────────────────────────────────
    passport_number = line2[0:9].replace("<", "").strip()
    nationality     = line2[10:13].replace("<", "").strip()
    dob_raw         = line2[13:19]
    gender_char     = line2[20]
    expiry_raw      = line2[21:27]

    gender_map = {"M": "Male", "F": "Female"}
    gender = gender_map.get(gender_char.upper(), "Other")

    return {
        "name":            full_name,
        "surname":         surname,
        "given_names":     given_names,
        "dob":             _format_date(dob_raw),
        "passport_number": passport_number,
        "nationality":     nationality,
        "gender":          gender,
        "expiry":          _format_date(expiry_raw),
    }


# ── watchdog handler ─────────────────────────────────────────────────────────

class MRZFileHandler(FileSystemEventHandler):

    def on_created(self, event):
        if event.is_directory:
            return
        path = event.src_path
        if not path.lower().endswith(".txt"):
            return

        print(f"[mrz_watcher] New file detected: {path}")
        time.sleep(0.6)   # wait for scanner to finish writing

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except OSError as exc:
            print(f"[mrz_watcher] Cannot read file: {exc}")
            return

        data = parse_mrz(content)
        if not data.get("passport_number"):
            print("[mrz_watcher] MRZ parse failed or empty passport number – skipping.")
            return

        params = urllib.parse.urlencode(
            {k: v for k, v in data.items() if v}, quote_via=urllib.parse.quote
        )
        url = f"{APP_URL}/register?{params}"
        print(f"[mrz_watcher] Opening browser: {url}")
        webbrowser.open(url)

        if DELETE_AFTER:
            try:
                os.remove(path)
                print(f"[mrz_watcher] Deleted: {path}")
            except OSError as exc:
                print(f"[mrz_watcher] Could not delete file: {exc}")


# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs(WATCH_FOLDER, exist_ok=True)
    print(f"[mrz_watcher] Watching:  {WATCH_FOLDER}")
    print(f"[mrz_watcher] App URL:   {APP_URL}")
    print(f"[mrz_watcher] Started at {datetime.now().strftime('%H:%M:%S')}. Press Ctrl+C to stop.\n")

    observer = Observer()
    observer.schedule(MRZFileHandler(), WATCH_FOLDER, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        print("\n[mrz_watcher] Stopped.")
