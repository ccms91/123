"""
MRZ Folder Watcher (runs locally on the clinic PC)

Watches a folder for new .txt files created by the MRZ passport scanner.
When a new file is detected:
1. Reads and parses the passport data
2. Opens the registration web app in the browser with the data pre-filled

USAGE:
    python mrz_watcher.py

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

# ── Settings ───────────────────────────────────────────────────────────────
# Folder where the MRZ scanner saves .txt files
WATCH_FOLDER = os.environ.get("MRZ_WATCH_FOLDER", r"C:\MRZ_Scans")

# URL of the local Station 1 app (local_app.py)
LOCAL_APP_URL = os.environ.get("LOCAL_APP_URL", "http://localhost:5001")

# ── MRZ Parser ─────────────────────────────────────────────────────────────

def parse_mrz_file(filepath):
    """
    Parse a .txt file from the MRZ scanner.

    MRZ scanners typically output either:
    A) Raw MRZ lines (2 lines of 44 chars for passports)
    B) Parsed key=value pairs

    This function handles both formats.
    Returns a dict with: name, passport_number, sex, dob, nationality
    """
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read().strip()

    lines = content.splitlines()

    # Try Format B: key=value pairs (common in many MRZ scanners)
    if any("=" in line for line in lines):
        return _parse_key_value(lines)

    # Try Format A: raw MRZ lines
    mrz_lines = [l.strip() for l in lines if len(l.strip()) >= 30]
    if len(mrz_lines) >= 2:
        return _parse_raw_mrz(mrz_lines)

    # Fallback: try to extract whatever we can
    print(f"[WARN] Could not parse MRZ format in {filepath}")
    print(f"       Content: {content[:200]}")
    return None


def _parse_key_value(lines):
    """Parse key=value format."""
    data = {}
    for line in lines:
        if "=" in line:
            key, _, value = line.partition("=")
            data[key.strip().lower()] = value.strip()

    # Map common field names to our format
    name_fields = ["surname", "last_name", "family_name"]
    given_fields = ["given_name", "given_names", "first_name"]

    surname = ""
    given = ""
    for k in name_fields:
        if k in data:
            surname = data[k]
            break
    for k in given_fields:
        if k in data:
            given = data[k]
            break

    # Some scanners use "name" or "full_name"
    full_name = data.get("name", data.get("full_name", ""))
    if not surname and full_name:
        name = full_name
    else:
        name = f"{given} {surname}".strip() if given else surname

    # DOB: try common formats
    dob_raw = data.get("dob", data.get("date_of_birth", data.get("birth_date", "")))
    dob = _normalize_dob(dob_raw)

    return {
        "name": name.upper(),
        "passport_number": data.get("document_number", data.get("passport_number", data.get("doc_no", ""))).upper(),
        "sex": data.get("sex", data.get("gender", "")).upper()[:1],
        "dob": dob,
        "nationality": data.get("nationality", data.get("country", "")).upper(),
    }


def _parse_raw_mrz(mrz_lines):
    """
    Parse standard ICAO 9303 passport MRZ (2 lines, 44 chars each).

    Line 1: P<ISSUING_COUNTRY<SURNAME<<GIVEN_NAMES<<<...
    Line 2: PASSPORT_NO<CHECK<NATIONALITY<DOB<CHECK<SEX<EXPIRY<CHECK<...
    """
    line1 = mrz_lines[0].replace(" ", "").ljust(44, "<")
    line2 = mrz_lines[1].replace(" ", "").ljust(44, "<")

    # Line 1: Extract names
    name_part = line1[5:]  # Skip "P<XXX"
    parts = name_part.split("<<")
    surname = parts[0].replace("<", " ").strip()
    given = parts[1].replace("<", " ").strip() if len(parts) > 1 else ""
    full_name = f"{given} {surname}".strip()

    # Line 2: Extract fields
    passport_no = line2[0:9].replace("<", "").strip()
    nationality = line2[10:13].replace("<", "").strip()
    dob_raw = line2[13:19]  # YYMMDD
    sex = line2[20:21]

    # Convert DOB from YYMMDD to YYYY-MM-DD
    yy = int(dob_raw[0:2])
    mm = dob_raw[2:4]
    dd = dob_raw[4:6]
    # Assume 00-30 = 2000s, 31-99 = 1900s
    yyyy = 2000 + yy if yy <= 30 else 1900 + yy
    dob = f"{yyyy}-{mm}-{dd}"

    return {
        "name": full_name.upper(),
        "passport_number": passport_no.upper(),
        "sex": sex.upper(),
        "dob": dob,
        "nationality": nationality.upper(),
    }


def _normalize_dob(dob_str):
    """Try to convert various DOB formats to YYYY-MM-DD."""
    dob_str = dob_str.strip()
    if not dob_str:
        return ""

    # Already YYYY-MM-DD
    if len(dob_str) == 10 and dob_str[4] == "-":
        return dob_str

    # DD/MM/YYYY or DD-MM-YYYY
    for sep in ["/", "-", "."]:
        if sep in dob_str:
            parts = dob_str.split(sep)
            if len(parts) == 3:
                if len(parts[2]) == 4:  # DD/MM/YYYY
                    return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                elif len(parts[0]) == 4:  # YYYY/MM/DD
                    return f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"

    # DDMMYYYY
    if len(dob_str) == 8 and dob_str.isdigit():
        return f"{dob_str[4:8]}-{dob_str[2:4]}-{dob_str[0:2]}"

    return dob_str


# ── File Watcher ───────────────────────────────────────────────────────────

class MrzFileHandler(FileSystemEventHandler):
    """Watch for new .txt files and parse them."""

    def on_created(self, event):
        if event.is_directory:
            return
        if not event.src_path.lower().endswith(".txt"):
            return

        print(f"[MRZ] New file detected: {event.src_path}")

        # Small delay to ensure file is fully written
        time.sleep(0.5)

        parsed = parse_mrz_file(event.src_path)
        if parsed:
            print(f"[MRZ] Parsed: {json.dumps(parsed, indent=2)}")

            # Send to local Station 1 app — browser tab updates automatically
            try:
                resp = requests.post(
                    f"{LOCAL_APP_URL}/api/mrz",
                    json=parsed,
                    timeout=5,
                )
                resp.raise_for_status()
                print(f"[MRZ] Sent to local app at {LOCAL_APP_URL}")
            except Exception as e:
                print(f"[MRZ] ERROR: Could not reach local app ({e})")
                print(f"[MRZ]        Is local_app.py running on {LOCAL_APP_URL}?")
        else:
            print(f"[MRZ] Could not parse file. Please enter data manually.")


def main():
    # Create watch folder if it doesn't exist
    if not os.path.exists(WATCH_FOLDER):
        os.makedirs(WATCH_FOLDER)
        print(f"[MRZ] Created watch folder: {WATCH_FOLDER}")

    print(f"[MRZ] Watching folder: {WATCH_FOLDER}")
    print(f"[MRZ] Local app URL: {LOCAL_APP_URL}")
    print(f"[MRZ] Waiting for passport scans...")
    print(f"[MRZ] Press Ctrl+C to stop.\n")

    observer = Observer()
    observer.schedule(MrzFileHandler(), WATCH_FOLDER, recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[MRZ] Stopping watcher...")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
