# 📌 Standard Library Imports (built-in modules)
import asyncio
import os
import sys
import json
import random
import time
import re
import string
from datetime import datetime
from pathlib import Path

# 📌 Third-Party Libraries
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import stealth_async

# 📌 Google Sheets API Handling
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow

# 📌 Environment Variables Management
from dotenv import load_dotenv

# === Config ===
# Define file paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")
SHEET_ID = "1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A"
SHEET_NAME = "CAPE CORAL FINAL"
SHEET_NAME_2 = "For REI Upload"
URL_RANGE = "R45:R"
MAX_RETRIES = 1

# Load environment variables from .env file
load_dotenv()

# Define Google Sheets API scopes
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# === Google Sheets Authentication ===
def authenticate_google_sheets():
    """Authenticate with Google Sheets API."""
    creds = None

    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                print("[✓] Token refreshed successfully.")
                with open(TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                print(f"[!] Error refreshing token: {e}")
                creds = None

        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
            with open(TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())
            print("[✓] New credentials obtained and saved.")

    return build('sheets', 'v4', credentials=creds)

# Initialize Sheets API
sheets_service = authenticate_google_sheets()

# Ensure correct stdout encoding
sys.stdout.reconfigure(encoding='utf-8')

def get_sheet_data(sheet_id, range_name):
    try:
        service = authenticate_google_sheets()
        result = service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range=f"{SHEET_NAME}!{range_name}"
        ).execute()
        values = result.get("values", [])
        base_row = int(re.search(r"(\d+):\w*", range_name).group(1))

        # Keep track of actual sheet row number
        return [
            (i + base_row, row[0])
            for i, row in enumerate(values)
            if row and row[0]
        ]
    except Exception as e:
        print(f"Error fetching data from Google Sheets: {e}")
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

