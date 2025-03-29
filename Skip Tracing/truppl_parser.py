import os
import random
import asyncio
import undetected_chromedriver as uc
from performSearch_TruPpl import perform_search, find_best_match
from utilities import increment_value_randomly, get_safe, random_delay
from csvHandler_beta import initialize_csv, append_to_csv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from selenium.webdriver.support.ui import WebDriverWait
import re
import urllib3
import ssl
import time
from urllib3.exceptions import ProtocolError
import requests
from fake_useragent import UserAgent
import gspread
import difflib
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import logging
from rapidfuzz import fuzz

logging.basicConfig(filename="error_log.txt", level=logging.ERROR)

# Initialize the UserAgent object
ua = UserAgent()

# Function to make a request with a random user agent
def fetch_url(url):
    headers = {
        'User-Agent': ua.random  # Generate a random user agent
    }
    response = requests.get(url, headers=headers)
    return response

# Example usage
url = 'https://www.truepeoplesearch.com/'
response = fetch_url(url)
print(f"Status Code: {response.status_code}")
print(f"Response Text (First 500 chars):\n{response.text[:500]}")

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
url = 'https://www.truepeoplesearch.com/'
response = make_request_with_retries(url)
print(response.data)

os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

# Disable SSL verification temporarily (use only for testing)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

# Define file paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")

# Constants
USER_DATA_DIR = "C:\\Users\\DELL\\AppData\\Local\\Google\\Chrome\\User Data"
PROFILE_DIRECTORY = "Profile 1"
SHEET_ID = "1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A"
SHEET_NAME = "Cape Coral - ArcGIS"

# Set up undetected chromedriver options with local profile
options = uc.ChromeOptions()
options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
options.add_argument(f"--profile-directory={PROFILE_DIRECTORY}")
options.add_argument("--start-maximized")

def authenticate_google_sheets():
    """Authenticate with Google Sheets API."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(
            TOKEN_PATH, ["https://www.googleapis.com/auth/spreadsheets"]
        )
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, ["https://www.googleapis.com/auth/spreadsheets"]
            )
            creds = flow.run_local_server(port=53221)
            with open(TOKEN_PATH, "w") as token:
                token.write(creds.to_json())
    return gspread.authorize(creds)


def get_sheet_data(sheet_id, sheet_name, cell_range):
    """
    Fetch data from a Google Sheets range.
    NOTE: `cell_range` should be something like 'A1:A100', NOT 'SheetName!A1:A100'.
    """
    try:
        service = authenticate_google_sheets()
        sheet = service.open_by_key(sheet_id)
        worksheet = sheet.worksheet(sheet_name)
        result = worksheet.get(cell_range)
        return result
    except Exception as e:
        print(f"Error fetching data from Google Sheets: {e}")
        return

def update_google_sheet(sheet, row, href_value, column_range='AD2:AD'):
    """Update the Google Sheet with the extracted href."""
    sheet.update_cell(row, 30, href_value)  # Column AD is the 30th column
    print(f"✅ Row {row} updated successfully with href: {href_value}")

def normalize_text(text):
    """Normalize text by lowercasing and removing non-alphanumeric characters."""
    return re.sub(r'[^a-zA-Z0-9]', '', text.strip().lower())

def get_match_percentage(str1, str2):
    """Calculate similarity using token set ratio (better for names with swapped/missing parts)."""
    return fuzz.token_set_ratio(str1, str2)

def split_multiline_names(multiline_text):
    """Splits a multi-line string into a list of trimmed lines."""
    return [line.strip() for line in multiline_text.splitlines() if line.strip()]


def extract_best_match(page_text, target_names, threshold=50):
    """
    Compare a page text (one div.h4) to all target names and find the best match.
    If any match exceeds the threshold, return it.
    """
    best_match = None
    best_match_percentage = 0

    for target_name in target_names:
        match_percentage = get_match_percentage(normalize_text(page_text), normalize_text(target_name))
        if match_percentage > best_match_percentage and match_percentage >= threshold:
            best_match_percentage = match_percentage
            best_match = target_name

    return best_match


async def process_url(driver, url, target_name_block, sheet, row):
    try:
        driver.get(url)
        await random_delay(2, 5)

        time.sleep(3)

        items = WebDriverWait(driver, 60).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div.content-center'))
        )

        if not items:
            print(f"No items found on page for URL: {url}")
            return

        for item in items:
            try:
                text_element = WebDriverWait(driver, 60).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div.h4'))
                )
                text = text_element.text.strip()

                # Match against the multi-line target name block
                matched_name = extract_best_match(text, target_name_block)

                if matched_name:
                    text_element.get_attribute('href')
                    print(f"✅ Best match found: {matched_name}")

                    href_element = WebDriverWait(driver, 60).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, 'a'))
                    )
                    href_value = href_element.get_attribute('href')

                    if href_value:
                        update_google_sheet(sheet, row, href_value)
                        print(f"✅ Extracted href: {href_value}")
                        return  # Stop after first successful match

                    else:
                        print(f"⚠️ No href found for match: {matched_name}")

            except Exception as item_error:
                print(f"⚠️ Error processing item for URL {url}: {item_error}")

        print(f"⚠️ No suitable matches found for URL: {url}")

    except Exception as e:
        print(f"❌ Error processing URL {url}: {e}")


async def main():
    driver = uc.Chrome(
        options=options,
        version_main=133  # Match your installed Chrome version
    )
    processed_queries = set()

    try:
        # Fetch data using the new get_sheet_data function for URL columns
        urls_z = get_sheet_data(SHEET_ID, SHEET_NAME, "Z2:Z")
        urls_ac = get_sheet_data(SHEET_ID, SHEET_NAME, "AC2:AC")
        target_names = get_sheet_data(SHEET_ID, SHEET_NAME, "C2:C")
        
        # Authenticate once for updates
        sheet_service = authenticate_google_sheets()
        sheet = sheet_service.open_by_key(SHEET_ID).worksheet(SHEET_NAME)

        # Loop through each URL in column Z and AC and process them
        for i, url in enumerate(urls_z):
            if not url or i >= len(urls_ac):
                continue

            url_value_z = url[0]
            url_value_ac = urls_ac[i][0]
            target_name_block = target_names[i][0]  # Full multi-line name block from column C

            if url_value_z:
                await process_url(driver, url_value_z, target_name_block, sheet, i + 2)

            if url_value_ac:
                await process_url(driver, url_value_ac, target_name_block, sheet, i + 2)

            await random_delay(2, 30)


    except Exception as e:
        logging.error("Error processing URL %s", url, exc_info=True)
    finally:
        driver.quit()

if __name__ == "__main__":
    asyncio.run(main())
