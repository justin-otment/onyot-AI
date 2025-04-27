import asyncio
import re
import string
import sys
import random

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import stealth_async
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from nordvpn import handle_rate_limit
import logging
from dotenv import load_dotenv
from captcha import get_site_key, solve_turnstile_captcha, detect_captcha, inject_token, solve_captcha
import traceback
from dotenv import load_dotenv
import os

vpn_username = os.getenv("VPN_USERNAME")
vpn_password = os.getenv("VPN_PASSWORD")

if not vpn_username or not vpn_password:
    raise ValueError("[!] Missing VPN credentials. Please check environment variables.")

# === Config ===
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
CREDENTIALS_JSON = os.getenv("GITHUB_CREDENTIALS_JSON")
TOKEN_JSON = os.getenv("GITHUB_TOKEN_JSON")

# Define sheet names and settings
SHEET_NAME = "CAPE CORAL FINAL"
SHEET_NAME_2 = "For REI Upload"
MAX_RETRIES = 1

# === Google Sheets Auth ===
# Validate credentials environment variables
if not CREDENTIALS_JSON:
    raise ValueError("[!] Missing GITHUB_CREDENTIALS_JSON environment variable. Check GitHub Secrets configuration.")
if not TOKEN_JSON:
    raise ValueError("[!] Missing GITHUB_TOKEN_JSON environment variable. Check GitHub Secrets configuration.")

# Save credentials and token JSON to files (useful for debugging and API requirements)
CREDENTIALS_PATH = "/home/runner/credentials.json"
TOKEN_PATH = "/home/runner/token.json"

# Write credentials JSON to file
if not os.path.exists(CREDENTIALS_PATH):
    with open(CREDENTIALS_PATH, 'w') as cred_file:
        cred_file.write(CREDENTIALS_JSON)

if not os.path.exists(TOKEN_PATH):
    with open(TOKEN_PATH, 'w') as token_file:
        token_file.write(TOKEN_JSON)

# Ensure credentials and token files are accessible
if not os.path.exists(CREDENTIALS_PATH):
    raise FileNotFoundError(f"Credentials file not found at {CREDENTIALS_PATH}")
if not os.path.exists(TOKEN_PATH):
    raise FileNotFoundError(f"Token file not found at {TOKEN_PATH}")

def authenticate_google_sheets():
    """Authenticate with Google Sheets API using credentials."""
    try:
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        if not creds.valid:
            raise ValueError("[!] Provided token is invalid. Consider refreshing it.")
        return build('sheets', 'v4', credentials=creds)
    except Exception as e:
        logging.error(f"[!] Google Sheets API Authentication failed: {e}")
        raise

# === Google Sheets Integration ===
def get_sheet_data(sheet_id, range_name):
    """
    Fetches data from Google Sheets for a given range.
    Returns list of (row_index, value) tuples for non-empty first-column values.
    """
    try:
        service = authenticate_google_sheets()
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=range_name
        ).execute()
        values = result.get("values", [])
        base_row = int(re.search(r"(\d+):", range_name).group(1))

        return [
            (i + base_row, row[0])
            for i, row in enumerate(values)
            if row and len(row) > 0 and row[0].strip()
        ]
    except Exception as e:
        logging.error(f"[!] Error fetching data from Google Sheets range '{range_name}': {e}")
        return []
    
