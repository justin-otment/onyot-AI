import os
import json
import base64
import time
import requests
import urllib3
import ssl
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Define constants
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENCODED_JSON_PATH = os.path.join(BASE_DIR, "service-account_base64.txt")
GECKODRIVER_PATH = "C:\\GeckoDriver\\geckodriver.exe"

# Read and decode service account JSON
try:
    with open(ENCODED_JSON_PATH, "r") as file:
        encoded_json = file.read().strip()

    if not encoded_json or not all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=" for c in encoded_json):
        raise Exception("Error: service-account_base64.txt contains invalid base64 characters!")

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

# Google Sheets setup
SHEET_ID = "1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A"
SHEET_NAME = "Cape Coral - ArcGIS_LANDonly"  # No need for additional quoting
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Corrected range formatting
names_range = f"{SHEET_NAME}!A2:A2500"
dates_range = f"{SHEET_NAME}!E2:E2500"

# Authenticate with Google Sheets API
def authenticate_google_sheets():
    try:
        creds = Credentials.from_service_account_info(json_data, scopes=SCOPES)
        return build("sheets", "v4", credentials=creds)
    except Exception as e:
        raise Exception(f"Error authenticating Google Sheets API: {e}")

# Fetch and update data in Google Sheets
def fetch_data_and_update_sheet():
    print("Authenticating with Google Sheets API...")
    sheets_service = authenticate_google_sheets()
    print("Authentication successful!")
    sheet = sheets_service.spreadsheets()

    if not SHEET_ID or not SHEET_NAME:
        raise Exception("Error: SHEET_ID or SHEET_NAME is not defined!")

    names_range = f"{SHEET_NAME}!A2:A2500"
    dates_range = f"{SHEET_NAME}!E2:E2500"

    try:
        print("Fetching sheet data...")
        names_result = sheet.values().get(spreadsheetId=SHEET_ID, range=names_range).execute()
        dates_result = sheet.values().get(spreadsheetId=SHEET_ID, range=dates_range).execute()
    except HttpError as e:
        raise RuntimeError(f"Google Sheets API error: {e}")

    names_data = names_result.get("values", [])
    dates_data = dates_result.get("values", [])

    print(f"Fetched {len(names_data)} names and {len(dates_data)} date cells.")

    url = "https://www.leepa.org/Search/PropertySearch.aspx"

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Error: Unable to fetch {url}. Reason: {e}")

    for i, (name_row, date_row) in enumerate(zip(names_data, dates_data), start=2):
        owner = name_row[0].strip() if name_row else ""
        sale_date = date_row[0].strip() if date_row else ""

        if sale_date or not owner:
            print(f"Skipping row {i}: sale_date={sale_date}, owner={owner}")
            continue

        print(f"Processing row {i}: Owner = {owner}")

        options = webdriver.FirefoxOptions()
        options.add_argument("--headless")

        service = Service(GECKODRIVER_PATH)
        driver = webdriver.Firefox(service=service, options=options)

        try:
            driver.get(url)

            strap_input = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID, "ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_STRAPTextBox"))
            )
            strap_input.send_keys(owner, Keys.RETURN)

            try:
                warning_button = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "ctl00_BodyContentPlaceHolder_btnWarning"))
                )
                warning_button.click()
            except TimeoutException:
                print("No warning popup detected.")

            href = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_BodyContentPlaceHolder_WebTab1"]/div/div[1]/div[1]/table/tbody/tr/td[4]/div/div[1]/a'))
            ).get_attribute('href')
            driver.get(href)

            sale_date = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="SalesDetails"]/div[3]/table/tbody/tr[2]/td[2]'))
            ).text
            sale_amount = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="SalesDetails"]/div[3]/table/tbody/tr[2]/td[1]'))
            ).text

            sheet.values().update(
                spreadsheetId=SHEET_ID,
                range=f"{SHEET_NAME_QUOTED}!E{i}",
                valueInputOption="RAW",
                body={"values": [[sale_date]]}
            ).execute()

            sheet.values().update(
                spreadsheetId=SHEET_ID,
                range=f"{SHEET_NAME_QUOTED}!F{i}",
                valueInputOption="RAW",
                body={"values": [[sale_amount]]}
            ).execute()

        except TimeoutException:
            print(f"Error: Timeout waiting for data in row {i}. Skipping...")
        except NoSuchElementException:
            print(f"Error: Expected element missing in row {i}. Skipping...")
        except Exception as e:
            print(f"Error processing row {i}: {e}")
        finally:
            driver.quit()

if __name__ == "__main__":
    fetch_data_and_update_sheet()
