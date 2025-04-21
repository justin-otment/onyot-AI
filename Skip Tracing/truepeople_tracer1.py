import asyncio
import os
import re
import string
import json
import sys
import random
import time
from datetime import datetime

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import stealth_async
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_authorized_user_file('token.json', SCOPES)
sheets_service = build('sheets', 'v4', credentials=creds)

sys.stdout.reconfigure(encoding='utf-8')

# === Config ===
# Define file paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")
SHEET_ID = "1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A"
SHEET_NAME = "CAPE CORAL FINAL"
URL_RANGE = "R2:R1717"
MAX_RETRIES = 1

# === Google Sheets Auth ===
def authenticate_google_sheets():
    """Authenticate with Google Sheets API."""
    creds = None
    
    # Check if we have a token file
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # If there's no valid credentials, refresh or prompt for login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())  # Attempt to refresh the expired token
                print("Token refreshed successfully.")
                # Save the refreshed token back to the token file
                with open(TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                print(f"Error refreshing token: {e}")
                creds = None  # Reset creds if refresh fails
        if not creds:
            # If no valid credentials are available or refresh fails, initiate re-authentication
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
            # Save the new credentials for future use
            with open(TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())
            print("New credentials obtained and saved.")
    
    # Build the Sheets API client with valid credentials
    return build('sheets', 'v4', credentials=creds)

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
    
def update_sheet_data(sheet_id, row_index, values):
    from string import ascii_uppercase

    # We'll write starting from column 'T'
    start_col_index = ascii_uppercase.index('T')  # 19th letter
    end_col_index = start_col_index + len(values) - 1  # Adjust based on length of values

    # Handle column letters for target range
    start_col_letter = ascii_uppercase[start_col_index]
    end_col_letter = ascii_uppercase[end_col_index] if end_col_index < len(ascii_uppercase) else get_column_letter(end_col_index)

    target_range = f"CAPE CORAL FINAL!{start_col_letter}{row_index}:{end_col_letter}{row_index}"

    body = {
        "range": target_range,
        "majorDimension": "ROWS",
        "values": [values]
    }

    sheets_service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=target_range,
        valueInputOption="RAW",
        body=body
    ).execute()

user_agents = [
    # Include at least 10 varied user agents here.
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...Chrome/120.0.0.0 Safari/537.36",
    # Add more user agents
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

# Load API Key for 2Captcha
api_key = os.getenv('TWOCAPTCHA_API_KEY')

async def get_site_key(page):
    """Extract sitekey by finding iframe URL or by scanning script contents."""
    try:
        # First attempt: look for the iframe with the sitekey in its src
        iframe = await page.query_selector('iframe[src*="challenges.cloudflare.com"]')
        if iframe:
            iframe_src = await iframe.get_attribute('src')
            if iframe_src and "k=" in iframe_src:
                return iframe_src.split("k=")[1].split("&")[0]
        
        # Fallback: search all <script> tags for potential 'k=' strings
        scripts = await page.query_selector_all("script")
        for script in scripts:
            script_content = await script.text_content()
            if script_content and "k=" in script_content:
                match = re.search(r'k=([a-zA-Z0-9_-]+)', script_content)
                if match:
                    return match.group(1)

    except Exception as e:
        print(f"[!] Error extracting sitekey: {e}")
    
    return None  # if nothing found

def solve_turnstile_captcha(sitekey, url):
    """Sends CAPTCHA solving request to 2Captcha API."""
    response = requests.post("http://2captcha.com/in.php", data={
        "key": api_key,
        "method": "turnstile",
        "sitekey": sitekey,
        "pageurl": url,
        "json": 1
    })

    request_data = response.json()
    if request_data.get("status") == 1:
        captcha_id = request_data["request"]
        print(f"[✓] CAPTCHA solving request sent. ID: {captcha_id}. Waiting for solution...")

        RETRY_DELAY = 8  # Configurable retry delay
        for _ in range(15):  # Poll for 75s max
            time.sleep(RETRY_DELAY)

            solved_response = requests.get(f"http://2captcha.com/res.php?key={api_key}&action=get&id={captcha_id}&json=1")
            solved_data = solved_response.json()

            if solved_data.get("status") == 1:
                captcha_token = solved_data["request"]
                print(f"[✓] CAPTCHA solved successfully: {captcha_token}")
                return captcha_token

        print("[!] CAPTCHA solving timed out.")
        return None

    print(f"[!] CAPTCHA request failed: {request_data}")
    return None

async def fetch_truepeoplesearch_data(url, browser, context, page):
    """Fetches page content while handling CAPTCHA detection dynamically, without closing the browser."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"Attempt {attempt} to fetch: {url}")
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Perform human-like interactions
            await page.wait_for_timeout(random.randint(3000, 5000))
            await page.mouse.move(random.randint(100, 400), random.randint(100, 400), steps=random.randint(10, 30))
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

async def main():
    url_entries = get_sheet_data(SHEET_ID, URL_RANGE)
    if not url_entries:
        print("[!] No URLs fetched from Google Sheets. Exiting...")
        return

    async with async_playwright() as p:
        try:
            headless = os.getenv("CI", "false").lower() == "true"
            if os.getenv("DEBUG") == "1":
                headless = True

            print(f"[+] Launching browser in {'headless' if headless else 'headed'} mode")
            browser = await p.chromium.launch(headless=headless)

            context = await browser.new_context(
                user_agent=random.choice(user_agents),
                locale='en-US',
                viewport={'width': 1280, 'height': 720},
                java_script_enabled=True,
                permissions=["geolocation"],
            )

            await context.add_init_script(stealth_js)
            page = await context.new_page()
            await stealth_async(page)

            for row_index, url in url_entries:
                if not url.strip():
                    continue

                print(f"\n[→] Processing Row {row_index}: {url}")

                try:
                    html_content = await fetch_truepeoplesearch_data(url, browser, context, page)
                    
                    if not html_content:
                        print(f"[!] No valid page content extracted for row {row_index}.")
                        continue

                    extracted_links = extract_links(html_content)
                    if not extracted_links:
                        print(f"[!] No valid person links extracted for row {row_index}.")
                        continue

                    ref_names = extract_reference_names(SHEET_ID, row_index)
                    if not ref_names:
                        print(f"[!] No reference names found in row {row_index} (cols D–J).")
                        continue

                    matched_results = match_entries(extracted_links, ref_names)

                    if matched_results:
                        print(f"[✓] Match found. Logging to row {row_index}.")
                        try:
                            log_matches_to_sheet(SHEET_ID, row_index, matched_results)
                            print(f"[✓] Successfully logged data for row {row_index}.")
                        except Exception as e:
                            print(f"[!] Error logging to Google Sheets for row {row_index}: {e}")
                    else:
                        print(f"[!] No match found in row {row_index}.")

                except Exception as e:
                    print(f"[!] Error processing row {row_index}: {e}")
                    continue

                delay_time = random.choice([x * 1.5 for x in range(1, 21)])
                print(f"[⏳] Waiting for {delay_time:.1f} seconds before next request...")
                await asyncio.sleep(delay_time)

        finally:
            if browser:
                await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