def append_to_google_sheet(first_name, last_name, phones, emails):
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
    MAX_RETRIES = 5  # Maximum retry attempts
    BACKOFF_FACTOR = 2  # Exponential backoff for retries

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logging.info(f"[!] Navigating to the page and processing row {row_index} (Attempt {attempt}/{MAX_RETRIES}).")

            # Navigate to the main page
            await page.goto("https://www.truepeoplesearch.com", wait_until="domcontentloaded", timeout=60000)
            
            # Check for rate limits and block messages
            content = await page.content()
            if "ratelimited" in content.lower() or "rate limit" in content.lower() or "you have been blocked" in content.lower():
                logging.warning("[!] Rate limit or block detected. Switching VPN server and retrying...")
                await handle_rate_limit(page)  # Ensure you’ve implemented this function
                await asyncio.sleep(BACKOFF_FACTOR ** attempt)  # Exponential backoff
                continue

            # Ensure form fields are visible and fill them
            await page.wait_for_selector('#id-d-n', state='visible', timeout=60000)
            await page.fill('#id-d-n', mailing_street)
            await page.wait_for_selector('#id-d-loc-name', state='visible', timeout=60000)
            await page.fill('#id-d-loc-name', zip_code)

            # Submit the form
            await page.click('#btnSubmit-d-n')
            await page.wait_for_load_state("networkidle")

            # Simulate human-like interactions for stealth
            await asyncio.sleep(random.uniform(3, 5))  # Random short delay
            await page.mouse.move(random.randint(100, 400), random.randint(100, 400), steps=20)
            await page.mouse.wheel(0, random.randint(400, 800))
            await asyncio.sleep(random.uniform(3, 5))  # Another short random delay

            # Detect CAPTCHA
            if "captcha" in content.lower() or "are you a human" in content.lower():
                logging.warning(f"[!] CAPTCHA detected on attempt {attempt}. Fetching sitekey dynamically...")
                sitekey = await get_site_key(page)
                if not sitekey:
                    logging.error("[!] Failed to retrieve sitekey. Retrying...")
                    await asyncio.sleep(BACKOFF_FACTOR ** attempt)  # Exponential backoff
                    continue

                # Solve CAPTCHA
                logging.info(f"[✓] Sitekey found: {sitekey}. Solving CAPTCHA via 2Captcha API.")
                captcha_token = solve_turnstile_captcha(sitekey, page.url)
                if not captcha_token:
                    logging.error("[!] CAPTCHA solving failed. Retrying...")
                    await asyncio.sleep(BACKOFF_FACTOR ** attempt)
                    continue

                # Inject the solved CAPTCHA token
                success = await inject_token(page, captcha_token, page.url)
                if not success:
                    logging.error("[!] CAPTCHA token injection failed. Retrying...")
                    await asyncio.sleep(BACKOFF_FACTOR ** attempt)
                    continue

                # Reload the page and validate CAPTCHA
                await page.reload(wait_until="networkidle")
                content = await page.content()
                if "captcha" not in content.lower():
                    logging.info("[✓] CAPTCHA solved and page loaded successfully.")
                    return content  # Return content if CAPTCHA solved
                else:
                    logging.warning("[!] CAPTCHA challenge persists after solving. Retrying...")
                    continue

            # If no CAPTCHA or rate limit, return the content
            return content

        except Exception as e:
            logging.error(f"[!] Error during attempt {attempt}: {str(e)}")
            await asyncio.sleep(BACKOFF_FACTOR ** attempt)  # Exponential backoff on errors
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
            url = new_tab.url
            if "ratelimited" in url:
                print("[!] Rate limit detected. Switching VPN server and retrying...")
                await handle_rate_limit(page.context)  # Using the page's context for VPN handling
                await new_tab.close()  # Ensure new tab is closed before retry
                continue

            # Check for specific keywords ("Death Record" or "Deceased")
            print("[!] Checking for 'Death Record' or 'Deceased'...")
            element = await new_tab.query_selector("div.row.pl-md-1")
            if element:
                element_text = await element.text_content()
                if "Death Record" in element_text or "Deceased" in element_text:
                    print("[!] Profile indicates 'Death Record' or 'Deceased'. Skipping...")
                    await new_tab.close()  # Close the tab before skipping
                    continue  

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
            await handle_rate_limit(page.context)  # Retry after VPN rotation
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

async def main():

    MAILING_STREETS_RANGE = "CAPE CORAL FINAL!P95:P"
    ZIPCODE_RANGE = "CAPE CORAL FINAL!Q95:Q"
    SHEET_ID = os.getenv("SHEET_ID")
    
    if not SHEET_ID:
        logging.error("[!] Missing SHEET_ID environment variable. Exiting...")
        sys.exit(1)

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

    async with async_playwright() as p:
        browser = None
        try:
            is_ci = os.getenv("CI") == "true"
            args = ["--no-sandbox", "--disable-setuid-sandbox"] if is_ci else []
            browser = await p.chromium.launch(headless=False, args=args)
            context = await browser.new_context(user_agent=random.choice(user_agents))

            await context.add_init_script(stealth_js)
            page = await context.new_page()
            await stealth_async(page)

            for row_index, mailing_street, zip_code in valid_entries:
                logging.info(f"[→] Processing Row {row_index}: {mailing_street}, {zip_code}")
                try:
                    html_content = await fetch_truepeoplesearch_data(
                        row_index, mailing_street, zip_code, browser, context, page
                    )
                    if not html_content:
                        continue

                    extracted_links = extract_links(html_content)
                    print(f"[DEBUG] Extracted {len(extracted_links)} links:")
                    for entry in extracted_links:
                        print(f"    - {entry['text']}")

                    if not extracted_links:
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
                    
                        matched_html = await navigate_to_profile(page, matched_url)
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

                        append_to_google_sheet(
                            first_name=first_name,
                            last_name=last_name,
                            phones=phone_data,
                            emails=emails
                        )

                except Exception as e:
                    print(f"[!] Error processing row {row_index}: {e}")
                    continue

        except Exception as e:
            print(f"[!] Error launching or processing browser: {e}")
        finally:
            # Close the browser after completing all iterations
            if browser:
                await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
