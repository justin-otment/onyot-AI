import os
import json
import base64
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Constants
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENCODED_JSON_PATH = os.path.join(BASE_DIR, "service-account_base64.txt")
GECKODRIVER_PATH = "C:\\GeckoDriver\\geckodriver.exe"

SHEET_ID = "1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A"
SHEET_NAME = "Cape Coral - ArcGIS_LANDonly"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SEARCH_URL = "https://www.leepa.org/Search/PropertySearch.aspx"

# Decode service account
def load_credentials():
    try:
        with open(ENCODED_JSON_PATH, "r") as f:
            encoded = f.read().strip()
        if not all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=" for c in encoded):
            raise ValueError("Invalid base64 content in service-account_base64.txt")
        json_data = json.loads(base64.b64decode(encoded).decode("utf-8"))

        required_keys = ["type", "project_id", "private_key", "client_email"]
        if not all(k in json_data for k in required_keys):
            raise KeyError("Missing required fields in decoded service account JSON")

        return json_data
    except Exception as e:
        raise RuntimeError(f"Failed to load credentials: {e}")

# Setup Google Sheets client
def authenticate_google_sheets():
    creds_json = load_credentials()
    creds = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)

# Scraping logic
def fetch_data_and_update_sheet():
    print("Authenticating with Google Sheets...")
    service = authenticate_google_sheets()
    sheet = service.spreadsheets()
    print("Authentication successful.")

    names_range = f"{SHEET_NAME}!A2:A2500"
    dates_range = f"{SHEET_NAME}!E2:E2500"

    try:
        print("Fetching sheet data...")
        names = sheet.values().get(spreadsheetId=SHEET_ID, range=names_range).execute().get("values", [])
        dates = sheet.values().get(spreadsheetId=SHEET_ID, range=dates_range).execute().get("values", [])
    except HttpError as e:
        raise RuntimeError(f"Google Sheets API error: {e}")

    print(f"Fetched {len(names)} names and {len(dates)} date cells.")

    # Test LEEPA availability
    try:
        requests.get(SEARCH_URL, timeout=10).raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"LEEPA site unreachable: {e}")

    for i, (name_row, date_row) in enumerate(zip(names, dates), start=2):
        owner = name_row[0].strip() if name_row else ""
        sale_date = date_row[0].strip() if date_row else ""

        if not owner or sale_date:
            print(f"Skipping row {i}: owner={owner}, sale_date={sale_date}")
            continue

        print(f"Processing row {i}: {owner}")
        options = webdriver.FirefoxOptions()
        options.add_argument("--headless")

        driver = webdriver.Firefox(service=Service(GECKODRIVER_PATH), options=options)

        try:
            driver.get(SEARCH_URL)

            search_input = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_STRAPTextBox"))
            )
            search_input.send_keys(owner, Keys.RETURN)

            try:
                warning_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "ctl00_BodyContentPlaceHolder_btnWarning"))
                )
                warning_btn.click()
            except TimeoutException:
                pass  # No warning popup

            href = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_BodyContentPlaceHolder_WebTab1"]/div/div[1]/div[1]/table/tbody/tr/td[4]/div/div[1]/a'))
            ).get_attribute("href")

            driver.get(href)

            sale_date = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="SalesDetails"]/div[3]/table/tbody/tr[2]/td[2]'))
            ).text

            sale_amount = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="SalesDetails"]/div[3]/table/tbody/tr[2]/td[1]'))
            ).text

            sheet.values().update(
                spreadsheetId=SHEET_ID,
                range=f"{SHEET_NAME}!E{i}",
                valueInputOption="RAW",
                body={"values": [[sale_date]]}
            ).execute()

            sheet.values().update(
                spreadsheetId=SHEET_ID,
                range=f"{SHEET_NAME}!F{i}",
                valueInputOption="RAW",
                body={"values": [[sale_amount]]}
            ).execute()

            print(f"Updated row {i}: {sale_date}, {sale_amount}")

        except (TimeoutException, NoSuchElementException) as e:
            print(f"Skipping row {i} due to error: {e}")
        finally:
            driver.quit()

if __name__ == "__main__":
    fetch_data_and_update_sheet()
