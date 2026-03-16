"""
Google Sheets Integration
Appends patient data as a new row to the configured Google Sheet.
"""

import os
import json
import gspread
from google.oauth2.service_account import Credentials


# Google Sheets API scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Column headers for the sheet (will be created if sheet is empty)
HEADERS = [
    "Date",
    "Name",
    "Passport No.",
    "Sex",
    "Date of Birth",
    "Nationality",
    "Test to be Ordered",
    "Doctor Name",
    "Doctor MCR",
    "Corporate Name",
    "Clinic HCI",
    # ── Fields populated at other stations ──
    "Height",
    "Weight",
    "Systolic BP",
    "Diastolic BP",
    "Vision Acuity",
    "Vaccine Type",
    "Vaccine Brand",
    "Vaccine Dose",
]


def _get_client(creds_file):
    """Authenticate and return a gspread client."""
    # Support credentials as a file path OR as a JSON string in env var
    creds_json = os.environ.get("GOOGLE_CREDS_JSON")
    if creds_json:
        info = json.loads(creds_json)
        credentials = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        credentials = Credentials.from_service_account_file(creds_file, scopes=SCOPES)

    return gspread.authorize(credentials)


def update_patient_in_sheet(passport_number, updates, creds_file="credentials.json", sheet_name="HealthScreening"):
    """
    Find the row for the given passport number and update specific columns.

    updates is a dict of {column_header: value}, e.g.:
        {"Height": "170", "Weight": "65"}

    Returns True if found and updated, False if patient not found.
    """
    client = _get_client(creds_file)
    sheet = client.open(sheet_name).sheet1

    all_values = sheet.get_all_values()
    if not all_values:
        return False

    headers = all_values[0]  # First row is headers

    # Find the passport column index
    try:
        passport_col = headers.index("Passport No.")
    except ValueError:
        raise ValueError("Sheet is missing 'Passport No.' header. Check the sheet.")

    # Find the patient's row (1-indexed for gspread, +1 for header row)
    row_index = None
    for i, row in enumerate(all_values[1:], start=2):
        if len(row) > passport_col and row[passport_col].strip().upper() == passport_number.strip().upper():
            row_index = i
            break

    if row_index is None:
        return False

    # Update each requested column
    for col_name, value in updates.items():
        try:
            col_index = headers.index(col_name) + 1  # gspread is 1-indexed
            sheet.update_cell(row_index, col_index, value)
        except ValueError:
            print(f"[WARN] Column '{col_name}' not found in sheet headers")

    return True


def append_patient_to_sheet(patient_data, creds_file="credentials.json", sheet_name="HealthScreening"):
    """
    Append a patient row to the Google Sheet.

    patient_data dict keys:
        date, name, passport_number, sex, dob, nationality,
        test_to_order, doctor_name, doctor_mcr, corporate_name, clinic_hci
    """
    client = _get_client(creds_file)
    sheet = client.open(sheet_name).sheet1

    # If the sheet is empty, add headers first
    existing = sheet.get_all_values()
    if not existing:
        sheet.append_row(HEADERS, value_input_option="RAW")

    # Format DOB from YYYY-MM-DD to DD/MM/YYYY
    dob = patient_data.get("dob", "")
    if dob and "-" in dob:
        parts = dob.split("-")
        dob = f"{parts[2]}/{parts[1]}/{parts[0]}"

    # Build the row (matching HEADERS order)
    row = [
        patient_data.get("date", ""),
        patient_data.get("name", ""),
        patient_data.get("passport_number", ""),
        patient_data.get("sex", ""),
        dob,
        patient_data.get("nationality", ""),
        patient_data.get("test_to_order", ""),
        patient_data.get("doctor_name", ""),
        patient_data.get("doctor_mcr", ""),
        patient_data.get("corporate_name", ""),
        patient_data.get("clinic_hci", ""),
        # Other station fields left empty
        "",  # Height
        "",  # Weight
        "",  # Systolic BP
        "",  # Diastolic BP
        "",  # Vision Acuity
        "",  # Vaccine Type
        "",  # Vaccine Brand
        "",  # Vaccine Dose
    ]

    sheet.append_row(row, value_input_option="RAW")
    return True
