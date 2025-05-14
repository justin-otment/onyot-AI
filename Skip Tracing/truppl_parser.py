import asyncio
import re
import string
import sys
import random
import time
import json
import base64

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from nordvpn import handle_rate_limit
from nordvpn import verify_vpn_connection  # VPN functionality from nordvpn.py
from captcha import get_site_key, solve_turnstile_captcha, inject_token  # CAPTCHA functionalities from captcha.py
import traceback
from dotenv import load_dotenv
import os
import sys
import json
import base64
import logging
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor  # <-- THIS FIXES YOUR ERROR
import os
print("Current Working Directory:", os.getcwd())
import logging
logging.basicConfig(level=logging.DEBUG, filename="logfile.log", filemode="a",
                    format="%(asctime)s - %(levelname)s - %(message)s")
logging.info("Script started")

load_dotenv()

# === Config ===
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHEET_ID = "1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A"
SHEET_NAME = "CAPE CORAL FINAL"
SHEET_NAME_2 = "For REI Upload"
MAX_RETRIES = 1

sys.stdout.reconfigure(encoding='utf-8')

CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")

# === Decode secrets and write to files (for GitHub Actions or secure environments) ===
def write_base64_json_files():
    credentials_b64 = os.getenv("GOOGLE_CREDENTIALS_JSON")
    token_b64 = os.getenv("GOOGLE_TOKEN_JSON")

    if credentials_b64:
        try:
            with open(CREDENTIALS_PATH, "wb") as f:
                f.write(base64.b64decode(credentials_b64))
        except Exception as e:
            print(f"[!] Failed to decode/write credentials.json: {e}", file=sys.stderr)
            sys.exit(1)

    if token_b64:
        try:
            with open(TOKEN_PATH, "wb") as f:
                f.write(base64.b64decode(token_b64))
        except Exception as e:
            print(f"[!] Failed to decode/write token.json: {e}", file=sys.stderr)
            sys.exit(1)

write_base64_json_files()

# === Check existence of credential files ===
if not os.path.exists(CREDENTIALS_PATH):
    print(f"[!] credentials.json not found at path: {CREDENTIALS_PATH}", file=sys.stderr)
    sys.exit(1)

if not os.path.exists(TOKEN_PATH):
    print(f"[!] token.json not found at path: {TOKEN_PATH}", file=sys.stderr)
    sys.exit(1)

# === Authenticate Google Sheets API ===
def authenticate_google_sheets():
    try:
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH, scopes=SCOPES
        )
        service = build("sheets", "v4", credentials=creds)
        return service
    except Exception as e:
        logging.error(f"[!] Failed to authenticate with Google Sheets API: {e}")
        raise


# === Get Data from Google Sheets ===
def get_sheet_data(sheet_id, range_name):
    """
    Fetches data from a specified range in a Google Sheet.
    :param sheet_id: The ID of the Google Sheet.
    :param range_name: The range to fetch data from (e.g., 'Sheet1!A1:D10').
    :return: List of rows from the specified range.
    """
    try:
        service = authenticate_google_sheets()
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_name
        ).execute()
        values = result.get('values', [])
        return [(i + 1, row[0]) for i, row in enumerate(values) if row]  # Include row index and value
    except Exception as e:
        logging.error(f"[!] Failed to get data from Google Sheets: {e}")
        return []

