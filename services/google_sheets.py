"""Google Sheets integration for health screening registrations."""

import os
import sys

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

SHEET_HEADERS = [
    "Timestamp",
    "Visit Date",
    "Full Name",
    "Surname",
    "Given Names",
    "Date of Birth",
    "Gender",
    "Passport Number",
    "Nationality",
    "Passport Expiry",
    "Corporation",
    "Tests Required",
    "Vaccine Required",
    "Doctor Name",
    "Doctor MCR",
    "Signed",
]


def _get_worksheet() -> gspread.Worksheet:
    creds_path = os.environ.get("GOOGLE_CREDENTIALS_JSON", "credentials.json")
    spreadsheet_id = os.environ.get("GOOGLE_SPREADSHEET_ID", "")
    sheet_name = os.environ.get("GOOGLE_SHEET_NAME", "Registrations")

    if not spreadsheet_id:
        raise ValueError(
            "GOOGLE_SPREADSHEET_ID not set in environment / .env file."
        )
    if not os.path.exists(creds_path):
        raise FileNotFoundError(
            f"Google credentials file not found: {creds_path}. "
            "Set GOOGLE_CREDENTIALS_JSON in your .env file."
        )

    creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(spreadsheet_id)

    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(
            title=sheet_name, rows=2000, cols=len(SHEET_HEADERS)
        )
        worksheet.append_row(SHEET_HEADERS)

    return worksheet


def append_registration(data: dict) -> None:
    """Append one patient registration row to the Google Sheet."""
    worksheet = _get_worksheet()
    row = [
        data.get("timestamp", ""),
        data.get("visit_date", ""),
        data.get("name", ""),
        data.get("surname", ""),
        data.get("given_names", ""),
        data.get("dob", ""),
        data.get("gender", ""),
        data.get("passport_number", ""),
        data.get("nationality", ""),
        data.get("expiry", ""),
        data.get("corporation", ""),
        data.get("tests_required", ""),
        data.get("vaccine_required", ""),
        data.get("doctor_name", ""),
        data.get("doctor_mcr", ""),
        data.get("signed", "No"),
    ]
    worksheet.append_row(row, value_input_option="USER_ENTERED")