def name_tokens(name):
    return [normalize_and_sort()(part) for part in name.split()]


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
        # Ensure 'link' and 'text' exist
        if "link" in entry and "text" in entry:
            normalized_text = normalize_and_sort(entry["text"])
            for ref in ref_names:
                normalized_ref = normalize_and_sort(ref)
                if normalized_ref in normalized_text or normalized_text in normalized_ref:
                    matched_results.append({
                        "link": entry["link"],
                        "text": entry["text"],
                        "matched_to": ref  # Add the matched reference term
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
        update_sheet_data(sheet_id, row_index, values)

# Load environment variables
load_dotenv()
TWOCAPTCHA_API_KEY = os.getenv("TWOCAPTCHA_API_KEY")

if not TWOCAPTCHA_API_KEY:
    print("[!] Missing TwoCaptcha API Key! Set TWOCAPTCHA_API_KEY in environment variables.")

async def get_site_key(page):
    """Extracts the CAPTCHA site key dynamically from the page with enhanced robustness."""
    MAX_RETRIES = 5  # Number of retries
    WAIT_TIME = 7000  # Time to wait between retries (milliseconds)

    # Log retries
    print("[*] Attempting to locate CAPTCHA sitekey...")

    for attempt in range(MAX_RETRIES):
        try:
            # Wait for the network activity to idle
            await page.wait_for_load_state("networkidle")
            
            # Wait for selector to appear (handle dynamic loading)
            await page.wait_for_selector("[data-sitekey], input[name=\"sitekey\"], .captcha-sitekey", timeout=60000)
            
            # Evaluate sitekey from DOM
            site_key = await page.evaluate("""() => {
                let selectors = [
                    document.querySelector('[data-sitekey]'),
                    document.querySelector('input[name="sitekey"]'),
                    document.querySelector('.captcha-sitekey')
                ];
                
                for (let selector of selectors) {
                    if (selector) {
                        return selector.getAttribute('data-sitekey') || selector.value;
                    }
                }
                return null;
            }""")
            
            # If sitekey is found, return it
            if site_key:
                print(f"[✓] Sitekey found: {site_key}")
                return site_key
            else:
                print(f"[!] Attempt {attempt + 1}: Sitekey not found. Retrying...")
                await page.wait_for_timeout(WAIT_TIME)  # Wait before retry

        except Exception as e:
            # Handle timeout or selector errors
            print(f"[!] Error during attempt {attempt + 1}: {str(e)}")
            await page.wait_for_timeout(WAIT_TIME)

    # Log failure and save DOM snapshot for debugging
    print("[✗] Failed to locate CAPTCHA sitekey after maximum retries.")
    dom_snapshot = await page.content()
    with open("dom_snapshot.html", "w") as file:
        file.write(dom_snapshot)
    print("[*] DOM snapshot saved as 'dom_snapshot.html'. Inspect to identify missing sitekey.")

    return None

def solve_turnstile_captcha(sitekey, url):
    """Sends CAPTCHA solving request to 2Captcha API."""
    if not TWOCAPTCHA_API_KEY:
        print("[!] Cannot solve CAPTCHA: No API key provided.")
        return None

    try:
        response = requests.post("http://2captcha.com/in.php", data={
            "key": TWOCAPTCHA_API_KEY,
            "method": "turnstile",
            "sitekey": sitekey,
            "pageurl": url,
            "json": 1
        })

        request_data = response.json()
        if request_data.get("status") != 1:
            print(f"[!] CAPTCHA request failed: {request_data}")
            return None

        captcha_id = request_data["request"]
        print(f"[✓] CAPTCHA solving request sent. ID: {captcha_id}. Waiting for solution...")

        RETRY_DELAY = 8  # Configurable retry delay
        for _ in range(15):  # Poll for 75s max
            time.sleep(RETRY_DELAY)

            solved_response = requests.get(f"http://2captcha.com/res.php?key={TWOCAPTCHA_API_KEY}&action=get&id={captcha_id}&json=1")
            solved_data = solved_response.json()

            if solved_data.get("status") == 1:
                captcha_token = solved_data["request"]
                print(f"[✓] CAPTCHA solved successfully: {captcha_token}")
                return captcha_token

        print("[!] CAPTCHA solving timed out.")
        return None

    except requests.exceptions.RequestException as e:
        print(f"[!] Error communicating with 2Captcha API: {e}")
        return None


async def fetch_truepeoplesearch_data(url, browser, context, page):
    """Fetches page content while handling CAPTCHA detection dynamically, without closing the browser."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"Attempt {attempt} to fetch: {url}")
            # Wait for the network activity to idle
            await page.wait_for_load_state("networkidle")
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Perform human-like interactions
            await page.wait_for_timeout(random.randint(3000, 5000))
            await page.mouse.move(random.randint(100, 400), random.randint(100, 400), steps=20)
            await page.mouse.wheel(0, random.randint(400, 800))
            await page.wait_for_timeout(random.randint(3000, 5000))

            content = await page.content()

            # Check for CAPTCHA
            if "captcha" in content.lower() or "are you a human" in content.lower():
                print(f"[!] CAPTCHA detected on attempt {attempt}. Fetching sitekey dynamically...")

                # Fetch the sitekey dynamically
                sitekey = await get_site_key(page)
                if not sitekey:
                    print("[!] No valid sitekey found. Skipping CAPTCHA solving.")
                    continue  # Proceed with retries

                print(f"[✓] Sitekey found: {sitekey}. Solving CAPTCHA via 2Captcha API.")
                captcha_token = solve_turnstile_captcha(sitekey, url)
                if not captcha_token:
                    print("[!] CAPTCHA solving failed. Skipping row.")
                    continue  # Retry instead of terminating

                print(f"[✓] CAPTCHA solved successfully. Retrying request for {url} with token.")

                # Inject CAPTCHA token into the correct context
                success = await inject_token(page, captcha_token, url)
                if not success:
                    print("[!] CAPTCHA injection failed. Retrying...")
                    continue  # Retry instead of terminating

                # Wait for CAPTCHA processing
                await page.wait_for_timeout(5000)

                # Force refresh to validate CAPTCHA completion
                print("[✓] Reloading page to validate CAPTCHA token.")
                await page.reload(wait_until="networkidle")

                # Recheck page content for CAPTCHA persistence
                content = await page.content()
                if "captcha" not in content.lower():
                    print("[✓] CAPTCHA solved and page loaded successfully.")
                    return content

                print("[!] CAPTCHA challenge still present. Retrying...")
                continue  # Retry instead of failing

            return content  # Page loaded successfully without CAPTCHA

        except Exception as e:
            print(f"[!] Error during attempt {attempt}: {e}")
            continue  # Retry instead of terminating

    print(f"[!] CAPTCHA challenge persisted after maximum retries. Skipping {url}.")
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

async def inject_token(page, captcha_token, url):
    """Injects CAPTCHA token, submits validation, and ensures return to original inquiry."""
    try:
        print("[✓] Attempting CAPTCHA token injection.")

        # Directly submit the CAPTCHA token via POST request
        response = await page.evaluate("""(token) => {
            return fetch("/internalcaptcha/captchasubmit", {
                method: "POST",
                body: new URLSearchParams({ 'captchaToken': token }),
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            }).then(res => res.json())
              .then(data => {
                  if (data.RedirectUrl) {
                      document.location.href = data.RedirectUrl;
                      console.log("[✓] CAPTCHA successfully submitted. Redirecting...");
                      return true;
                  } else {
                      console.error("[!] CAPTCHA submission failed.");
                      return false;
                  }
              }).catch(error => {
                  console.error("[!] Error in CAPTCHA submission:", error);
                  return false;
              });
        }""", captcha_token)

        # If CAPTCHA submission failed, reload the page and retry
        if not response:
            print("[!] CAPTCHA submission failed. Trying page reload...")
            await page.reload(wait_until="networkidle")
            return False

        print(f"[✓] CAPTCHA solved! Navigating back to original URL: {url}")
        await page.goto(url, wait_until="networkidle", timeout=60000)

        return True  # CAPTCHA successfully cleared

    except Exception as e:
        print(f"[!] Error injecting CAPTCHA token: {e}")
        return False

def extract_links(html):
    soup = BeautifulSoup(html, 'html.parser')
    entries = []

    # Modify this to extract link data correctly
    for person_link in soup.find_all("a", href=re.compile(r"^/find/person/")):  # Adjust the target elements as needed
        link = f"https://www.truepeoplesearch.com{person_link['href']}"
        text = person_link.get_text(strip=True)
        entries.append({"link": link, "text": text})
    return entries

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
    """Handles CAPTCHA while navigating to matched profiles."""
    for attempt in range(1, 4):  # Limit retries``
        try:
            print(f"Attempt {attempt} to fetch: {matched_url}")
            # Wait for the network activity to idle
            await page.wait_for_load_state("networkidle")
            await page.goto(matched_url, wait_until="networkidle", timeout=60000)

            # Human-like interactions
            await page.wait_for_timeout(random.randint(3000, 5000))
            await page.mouse.move(random.randint(100, 400), random.randint(100, 400), steps=20)
            await page.mouse.wheel(0, random.randint(400, 800))
            await page.wait_for_timeout(random.randint(3000, 5000))

            content = await page.content()

            if "captcha" in content.lower() or "are you a human" in content.lower():
                print(f"[!] CAPTCHA detected on attempt {attempt}. Fetching sitekey dynamically...")

                sitekey = await get_site_key(page)
                if not sitekey:
                    print("[!] No valid sitekey found. Skipping CAPTCHA solving.")
                    continue  

                print(f"[✓] Sitekey found: {sitekey}. Solving CAPTCHA via 2Captcha API.")
                captcha_token = solve_turnstile_captcha(sitekey, matched_url)
                if not captcha_token:
                    print("[!] CAPTCHA solving failed. Skipping row.")
                    continue  

                print(f"[✓] CAPTCHA solved successfully. Retrying request for {matched_url} with token.")

                success = await inject_token(page, captcha_token, matched_url)
                if not success:
                    print("[!] CAPTCHA injection failed. Retrying...")
                    continue  

                await page.wait_for_timeout(5000)

                print("[✓] Reloading page to validate CAPTCHA token.")
                await page.reload(wait_until="networkidle")

                content = await page.content()
                if "captcha" not in content.lower():
                    print("[✓] CAPTCHA solved and page loaded successfully.")
                    return content

                print("[!] CAPTCHA challenge still present. Retrying...")
                continue  
            
            return content  # Page loaded successfully without CAPTCHA


        except Exception as e:
            print(f"[!] Error during attempt {attempt} for {matched_url}: {e}")
            continue

    print(f"[!] Skipping {matched_url} due to persistent CAPTCHA.")
    return None

# === Main Playwright Execution ===
async def main():
    """Main execution function for Playwright automation."""
    url_entries = get_sheet_data(SHEET_ID, URL_RANGE)
    if not url_entries:
        print("[!] No URLs fetched from Google Sheets. Exiting...")
        return

    async with async_playwright() as p:
        for attempt in range(1, MAX_RETRIES + 1):
            print(f"[✓] Attempt {attempt} to launch browser.")
        try:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            context = await browser.new_context(user_agent=random.choice(user_agents))
            page = await context.new_page()
            await stealth_async(page)


            for row_index, url in url_entries:
                if not url.strip():
                    continue

                print(f"\n[→] Processing Row {row_index}: {url}")

                try:
                    html_content = await fetch_truepeoplesearch_data(url, browser, context, page)
                    if not html_content:
                        continue

                    extracted_links = extract_links(html_content)
                    if not extracted_links:
                        continue

                    ref_names = extract_reference_names(SHEET_ID, row_index)
                    matched_results = match_entries(extracted_links, ref_names)

                    if not matched_results:
                        print(f"[!] No match found in row {row_index}. Skipping second batch extraction.")
                        continue

                    # **Retrieve Headers for "For REI Upload"**
                    available_headers = get_existing_headers(SHEET_ID, SHEET_NAME_2)
                    print(f"[✓] Available headers in '{SHEET_NAME_2}': {available_headers}")

                    # **Second Batch Extraction (Contact Details)**
                    for matched_entry in matched_results:
                        matched_url = matched_entry["link"]
                        matched_name = matched_entry["text"]
                        print(f"[→] Navigating to matched profile: {matched_url}")

                        matched_html = await navigate_to_profile(page, matched_url)
                        if not matched_html:
                            continue  # Skip if CAPTCHA blocks all retries

                        # Extract contact details
                        phone_numbers, phone_types, emails = parse_contact_info(matched_html)

                        # Combine phone numbers and types into pairs (zip them)
                        phone_data = list(zip(phone_numbers, phone_types))
                        
                        # Skip if no phone numbers or phone types
                        if not phone_numbers or not phone_types:
                            print(f"[!] Skipping row {row_index}: No phone data found.")
                            continue

                        # Extract first/last name from matched text
                        first_name, last_name = matched_name.split(" ", 1) if " " in matched_name else (matched_name, "")

                        # Log to Google Sheets
                        append_to_google_sheet(
                            first_name=first_name,
                            last_name=last_name,
                            phones=phone_data,
                            emails=emails
                        )


                except Exception as e:
                    print(f"[!] Error processing row {row_index}: {e}")
                    continue
                
                # Introduce randomized delay
                delay_time = random.uniform(2.5, 60)  # Randomized delay between requests
                print(f"[⏳] Waiting for {delay_time:.1f} seconds before next request...")
                await asyncio.sleep(delay_time)
                
        except Exception as e:
            print(f"[❌] Critical error encountered: {e}")

        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