def append_to_google_sheet(first_name, last_name, phones, emails, site):
    """
    Appends extracted data to the next available row in the 'For REI Upload' sheet.
    """
    service = authenticate_google_sheets()

    # Fetch header row to determine column layout
    header_row = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"{SHEET_NAME_2}!1:1"
    ).execute().get("values", [[]])[0]

    row_data = [""] * len(header_row)

    # Insert Site value
    if "Site" in header_row:
        row_data[header_row.index("Site")] = site

    # Insert First Name and Last Name
    if "First Name" in header_row:
        row_data[header_row.index("First Name")] = first_name
    if "Last Name" in header_row:
        row_data[header_row.index("Last Name")] = last_name

    # Insert up to 5 phone number/type pairs
    for i, (phone, phone_type) in enumerate(phones[:5]):
        try:
            phone_col = header_row.index("Phone Number") + (i * 2)
            type_col = header_row.index("Phone Type") + (i * 2)
            row_data[phone_col] = phone
            row_data[type_col] = phone_type
        except ValueError:
            print(f"[!] Phone columns missing or misaligned for pair #{i + 1}")

    # Insert up to 3 emails
    for i, email in enumerate(emails[:3]):
        email_header = f"Email {i + 1}"
        if email_header in header_row:
            row_data[header_row.index(email_header)] = email

    # Append the data to the next available row
    service.spreadsheets().values().append(
        spreadsheetId=SHEET_ID,
        range=f"{SHEET_NAME_2}!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row_data]}
    ).execute()

    print(f"[✓] Data appended to '{SHEET_NAME_2}'")

user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.74 Mobile Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 11_2_3) AppleWebKit/537.36 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
    "Mozilla/5.0 (Linux; Android 10; Mi 9T Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Mobile Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Safari/537.36",
]

