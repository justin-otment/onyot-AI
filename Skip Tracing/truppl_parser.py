import base64
import re
import os
import asyncio
import logging
import traceback
import time
from concurrent.futures import ThreadPoolExecutor
import requests
import urllib3
from urllib3.exceptions import ProtocolError
import sys
import ssl
from selenium import webdriver
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options
from selenium_stealth import stealth
from nordvpn import handle_rate_limit, verify_vpn_connection
from captcha import get_site_key, solve_turnstile_captcha, inject_token
import json
import undetected_chromedriver as uc
from fake_useragent import UserAgent
ua = UserAgent()


# Request with retries
def make_request_with_retries(url, retries=3, backoff_factor=1):
    http = urllib3.PoolManager()
    attempt = 0
    while attempt < retries:
        try:
            response = http.request('GET', url)
            return response
        except ProtocolError as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            attempt += 1
            sleep_time = backoff_factor * (2 ** attempt)  # Exponential backoff
            print(f"Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)
    raise Exception(f"Failed to fetch {url} after {retries} attempts.")

# Example usage:
url = 'https://www.truepeoplesearch.com'
response = make_request_with_retries(url)
print(response.data)

# Disable SSL verification temporarily (use only for testing)
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE


# === Setup ===
logging.basicConfig(
    level=logging.DEBUG,
    filename="logfile.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)

sys.stdout.reconfigure(encoding='utf-8')

# === Global Configurations ===
CAPTCHA_CONFIG = {
    "max_retries": 5,
    "wait_time_ms": 7000,
    "poll_interval_seconds": 5,
    "captcha_timeout_seconds": 75,
}
API_KEY = os.getenv("TWO_CAPTCHA_API_KEY")
CAPTCHA_API_URL = "http://2captcha.com"
LOGGING_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)

MAX_RETRIES = 5  # Maximum retry attempts for main function
BACKOFF_FACTOR = 2  # Exponential backoff factor

vpn_username =   os.getenv("VPN_USERNAME")
vpn_password = os.getenv("VPN_PASSWORD")

if not vpn_username or not vpn_password:
    print("[!] Failed to load VPN credentials!")
else:
    print("VPN Username:", vpn_username)
    print("VPN Password: Loaded successfully")


# === Constants ===
SHEET_ID = "1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A"
SHEET_NAME = "CAPE CORAL FINAL"
SHEET_NAME_2 = "For REI Upload"
START_ROW = 2
BATCH_SIZE = 10
MAX_RETRIES = 2
MAX_CAPTCHA_RETRIES = 2
BACKOFF_FACTOR = 2  # Exponential backoff factor

# Define constants
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENCODED_JSON_PATH = os.path.join(BASE_DIR, "service-account_base64.txt")
GECKODRIVER_PATH = "C:\\GeckoDriver\\geckodriver.exe"

# Read and decode service account JSON
try:
    with open(ENCODED_JSON_PATH, "r") as file:
        encoded_json = file.read().strip()

    if not encoded_json:
        raise Exception("Error: service-account_base64.txt is empty!")

    SERVICE_ACCOUNT_JSON = base64.b64decode(encoded_json).decode("utf-8")
except FileNotFoundError:
    raise Exception("Error: service-account_base64.txt is missing!")
except Exception as e:
    raise Exception(f"Error reading service-account JSON: {e}")

# Validate JSON structure
try:
    json_data = json.loads(SERVICE_ACCOUNT_JSON)
    required_keys = ["type", "project_id", "private_key", "client_email"]
    if not all(key in json_data for key in required_keys):
        raise Exception("Error: Decoded SERVICE_ACCOUNT_JSON is missing required authentication fields!")
except json.JSONDecodeError:
    raise Exception("Error: Decoded SERVICE_ACCOUNT_JSON is corrupted or improperly formatted!")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


# Authenticate with Google Sheets API
def authenticate_google_sheets():
    try:
        creds = Credentials.from_service_account_info(json_data, scopes=SCOPES)
        return build("sheets", "v4", credentials=creds)
    except Exception as e:
        raise Exception(f"Error authenticating Google Sheets API: {e}")

def get_sheet_data(sheet_id, range_name, start_row=2):
    """Fetch data from the specified Google Sheet range."""
    service = authenticate_google_sheets()
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=range_name
    ).execute()
    values = result.get('values', [])
    print(f"[DEBUG] Retrieved {len(values)} rows from range {range_name}")
    return [(start_row + i, row[0]) for i, row in enumerate(values) if row and len(row) > 0]

