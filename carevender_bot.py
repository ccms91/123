"""
Carevender Bot — Windows Desktop Automation
Reads patient data from Google Sheets every N minutes and submits web forms.
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import gspread
import schedule
import time
from google.oauth2.service_account import Credentials
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ---------------------------------------------------------------------------
# Nationality mapping: MRZ ISO 3166-1 alpha-3 → Carevender dropdown text
# ---------------------------------------------------------------------------
MRZ_TO_CAREVENDER = {
    "AFG": "Afghan", "ALB": "Albanian", "DZA": "Algerian", "USA": "American",
    "AND": "Andorran", "AGO": "Angolan", "ATG": "Antiguan", "ARG": "Argentinian",
    "ARM": "Armenian", "AUS": "Australian", "AUT": "Austrian", "AZE": "Azerbaijani",
    "BHS": "Bahamian", "BHR": "Bahraini", "BGD": "Bangladeshi", "BRB": "Barbadian",
    "BLR": "Belarusian", "BEL": "Belgian", "BLZ": "Belizean", "BEN": "Beninese",
    "BTN": "Bhutanese", "BOL": "Bolivian", "BIH": "Bosnian", "BWA": "Botswanan",
    "BRA": "Brazilian", "BRN": "Bruneian", "BGR": "Bulgarian", "BFA": "Burkinabe",
    "BDI": "Burundian", "CPV": "Cape Verdean", "KHM": "Cambodian", "CMR": "Cameroonian",
    "CAN": "Canadian", "CAF": "Central African", "TCD": "Chadian", "CHL": "Chilean",
    "CHN": "Chinese", "COL": "Colombian", "COM": "Comoran", "COD": "Congolese",
    "COG": "Congolese", "CRI": "Costa Rican", "HRV": "Croatian", "CUB": "Cuban",
    "CYP": "Cypriot", "CZE": "Czech", "DNK": "Danish", "DJI": "Djiboutian",
    "DOM": "Dominican", "ECU": "Ecuadorian", "EGY": "Egyptian", "SLV": "Salvadoran",
    "GNQ": "Equatorial Guinean", "ERI": "Eritrean", "EST": "Estonian", "SWZ": "Swazi",
    "ETH": "Ethiopian", "FJI": "Fijian", "FIN": "Finnish", "FRA": "French",
    "GAB": "Gabonese", "GMB": "Gambian", "GEO": "Georgian", "DEU": "German",
    "GHA": "Ghanaian", "GRC": "Greek", "GRD": "Grenadian", "GTM": "Guatemalan",
    "GIN": "Guinean", "GNB": "Guinea-Bissauan", "GUY": "Guyanese", "HTI": "Haitian",
    "HND": "Honduran", "HUN": "Hungarian", "ISL": "Icelandic", "IND": "Indian",
    "IDN": "Indonesian", "IRN": "Iranian", "IRQ": "Iraqi", "IRL": "Irish",
    "ISR": "Israeli", "ITA": "Italian", "JAM": "Jamaican", "JPN": "Japanese",
    "JOR": "Jordanian", "KAZ": "Kazakhstani", "KEN": "Kenyan", "KIR": "Kiribatian",
    "PRK": "North Korean", "KOR": "South Korean", "XKX": "Kosovar", "KWT": "Kuwaiti",
    "KGZ": "Kyrgyzstani", "LAO": "Laotian", "LVA": "Latvian", "LBN": "Lebanese",
    "LSO": "Basotho", "LBR": "Liberian", "LBY": "Libyan", "LIE": "Liechtensteiner",
    "LTU": "Lithuanian", "LUX": "Luxembourger", "MDG": "Malagasy", "MWI": "Malawian",
    "MYS": "Malaysian", "MDV": "Maldivian", "MLI": "Malian", "MLT": "Maltese",
    "MHL": "Marshallese", "MRT": "Mauritanian", "MUS": "Mauritian", "MEX": "Mexican",
    "FSM": "Micronesian", "MDA": "Moldovan", "MCO": "Monegasque", "MNG": "Mongolian",
    "MNE": "Montenegrin", "MAR": "Moroccan", "MOZ": "Mozambican", "MMR": "Myanmar",
    "NAM": "Namibian", "NRU": "Nauruan", "NPL": "Nepalese", "NLD": "Dutch",
    "NZL": "New Zealander", "NIC": "Nicaraguan", "NER": "Nigerien", "NGA": "Nigerian",
    "MKD": "Macedonian", "NOR": "Norwegian", "OMN": "Omani", "PAK": "Pakistani",
    "PLW": "Palauan", "PAN": "Panamanian", "PNG": "Papua New Guinean", "PRY": "Paraguayan",
    "PER": "Peruvian", "PHL": "Filipino", "POL": "Polish", "PRT": "Portuguese",
    "QAT": "Qatari", "ROU": "Romanian", "RUS": "Russian", "RWA": "Rwandan",
    "KNA": "Kittitian", "LCA": "Saint Lucian", "VCT": "Vincentian", "WSM": "Samoan",
    "SMR": "Sammarinese", "STP": "Sao Tomean", "SAU": "Saudi Arabian", "SEN": "Senegalese",
    "SRB": "Serbian", "SYC": "Seychellois", "SLE": "Sierra Leonean", "SGP": "Singapore Citizen",
    "SVK": "Slovak", "SVN": "Slovenian", "SLB": "Solomon Islander", "SOM": "Somali",
    "ZAF": "South African", "SSD": "South Sudanese", "ESP": "Spanish", "LKA": "Sri Lankan",
    "SDN": "Sudanese", "SUR": "Surinamese", "SWE": "Swedish", "CHE": "Swiss",
    "SYR": "Syrian", "TWN": "Taiwanese", "TJK": "Tajik", "TZA": "Tanzanian",
    "THA": "Thai", "TLS": "Timorese", "TGO": "Togolese", "TON": "Tongan",
    "TTO": "Trinidadian", "TUN": "Tunisian", "TUR": "Turkish", "TKM": "Turkmen",
    "TUV": "Tuvaluan", "UGA": "Ugandan", "UKR": "Ukrainian", "ARE": "Emirati",
    "GBR": "British", "URY": "Uruguayan", "UZB": "Uzbekistani", "VUT": "Vanuatuan",
    "VEN": "Venezuelan", "VNM": "Vietnamese", "YEM": "Yemeni", "ZMB": "Zambian",
    "ZWE": "Zimbabwean",
}

# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent.resolve()
CONFIG_PATH = SCRIPT_DIR / "config.json"


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
def setup_logging() -> logging.Logger:
    logger = logging.getLogger("carevender_bot")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler
    fh = logging.FileHandler(SCRIPT_DIR / "bot.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


logger = setup_logging()

# ---------------------------------------------------------------------------
# Google Sheets helpers
# ---------------------------------------------------------------------------
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def get_worksheet(config: dict):
    creds_file = SCRIPT_DIR / config["google_credentials_file"]
    creds = Credentials.from_service_account_file(str(creds_file), scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open(config["spreadsheet_name"])
    return spreadsheet.worksheet(config["worksheet_name"])


def get_new_patients(worksheet, config: dict) -> list[dict]:
    """Return rows where Status is blank (not 'Done' and not starting with 'Error')."""
    cols = config["columns"]
    all_records = worksheet.get_all_records(expected_headers=[])

    new_patients = []
    for i, row in enumerate(all_records, start=2):  # row index 2 = first data row (1-indexed)
        status = str(row.get(cols["status"], "")).strip()
        if status == "" or (status.lower() != "done" and not status.lower().startswith("error")):
            # Only include rows that are actually blank (not already processed)
            if status == "":
                new_patients.append({"row_index": i, "data": row})
    return new_patients


def update_status(worksheet, row_index: int, status_value: str, config: dict) -> None:
    cols = config["columns"]
    # Find the column letter for the Status column
    header_row = worksheet.row_values(1)
    status_col_name = cols["status"]
    try:
        col_index = header_row.index(status_col_name) + 1  # 1-indexed
    except ValueError:
        logger.error("Status column '%s' not found in sheet headers.", status_col_name)
        return
    worksheet.update_cell(row_index, col_index, status_value)


# ---------------------------------------------------------------------------
# Nationality translation
# ---------------------------------------------------------------------------
def translate_nationality(raw: str) -> str | None:
    """Translate MRZ code or full-text nationality to Carevender dropdown label."""
    value = raw.strip().upper()
    if len(value) == 3:
        translated = MRZ_TO_CAREVENDER.get(value)
        if translated is None:
            logger.warning("Unknown MRZ nationality code: '%s' — leaving nationality blank.", value)
        return translated
    elif len(value) > 3:
        # Already full text — use as-is (preserve original casing from sheet)
        return raw.strip()
    return None


# ---------------------------------------------------------------------------
# Gender mapping
# ---------------------------------------------------------------------------
def map_gender(raw: str) -> str:
    v = raw.strip().lower()
    if v in ("male", "m"):
        return "Male"
    elif v in ("female", "f"):
        return "Female"
    else:
        return "Unknown"


# ---------------------------------------------------------------------------
# DOB formatting
# ---------------------------------------------------------------------------
def format_dob(raw: str) -> str:
    """Convert DDMMYYYY (8 digits) → DD/MM/YYYY."""
    raw = raw.strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[0:2]}/{raw[2:4]}/{raw[4:8]}"
    # Already formatted or unexpected — return as-is
    return raw


# ---------------------------------------------------------------------------
# Browser context management
# ---------------------------------------------------------------------------
_playwright_instance = None
_browser_context = None


def launch_browser(config: dict):
    global _playwright_instance, _browser_context
    profile_dir = config["browser_profile_dir"]
    headless = config.get("headless", False)

    _playwright_instance = sync_playwright().start()
    _browser_context = _playwright_instance.chromium.launch_persistent_context(
        user_data_dir=profile_dir,
        headless=headless,
        args=["--start-maximized"],
    )
    logger.info("Browser launched with profile: %s", profile_dir)
    return _browser_context


def close_browser() -> None:
    global _playwright_instance, _browser_context
    try:
        if _browser_context:
            _browser_context.close()
    except Exception:
        pass
    try:
        if _playwright_instance:
            _playwright_instance.stop()
    except Exception:
        pass
    _browser_context = None
    _playwright_instance = None


def get_or_relaunch_browser(config: dict):
    global _browser_context
    if _browser_context is None:
        logger.info("Launching browser context...")
        launch_browser(config)
    return _browser_context


def ensure_logged_in(context, config: dict) -> None:
    """Navigate to the target URL and prompt for manual login if redirected to login page."""
    url = config["carevender_url"]
    page = context.new_page()
    try:
        logger.info("Navigating to %s to check login state...", url)
        page.goto(url, wait_until="networkidle", timeout=30000)
        current_url = page.url
        if "login" in current_url.lower():
            print("\n" + "=" * 60)
            print("ACTION REQUIRED: You are not logged in to Carevender.")
            print("A browser window has opened. Please log in manually.")
            print("=" * 60)
            input("Press Enter here once you are logged in...")
            # Verify login succeeded
            page.goto(url, wait_until="networkidle", timeout=30000)
            if "login" in page.url.lower():
                logger.error("Still on login page after user pressed Enter. Exiting.")
                sys.exit(1)
        logger.info("Login verified. Current URL: %s", page.url)
    finally:
        page.close()


# ---------------------------------------------------------------------------
# Form filling logic
# ---------------------------------------------------------------------------
DEFAULT_TIMEOUT = 15000  # 15 seconds


def fill_and_submit_patient(page, patient: dict, config: dict) -> None:
    """Fill the Carevender express registration form for one patient."""
    cols = config["columns"]
    data = patient["data"]
    url = config["carevender_url"]

    corporate = str(data.get(cols["corporate"], "")).strip()
    passport = str(data.get(cols["passport"], "")).strip()
    full_name = str(data.get(cols["full_name"], "")).strip()
    dob_raw = str(data.get(cols["dob"], "")).strip()
    nationality_raw = str(data.get(cols["nationality"], "")).strip()
    gender_raw = str(data.get(cols["gender"], "")).strip()

    logger.info("Processing patient: %s (Passport: %s)", full_name, passport)

    # Step 1 — Navigate to the form page
    page.goto(url, wait_until="networkidle", timeout=DEFAULT_TIMEOUT)
    page.wait_for_timeout(1500)

    # Step 2 — Corporate type selector
    logger.debug("Step 2: Setting corporate type selector to 'Corporate'")
    # Find the select that has a "Corporate" option
    selects = page.locator("select").all()
    corporate_type_select = None
    for sel in selects:
        inner = sel.inner_html(timeout=DEFAULT_TIMEOUT)
        if "Corporate" in inner and "Walk In" in inner:
            corporate_type_select = sel
            break
    if corporate_type_select is None:
        raise RuntimeError("Could not find the Corporate/Walk-In type selector on the page.")
    corporate_type_select.select_option(label="Corporate", timeout=DEFAULT_TIMEOUT)
    page.wait_for_timeout(500)

    # Step 3 — Corporate name type-ahead
    logger.debug("Step 3: Typing corporate name '%s'", corporate)
    corp_input = page.locator("input[placeholder*='Search corporate name']")
    corp_input.wait_for(state="visible", timeout=DEFAULT_TIMEOUT)
    corp_input.click(timeout=DEFAULT_TIMEOUT)
    corp_input.type(corporate, delay=80)

    # Wait for dropdown to appear (up to 3 seconds)
    dropdown_appeared = False
    try:
        # Common patterns for Vue.js autocomplete dropdowns
        page.wait_for_selector(
            "ul li, .dropdown-item, [role='option'], .autocomplete-result",
            timeout=3000,
        )
        dropdown_appeared = True
    except PlaywrightTimeoutError:
        logger.warning("Corporate dropdown did not appear for '%s' — continuing anyway.", corporate)

    if dropdown_appeared:
        try:
            first_item = page.locator(
                "ul li, .dropdown-item, [role='option'], .autocomplete-result"
            ).first
            first_item.click(timeout=DEFAULT_TIMEOUT)
        except Exception as e:
            logger.warning("Could not click first corporate dropdown item: %s", e)

    page.wait_for_timeout(1000)

    # Step 4 — ID Type selector
    logger.debug("Step 4: Setting ID type to 'Passport'")
    id_select = page.locator("select#identify")
    id_select.wait_for(state="visible", timeout=DEFAULT_TIMEOUT)
    id_select.select_option(label="Passport", timeout=DEFAULT_TIMEOUT)
    page.wait_for_timeout(300)

    # Step 5 — Passport number
    logger.debug("Step 5: Filling passport number '%s'", passport)
    passport_input = page.locator("input[placeholder*='NRIC/Passport']")
    passport_input.wait_for(state="visible", timeout=DEFAULT_TIMEOUT)
    passport_input.click(timeout=DEFAULT_TIMEOUT)
    passport_input.triple_click(timeout=DEFAULT_TIMEOUT)
    passport_input.fill(passport, timeout=DEFAULT_TIMEOUT)
    page.wait_for_timeout(1000)

    # Step 6 — Full Name
    logger.debug("Step 6: Filling full name '%s'", full_name)
    name_input = page.locator("input[placeholder*='Full Name']")
    name_input.wait_for(state="visible", timeout=DEFAULT_TIMEOUT)
    name_input.fill(full_name, timeout=DEFAULT_TIMEOUT)
    page.wait_for_timeout(1000)

    # Step 7 — Date of Birth
    dob_formatted = format_dob(dob_raw)
    logger.debug("Step 7: Filling DOB '%s' (raw: '%s')", dob_formatted, dob_raw)
    dob_input = page.locator("input[placeholder*='Date of Birth']")
    dob_input.wait_for(state="visible", timeout=DEFAULT_TIMEOUT)
    dob_input.triple_click(timeout=DEFAULT_TIMEOUT)
    dob_input.type(dob_formatted, delay=50)
    page.wait_for_timeout(1000)

    # Step 8 — Nationality
    logger.debug("Step 8: Setting nationality (raw: '%s')", nationality_raw)
    nationality_text = translate_nationality(nationality_raw)
    if nationality_text:
        # Find the select whose id starts with "ss"
        nat_select = None
        all_selects = page.locator("select").all()
        for sel in all_selects:
            sel_id = sel.get_attribute("id") or ""
            if sel_id.startswith("ss"):
                nat_select = sel
                break
        if nat_select is None:
            logger.warning("Could not find nationality select (id starting with 'ss') — skipping.")
        else:
            try:
                nat_select.select_option(label=nationality_text, timeout=DEFAULT_TIMEOUT)
                nat_select.press("Enter", timeout=DEFAULT_TIMEOUT)
                page.wait_for_timeout(300)
            except Exception as e:
                logger.warning("Could not select nationality '%s': %s", nationality_text, e)
    else:
        logger.warning("No nationality text resolved for raw value '%s' — skipping nationality field.", nationality_raw)

    page.wait_for_timeout(1000)

    # Step 9 — Gender
    gender_value = map_gender(gender_raw)
    logger.debug("Step 9: Setting gender to '%s' (raw: '%s')", gender_value, gender_raw)
    gender_select = page.locator("select#gender")
    gender_select.wait_for(state="visible", timeout=DEFAULT_TIMEOUT)
    gender_select.select_option(label=gender_value, timeout=DEFAULT_TIMEOUT)
    page.wait_for_timeout(1000)

    # Step 10 — Submit
    logger.debug("Step 10: Clicking 'Add to Queue & Start New'")
    submit_btn = page.locator("button", has_text="Add to Queue & Start New")
    submit_btn.wait_for(state="visible", timeout=DEFAULT_TIMEOUT)
    submit_btn.click(timeout=DEFAULT_TIMEOUT)
    page.wait_for_timeout(2000)

    logger.info("SUCCESS: Patient %s (Passport: %s) submitted.", full_name, passport)


# ---------------------------------------------------------------------------
# Main processing loop
# ---------------------------------------------------------------------------
def process_patients(config: dict) -> None:
    logger.info("--- Scheduled check started ---")

    # Fetch sheet data
    try:
        worksheet = get_worksheet(config)
        new_patients = get_new_patients(worksheet, config)
    except Exception as e:
        logger.error("Failed to access Google Sheet: %s", e, exc_info=True)
        logger.info("Skipping this run. Will retry at next interval.")
        return

    logger.info("Found %d new patient(s) to process.", len(new_patients))
    if not new_patients:
        return

    context = get_or_relaunch_browser(config)

    for patient in new_patients:
        row_index = patient["row_index"]
        cols = config["columns"]
        full_name = str(patient["data"].get(cols["full_name"], "")).strip()
        passport = str(patient["data"].get(cols["passport"], "")).strip()

        page = None
        try:
            page = context.new_page()
            fill_and_submit_patient(page, patient, config)
            update_status(worksheet, row_index, "Done", config)
        except PlaywrightTimeoutError as e:
            msg = f"Timeout error for patient {full_name} ({passport}): {e}"
            logger.error(msg, exc_info=True)
            try:
                update_status(worksheet, row_index, f"Error: Timeout — {e}", config)
            except Exception:
                pass
        except Exception as e:
            msg = f"Error processing patient {full_name} ({passport}): {e}"
            logger.error(msg, exc_info=True)
            try:
                update_status(worksheet, row_index, f"Error: {e}", config)
            except Exception:
                pass
            # Check if browser is still responsive; if not, relaunch
            try:
                context.pages  # simple probe
            except Exception:
                logger.warning("Browser appears unresponsive — relaunching...")
                close_browser()
                context = launch_browser(config)
        finally:
            if page:
                try:
                    page.close()
                except Exception:
                    pass

    logger.info("--- Scheduled check complete ---")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    logger.info("Carevender Bot starting up. PID=%d", os.getpid())
    config = load_config()
    logger.info("Config loaded from %s", CONFIG_PATH)

    # Launch browser and verify login
    context = launch_browser(config)
    ensure_logged_in(context, config)

    interval = config.get("check_interval_minutes", 5)
    logger.info("Scheduling patient checks every %d minute(s).", interval)

    # Run once immediately on startup
    process_patients(config)

    # Then schedule recurring runs
    schedule.every(interval).minutes.do(process_patients, config=config)

    logger.info("Bot is running. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(10)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    finally:
        close_browser()