stealth_js = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
window.chrome = { runtime: {} };
window.navigator.chrome = { runtime: {} };
"""

def extract_links(html):
    soup = BeautifulSoup(html, 'html.parser')
    entries = []

    for card in soup.find_all("div", class_="card-summary"):
        link = card.get("data-detail-link")
        if not link:
            continue
        full_link = f"https://www.truepeoplesearch.com{link}"

        name_tag = card.find("div", class_="h4")
        name = name_tag.get_text(strip=True) if name_tag else ""

        if name:
            entries.append({"link": full_link, "text": name})

    print(f"[DEBUG] Extracted {len(entries)} links:")
    for e in entries:
        print(f"    - {e['text']} -> {e['link']}")
    return entries


def name_tokens(name):
    return [normalize_and_sort(part) for part in name.split()]

def normalize_text(text):
    return re.sub(r'\s+', ' ', text.strip().upper())

def normalize_and_sort(text):
    words = re.findall(r'\w+', text.upper())
    return ' '.join(sorted(words))

def is_match(entry_text, ref_names):
    normalized_entry = normalize_and_sort(entry_text)
    for ref in ref_names:
        normalized_ref = normalize_and_sort(ref)
        if normalized_ref in normalized_entry or normalized_entry in normalized_ref:
            return True
    return False

def extract_reference_names(sheet_id, row_index):
    range_ = f'CAPE CORAL FINAL!D{row_index}:J{row_index}'
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=range_
    ).execute()
    values = result.get('values', [[]])[0]
    return [normalize_text(val) for val in values if val.strip()]

def match_entries(extracted, ref_names):
    matched_results = []
    for entry in extracted:
        if "link" in entry and "text" in entry:
            normalized_text = normalize_and_sort(entry["text"])
            for ref in ref_names:
                normalized_ref = normalize_and_sort(ref)
                if normalized_ref in normalized_text or normalized_text in normalized_ref:
                    matched_results.append({
                        "link": entry["link"],
                        "text": entry["text"],
                        "matched_to": ref
                    })
    return matched_results

def log_matches_to_sheet(sheet_id, row_index, matched_results):
    values = []
    for result in matched_results:
        if "matched_to" in result:
            entry_text = result['text']
            entry_link = result['link']
            match_label = result['matched_to']
            combined_entry = f"{entry_text} (Matched: {match_label})"
            values.extend([combined_entry, entry_link])  # Each pair in two columns

    if values:
        append_to_google_sheet(sheet_id, row_index, values)

# === Configure Logging ===
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# === Constants ===
MAX_RETRIES = 5

# === Rate-Limit Detection ===
async def detect_rate_limit(content):
    """
    Detects rate-limiting messages in the page content.
    :param content: The HTML content of the page.
    :return: True if rate limit detected, False otherwise.
    """
    if "rate limit" in content.lower() or "too many requests" in content.lower() or "temporarily rate-limited" in content.lower():
        logging.warning("[!] Rate limit detected in page content.")
        return True
    return False

# === Utility: Switch VPN with Retry ===
def switch_vpn_with_retry(max_attempts=3):
    """
    Attempts to switch VPN connection using 'verify_vpn_connection' function from nordvpn.py.
    :param max_attempts: Number of retries for VPN connection.
    :return: True if VPN switched successfully, False otherwise.
    """
    for attempt in range(1, max_attempts + 1):
        logging.info(f"[*] Attempting VPN switch (Attempt {attempt}/{max_attempts})...")
        vpn_success = verify_vpn_connection()
        if vpn_success:
            logging.info("[✓] VPN rotated successfully.")
            return True
        else:
            logging.error("[✗] VPN rotation failed.")
            time.sleep(5)  # Introduce a brief delay before retrying.
    logging.error("[!] VPN switch attempts exceeded maximum retries. Operation failed.")
    return False


async def fetch_truepeoplesearch_data(row_index, mailing_street, zip_code, browser, context, page):
    """
    Fetches page content while handling CAPTCHA detection and rate-limit errors dynamically.
    Inputs mailing street and zip code into the target website form, navigates, and handles parsing.

    :param row_index: Row index of the entry for logging purposes.
    :param mailing_street: Mailing street address to input in the form.
    :param zip_code: ZIP code to input in the form.
    :param browser: Browser instance.
    :param context: Browser context object.
    :param page: Playwright page object.
    :return: Fetched content or None if retries fail.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"[!] Navigating to the page and processing row {row_index} (Attempt {attempt}/{MAX_RETRIES}).")
            
            await page.goto("https://www.truepeoplesearch.com", wait_until="networkidle", timeout=60000)

            # Check for rate limits and block messages
            content = await page.content()
            if "rate limited" in content.lower() or "rate limit" in content.lower() or "blocked" in content.lower():
                logging.warning("[!] Rate limit or block detected. Attempting to resolve...")
                if await handle_rate_limit(page):
                    await asyncio.sleep(BACKOFF_FACTOR ** attempt)
                    continue
                else:
                    logging.error("[!] Rate limit handling failed. Exiting...")
                    break

            # Fill and submit the form
            await page.wait_for_selector('#id-d-n', state='visible', timeout=60000)
            await page.click('#id-d-n')  # Focus on the input field
            await page.press('#id-d-n', 'Control+A')  # Select all text
            await page.press('#id-d-n', 'Delete')  # Delete selected text
            await page.fill('#id-d-n', mailing_street)

            await page.wait_for_selector('#id-d-loc-name', state='visible', timeout=60000)
            await page.click('#id-d-loc-name')  # Focus on the input field
            await page.press('#id-d-loc-name', 'Control+A')  # Select all text
            await page.press('#id-d-loc-name', 'Delete')  # Delete selected text
            await page.fill('#id-d-loc-name', zip_code)

            await page.click('#btnSubmit-d-n')
            await page.wait_for_load_state("domcontentloaded", timeout=60000)

            # Simulate human-like interactions for stealth
            await asyncio.sleep(random.uniform(3, 5))
            await page.mouse.move(random.randint(100, 400), random.randint(100, 400), steps=20)
            await page.mouse.wheel(0, random.randint(400, 800))
            await asyncio.sleep(random.uniform(3, 5))

            content = await page.content()
            logging.debug(f"[DEBUG] Full page content at timeout: {content[:1000]}")  # Logs a snippet (1000 characters).

            # CAPTCHA handling logic
            if "captcha" in content.lower() or "are you a human" in content.lower():
                logging.warning(f"[!] CAPTCHA detected on attempt {attempt}. Fetching sitekey dynamically...")
                sitekey = await get_site_key(page)
                if not sitekey:
                    logging.error("[!] Failed to retrieve sitekey. Retrying...")
                    await asyncio.sleep(BACKOFF_FACTOR ** attempt)
                    continue

                logging.info(f"[✓] Sitekey found: {sitekey}. Solving CAPTCHA via 2Captcha API.")
                captcha_token = solve_turnstile_captcha(sitekey, page.url)
                if not captcha_token:
                    logging.error("[!] CAPTCHA solving failed. Retrying...")
                    await asyncio.sleep(BACKOFF_FACTOR ** attempt)
                    continue

                success = await inject_token(page, captcha_token, page.url)
                if not success:
                    logging.error("[!] CAPTCHA token injection failed. Retrying...")
                    await asyncio.sleep(BACKOFF_FACTOR ** attempt)
                    continue

                await page.reload(wait_until="networkidle")
                content = await page.content()
                if "captcha" not in content.lower():
                    logging.info("[✓] CAPTCHA solved and page loaded successfully.")
                    return content
                else:
                    logging.warning("[!] CAPTCHA challenge persists after solving. Retrying...")
                    continue

            # If no CAPTCHA or rate limit, return the content
            return content

        except Exception as e:
            logging.error(f"[!] Error during attempt {attempt}: {str(e)}")
            await asyncio.sleep(BACKOFF_FACTOR ** attempt)
            continue

    logging.error(f"[!] Maximum retries reached. Failed to fetch data for row {row_index}.")
    return None