def extract_reference_names(sheet_id, row_index):
    """Extract reference names from columns B:H for a given row."""
    service = authenticate_google_sheets()
    range_ = f"{SHEET_NAME}!B{row_index}:H{row_index}"
    
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id,
        range=range_
    ).execute()
    
    row = result.get("values", [[]])[0]
    return [val.strip() for val in row if val.strip()]

def append_to_google_sheet(first_name, last_name, phones, emails, site):
    """Append a structured row to the 'For REI Upload' sheet."""
    
    # Validate required fields
    if not first_name or not last_name:
        logging.warning("[!] Attempting to append data with missing name fields. Skipping entry.")
        return
    if not phones:
        logging.warning(f"[!] No phone numbers found for {first_name} {last_name}. Skipping entry.")
        return
    
    try:
        service = authenticate_google_sheets()
        sheet = service.spreadsheets()

        max_phones = 5
        max_emails = 3
        phone_values = [p[0] for p in phones[:max_phones]]
        phone_types = [p[1] for p in phones[:max_phones]]
        email_values = emails[:max_emails]

        # Prepare row structure
        row = [first_name, last_name]
        for i in range(max_phones):
            row += [
                phone_values[i] if i < len(phone_values) else "",
                phone_types[i] if i < len(phone_types) else ""
            ]
        row += email_values + [""] * (max_emails - len(email_values)) + [site]

        # Append to Google Sheets
        sheet.values().append(
            spreadsheetId=SHEET_ID,
            range=f"{SHEET_NAME}!A1",  # Ensure correct sheet reference
            valueInputOption="USER_ENTERED",
            body={"values": [row]}
        ).execute()

        print(f"[+] Successfully appended result for {first_name} {last_name}")

    except HttpError as http_err:
        logging.error(f"[!] Google API Error: {http_err}")
    except Exception as e:
        logging.error(f"[!] Unexpected failure: {traceback.format_exc()}")
    
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

def fetch_truepeoplesearch_data(driver, row_index, mailing_street, zip_code):
    """
    Fetches page content while handling CAPTCHA detection and rate-limit errors dynamically.
    Inputs mailing street and zip code into the target website form, navigates, and handles parsing.

    :param driver: Selenium WebDriver instance.
    :param row_index: Row index of the entry for logging purposes.
    :param mailing_street: Mailing street address to input in the form.
    :param zip_code: ZIP code to input in the form.
    :return: Page content or None if retries fail.
    """

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"[!] Navigating to TruePeopleSearch for row {row_index} (Attempt {attempt}/{MAX_RETRIES})")

            driver.get("https://www.truepeoplesearch.com")
            time.sleep(random.uniform(2, 5))  # Mimic human behavior with random delays
            
            # Check for rate-limit or blocked message
            if any(block_word in driver.page_source.lower() for block_word in ["rate limit", "blocked", "challenge"]):
                logging.warning("[!] Rate limit detected. Retrying after backoff...")
                time.sleep(BACKOFF_FACTOR ** attempt)
                driver.refresh()
                continue

            # Fill the form with the mailing street
            WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, 'id-d-n')))
            input_field = driver.find_element(By.ID, 'id-d-n')
            input_field.clear()
            input_field.send_keys(mailing_street)

            # Fill the ZIP code field
            WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.ID, 'id-d-loc-name')))
            zip_field = driver.find_element(By.ID, 'id-d-loc-name')
            zip_field.clear()
            zip_field.send_keys(zip_code)

            # Click the search button
            driver.find_element(By.ID, 'btnSubmit-d-n').click()

            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(random.uniform(3, 5))

            # Human-like interactions to evade detection
            ActionChains(driver).move_by_offset(random.randint(100, 400), random.randint(100, 400)).perform()
            driver.execute_script("window.scrollBy(0, arguments[0]);", random.randint(400, 800))
            time.sleep(random.uniform(3, 5))

            # CAPTCHA handling logic
            page_content = driver.page_source

            # Handle CAPTCHA or Cloudflare challenge
            if any(word in page_content.lower() for word in ["captcha", "are you a human", "just a moment"]):
                logging.warning("[!] CAPTCHA or Cloudflare challenge detected. Retrying after backoff...")
                
                # Save the challenge page for debugging
                with open(f"cf_challenge_row{row_index}.html", "w", encoding="utf-8") as f:
                    f.write(page_content)
                
                time.sleep(BACKOFF_FACTOR ** attempt)
                driver.refresh()
                continue


            logging.debug(f"[DEBUG] Page content snippet: {page_content[:1000]}")
            return page_content

        except Exception as e:
            logging.error(f"[!] Error during attempt {attempt}: {str(e)}")
            time.sleep(BACKOFF_FACTOR ** attempt)
            continue

    logging.error(f"[!] Maximum retries reached. Failed to fetch data for row {row_index}.")
    return None

def parse_contact_info(html):
    soup = BeautifulSoup(html, 'html.parser')

    phone_numbers = [span.get_text(strip=True) for span in soup.select("[itemprop='telephone']")]
    phone_types = [span.get_text(strip=True) for span in soup.select(".col-12 span.smaller")]
    
    emails = []
    for email_div in soup.select("div:nth-of-type(12) .col-12 > div.pl-sm-2 .col div"):
        email_text = email_div.get_text(strip=True)
        if re.match(r"[^@]+@[^@]+\.[^@]+", email_text):
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

def navigate_to_profile(driver, matched_url):
    """
    Handles CAPTCHA while navigating to matched profiles and dynamically manages rate-limit errors.
    Checks for specific keywords indicating "Death Record" or "Deceased" before proceeding.

    :param driver: Selenium WebDriver instance.
    :param matched_url: URL of the profile to navigate to.
    :return: Page content or None if retries fail.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"[!] Attempt {attempt} to fetch: {matched_url}")
            
            # Open a new tab and switch to it
            driver.execute_script(f"window.open('{matched_url}', '_blank');")
            driver.switch_to.window(driver.window_handles[-1])
            
            # Wait for network activity to stabilize
            time.sleep(random.uniform(3, 5))
            
            # Detect rate-limiting
            if "ratelimited" in driver.current_url:
                logging.warning("[!] Rate limit detected. Retrying after backoff...")
                time.sleep(BACKOFF_FACTOR ** attempt)
                driver.refresh()
                continue
            
            # Check for specific keywords ("Death Record" or "Deceased")
            time.sleep(random.uniform(2, 4))  # Simulating human interaction delay
            page_content = driver.page_source

            # Check for death indicators
            if any(keyword in page_content.lower() for keyword in ["death record", "deceased"]):
                logging.warning("[!] Profile indicates 'Death Record' or 'Deceased'. Skipping...")
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
                return None  
            
            # Handle CAPTCHA or Cloudflare challenge
            if any(word in page_content.lower() for word in ["captcha", "are you a human", "just a moment"]):
                logging.warning("[!] CAPTCHA or Cloudflare challenge detected. Retrying...")
                
                # Save the challenge page for debugging
                with open(f"cf_challenge_profile_row{attempt}.html", "w", encoding="utf-8") as f:
                    f.write(page_content)
            
                time.sleep(BACKOFF_FACTOR ** attempt)
                driver.refresh()
                continue

            
            logging.debug(f"[DEBUG] Page content: {page_content[:1000]}")  # Logs a snippet of content
            driver.close()
            driver.switch_to.window(driver.window_handles[0])  # Switch back to main tab
            return page_content

        except Exception as e:
            logging.error(f"[!] Error during attempt {attempt}: {str(e)}")
            time.sleep(BACKOFF_FACTOR ** attempt)
            continue

    logging.error(f"[!] Maximum retries reached. Failed to fetch data from {matched_url}.")
    return None

def clear_browser_cookies(driver):
    """Clear cookies and local storage for the current browser session."""
    try:
        print("[!] Clearing browser cookies and session storage...")
        driver.delete_all_cookies()
        driver.execute_script("window.localStorage.clear();")
        driver.execute_script("window.sessionStorage.clear();")
        print("[✓] Browser session cleared.")
    except Exception as e:
        print(f"[!] Error clearing browser session: {e}")


def extract_sitekey(page_source):
    """
    Extracts CAPTCHA sitekey from the page source.
    :param page_source: The raw HTML source of the page.
    :return: Extracted sitekey or None if not found.
    """
    try:
        match = re.search(r'data-sitekey="([a-zA-Z0-9_\-]+)"', page_source)
        if match:
            sitekey = match.group(1)
            logging.info(f"[✓] Sitekey extracted: {sitekey}")
            return sitekey
        else:
            logging.warning("[!] Sitekey not found.")
            return None
    except Exception as e:
        logging.error(f"[!] Error extracting sitekey: {e}")
        return None

def main():
    """Main execution function."""

    # Define sheet data ranges before calling get_sheet_data()
    MAILING_STREETS_RANGE = f"{SHEET_NAME}!P2:P"
    ZIPCODE_RANGE = f"{SHEET_NAME}!Q2:Q"
    SITE_RANGE = f"{SHEET_NAME}!B{START_ROW}:B"

    # Retrieve sheet data
    mailing_streets = get_sheet_data(SHEET_ID, MAILING_STREETS_RANGE)
    zip_codes = get_sheet_data(SHEET_ID, ZIPCODE_RANGE)
    site_data = get_sheet_data(SHEET_ID, SITE_RANGE)

    if not mailing_streets or not zip_codes:
        logging.warning("[!] Missing data in one or both ranges. Skipping processing...")
        return

    # Convert to dictionaries for structured processing
    street_dict = dict(mailing_streets)
    zip_dict = dict(zip_codes)
    site_dict = dict(site_data)

    # Define valid entries
    valid_entries = [(idx, street_dict[idx], zip_dict[idx]) for idx in street_dict.keys() & zip_dict.keys()]

    if not valid_entries:
        logging.warning("[!] No valid entries to process. Exiting...")
        return

    logging.info(f"Processing {len(valid_entries)} total entries.")

    # -------------------------------
    # Setup Undetected Chrome Driver
    # -------------------------------
    ua = UserAgent()
    options = uc.ChromeOptions()
    options.headless = True
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument(f"user-agent={ua.random}")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = uc.Chrome(options=options)

    try:
        for batch_start in range(0, len(valid_entries), BATCH_SIZE):
            batch = valid_entries[batch_start:batch_start + BATCH_SIZE]
            print(f"[→] Processing batch {batch_start // BATCH_SIZE + 1} with {len(batch)} entries...")

            for row_index, mailing_street, zip_code in batch:
                print(f"\n[→] Processing Row {row_index}: {mailing_street}, {zip_code}")
                try:
                    captcha_retries = 0
                    html_content = None

                    while captcha_retries < MAX_CAPTCHA_RETRIES:
                        html_content = fetch_truepeoplesearch_data(driver, row_index, mailing_street, zip_code)
                        if html_content:
                            break
                        captcha_retries += 1
                        print(f"[!] CAPTCHA retry {captcha_retries}/{MAX_CAPTCHA_RETRIES}...")

                    if not html_content:
                        print("[!] Skipping row due to repeated CAPTCHA failures.")
                        continue

                    extracted_links = extract_links(html_content)
                    if not extracted_links:
                        print("[DEBUG] Extracted 0 links.")
                        handle_rate_limit()
                        continue

                    ref_names = extract_reference_names(SHEET_ID, row_index)
                    matched_results = match_entries(extracted_links, ref_names)
                    if not matched_results:
                        print(f"[!] No match found for row {row_index}.")
                        continue

                    for matched_entry in matched_results:
                        matched_url = matched_entry["link"]
                        matched_name = matched_entry["text"]
                        print(f"[→] Visiting profile: {matched_url}")

                        matched_html = navigate_to_profile(driver, matched_url)
                        if not matched_html:
                            print(f"[!] CAPTCHA blocked: {matched_url}")

                            # Save blocked page for debugging
                            with open(f"cf_blocked_row{row_index}.html", "w", encoding="utf-8") as f:
                                f.write(driver.page_source)
                            continue

                        phone_numbers, phone_types, emails = parse_contact_info(matched_html)
                        if not phone_numbers:
                            print(f"[!] No phone numbers found for row {row_index}")
                            continue

                        name_parts = matched_name.strip().split()
                        first_name = name_parts[0]
                        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

                        site_data = get_sheet_data(SHEET_ID, SITE_RANGE, START_ROW)
                        site_dict = {idx: value for idx, value in site_data}
                        site_value = site_dict.get(row_index, None)

                        if site_value is None:
                            print(f"[!] No Site value found for row {row_index}")
                            continue

                        phone_data = list(zip(phone_numbers, phone_types))
                        append_to_google_sheet(first_name, last_name, phone_data, emails, site_value)

                except Exception as e:
                    print(f"[!] Error processing row {row_index}: {e}")
                    continue

    finally:
        driver.quit()
        print("[✓] Browser session closed.")

if __name__ == "__main__":
    main()