def parse_contact_info(html):
    soup = BeautifulSoup(html, 'html.parser')

    phone_numbers = []
    phone_types = []
    emails = []

    # Extract Phone Numbers
    phone_spans = soup.select(".col-12 > div.row span[itemprop='telephone'], .collapse span[itemprop='telephone']")
    for span in phone_spans:
        phone_numbers.append(span.get_text(strip=True))

    # Extract Phone Types
    phone_types_spans = soup.select(".col-12 > div.row span.smaller, .collapse span.smaller")
    for span in phone_types_spans:
        phone_types.append(span.get_text(strip=True))

    # Extract Emails
    email_divs = soup.select("div:nth-of-type(12) .col-12 > div.pl-sm-2 .col div")
    for email_div in email_divs:
        email_text = email_div.get_text(strip=True)
        if re.match(r"[^@]+@[^@]+\.[^@]+", email_text):  # Validate email format
            emails.append(email_text)

    return phone_numbers, phone_types, emails

# === Sheet Update Logic ===
def get_column_letter(index):
    letters = string.ascii_uppercase
    return letters[index] if index < 26 else letters[(index // 26) - 1] + letters[index % 26]

def get_existing_headers(sheet_id, sheet_name):
    """Fetch column headers from row 1 of the specified sheet."""
    range_ = f"{sheet_name}!1:1"  # Specify correct sheet name
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=range_
    ).execute()
    headers = result.get("values", [[]])[0]
    return headers if headers else []

async def navigate_to_profile(page, matched_url):
    """
    Handles CAPTCHA while navigating to matched profiles and dynamically manages rate-limit errors.
    Checks for specific keywords indicating "Death Record" or "Deceased" before proceeding.
    :param page: Playwright Page object.
    :param matched_url: URL of the profile to navigate to.
    :return: Page content or None if retries fail.
    """
    MAX_RETRIES = 3  # Limit retries

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"[!] Attempt {attempt} to fetch: {matched_url}")
            
            # Open new tab manually using the browser context of the existing page
            browser_context = page.context
            new_tab = await browser_context.new_page()

            # Wait for network activity to idle
            await new_tab.wait_for_load_state("networkidle")
            await new_tab.goto(matched_url, wait_until="networkidle", timeout=60000)

            # Check if rate-limited by inspecting the current URL
            page = new_tab.url
            if "ratelimited" in page:
                print("[!] Rate limit detected. Switching VPN server and retrying...")
                await handle_rate_limit(page)  # Fixed usage by passing `new_tab`
                await new_tab.reload(wait_until="networkidle", timeout=60000)
                await asyncio.sleep(3)  # Allow stabilization
                continue

            # Check for specific keywords ("Death Record" or "Deceased")
            print("[!] Checking for 'Death Record' or 'Deceased'...")
            element = await new_tab.query_selector("div.row.pl-md-1")
            if element:
                element_text = await element.text_content()
                if "Death Record" in element_text or "Deceased" in element_text:
                    print("[!] Profile indicates 'Death Record' or 'Deceased'. Skipping...")
                    await new_tab.close()  # Close the tab before skipping
                    return None  

            # Human-like interactions
            await new_tab.wait_for_timeout(random.randint(3000, 5000))
            await new_tab.mouse.move(random.randint(100, 400), random.randint(100, 400), steps=20)
            await new_tab.mouse.wheel(0, random.randint(400, 800))
            await new_tab.wait_for_timeout(random.randint(3000, 5000))

            content = await new_tab.content()

            # Detect CAPTCHA
            if "captcha" in content.lower() or "are you a human" in content.lower():
                print(f"[!] CAPTCHA detected on attempt {attempt}. Fetching sitekey dynamically...")
                sitekey = await get_site_key(new_tab)
                if not sitekey:
                    print("[!] No valid sitekey found. Skipping CAPTCHA solving.")
                    await new_tab.close()  # Close the tab before skipping
                    continue  

                print(f"[✓] Sitekey found: {sitekey}. Solving CAPTCHA via 2Captcha API.")
                captcha_token = solve_turnstile_captcha(sitekey, matched_url)
                if not captcha_token:
                    print("[!] CAPTCHA solving failed. Retrying...")
                    await new_tab.close()  # Close the tab before retrying
                    continue  

                # Inject CAPTCHA token
                success = await inject_token(new_tab, captcha_token, matched_url)
                if not success:
                    print("[!] CAPTCHA token injection failed. Retrying...")
                    await new_tab.close()  # Close the tab before retrying
                    continue  

                print("[✓] CAPTCHA solved successfully. Reloading page...")
                await new_tab.reload(wait_until="networkidle")
                content = await new_tab.content()

                if "captcha" not in content.lower():
                    print("[✓] CAPTCHA solved and page loaded successfully.")
                    await new_tab.close()  # Close the tab after successful processing
                    return content

                print("[!] CAPTCHA challenge still present. Retrying...")
                await new_tab.close()  # Close the tab before retrying
                continue  

            await new_tab.close()  # Close the tab after successful processing
            return content  # Page loaded successfully without CAPTCHA or rate-limiting issues
        
        except Exception as e:
            print(f"[!] Error during attempt {attempt} for {matched_url}: {e}")
            await handle_rate_limit(new_tab)  # Corrected to retry VPN on `new_tab`
            continue

    print(f"[!] Skipping {matched_url} due to persistent CAPTCHA or rate-limit issues.")
    return None

async def clear_browser_cookies(page):
    """Clear cookies and local storage for the current browser session."""
    try:
        print("[!] Clearing browser cookies and session storage...")
        await page.context.clear_cookies()
        await page.evaluate("window.localStorage.clear();")
        await page.evaluate("window.sessionStorage.clear();")
        print("[✓] Browser session cleared.")
    except Exception as e:
        print(f"[!] Error clearing browser session: {e}")


def extract_sitekey(response_body):
    """
    Extracts the CAPTCHA sitekey from the network response body.
    :param response_body: The raw response content as a string.
    :return: The extracted sitekey or None if not found.
    """
    try:
        # Use regex to search for "data-sitekey" in the response
        match = re.search(r'data-sitekey="([a-zA-Z0-9_\-]+)"', response_body)
        if match:
            sitekey = match.group(1)
            logging.info(f"[✓] Sitekey extracted: {sitekey}")
            return sitekey
        else:
            logging.warning("[!] Sitekey not found in the response body.")
            return None
    except Exception as e:
        logging.error(f"[!] Error extracting sitekey: {e}")
        return None

executor = ThreadPoolExecutor()

async def main():
    MAILING_STREETS_RANGE = "CAPE CORAL FINAL!P2612:P"
    ZIPCODE_RANGE = "CAPE CORAL FINAL!Q2612:Q"
    SHEET_ID = "1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A"
    SHEET_NAME = "CAPE CORAL FINAL!"
    BATCH_SIZE = 10
    MAX_CAPTCHA_RETRIES = 3

    mailing_streets = get_sheet_data(SHEET_ID, MAILING_STREETS_RANGE)
    zip_codes = get_sheet_data(SHEET_ID, ZIPCODE_RANGE)

    if not mailing_streets or not zip_codes:
        print("[!] Missing data in one or both ranges. Skipping processing...")
        return

    mailing_streets = [(row_index, value) for row_index, value in mailing_streets if value.strip()]
    zip_codes = [(row_index, value) for row_index, value in zip_codes if value.strip()]

    street_dict = {row_index: value for row_index, value in mailing_streets}
    zip_dict = {row_index: value for row_index, value in zip_codes}

    valid_entries = [
        (index, street_dict[index], zip_dict[index])
        for index in street_dict.keys() & zip_dict.keys()
    ]

    if not valid_entries:
        print("[!] No valid entries to process. Exiting...")
        return

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    for batch_start in range(0, len(valid_entries), BATCH_SIZE):
        batch = valid_entries[batch_start:batch_start + BATCH_SIZE]
        print(f"[→] Processing batch {batch_start // BATCH_SIZE + 1} with {len(batch)} entries...")

        for row_index, mailing_street, zip_code in batch:
            print(f"\n[→] Processing Row {row_index}: Mailing Street '{mailing_street}', ZIP '{zip_code}'")
            try:
                captcha_retries = 0
                html_content = None

                while captcha_retries < MAX_CAPTCHA_RETRIES:
                    html_content = await fetch_truepeoplesearch_data(row_index, mailing_street, zip_code)
                    if html_content:
                        break
                    captcha_retries += 1
                    print(f"[!] Retrying CAPTCHA solving for row {row_index} ({captcha_retries}/{MAX_CAPTCHA_RETRIES})...")

                if not html_content:
                    print("[!] Skipping row due to repeated CAPTCHA failures.")
                    continue

                extracted_links = extract_links(html_content)

                if not extracted_links:
                    print("[DEBUG] Extracted 0 links:")
                    await handle_rate_limit()
                    continue

                ref_names = extract_reference_names(SHEET_ID, row_index)
                matched_results = match_entries(extracted_links, ref_names)

                if not matched_results:
                    print(f"[!] No match found in row {row_index}. Skipping second batch extraction.")
                    continue

                for matched_entry in matched_results:
                    matched_url = matched_entry["link"]
                    matched_name = matched_entry["text"]
                    print(f"[→] Navigating to matched profile: {matched_url}")

                    matched_html = await navigate_to_profile(matched_name, mailing_street, matched_url)
                    if not matched_html:
                        print(f"[!] CAPTCHA blocked access to: {matched_url}")
                        continue

                    phone_numbers, phone_types, emails = parse_contact_info(matched_html)
                    phone_data = list(zip(phone_numbers, phone_types))

                    if not phone_numbers or not phone_types:
                        print(f"[!] Skipping row {row_index}: No phone data found.")
                        continue

                    name_parts = matched_name.strip().split()
                    first_name = name_parts[0] if name_parts else ""
                    last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

                    site_data = get_sheet_data(SHEET_ID, range_name=f"{SHEET_NAME}!B2612:B")
                    site_dict = {idx: value for idx, value in site_data}
                    site_value = site_dict.get(row_index, None)

                    if site_value is None:
                        logging.warning(f"[!] No Site value found for row {row_index}. Skipping.")
                        continue

                    append_to_google_sheet(
                        first_name=first_name,
                        last_name=last_name,
                        phones=phone_data,
                        emails=emails,
                        site=site_value
                    )

            except Exception as e:
                print(f"[!] Error processing row {row_index}: {e}")
                continue

if __name__ == "__main__":
    asyncio.run(main())
