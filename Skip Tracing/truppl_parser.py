import os
import time
import json
import requests
import urllib3
import ssl
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib3.exceptions import ProtocolError
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# Define constants
GECKODRIVER_PATH = "C:\\GeckoDriver\\geckodriver.exe"  # Windows-compatible path
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

if not GOOGLE_CREDENTIALS_PATH or not os.path.exists(GOOGLE_CREDENTIALS_PATH):
    raise Exception(f"Google Sheets authentication failed: Credential file not found. Path: {GOOGLE_CREDENTIALS_PATH}")

# Disable SSL verification temporarily (use only for testing)
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

# Request with retries for webpage access
def make_request_with_retries(url, retries=3, backoff_factor=1):
    http = urllib3.PoolManager()
    attempt = 0
    while attempt < retries:
        try:
            response = http.request('GET', url)
            if response.status == 200:
                return response.data
        except ProtocolError as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            attempt += 1
            sleep_time = backoff_factor * (2 ** attempt)
            print(f"Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)
    raise Exception(f"Failed to fetch {url} after {retries} attempts.")

# Google Sheets setup
SHEET_ID = '1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A'
SHEET_NAME = 'Cape Coral - ArcGIS_LANDonly'

# Authenticate with Google Sheets API
def authenticate_google_sheets():
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH)
    return build("sheets", "v4", credentials=creds)

# Fetch and update data in Google Sheets
def fetch_data_and_update_sheet():
    sheets_service = authenticate_google_sheets()
    sheet = sheets_service.spreadsheets()

    names_range = f"{SHEET_NAME}!A2:A"
    dates_range = f"{SHEET_NAME}!E2:E"

    names_result = sheet.values().get(spreadsheetId=SHEET_ID, range=names_range).execute()
    dates_result = sheet.values().get(spreadsheetId=SHEET_ID, range=dates_range).execute()

    names_data = names_result.get("values", [])
    dates_data = dates_result.get("values", [])

    print(f"Fetched {len(names_data)} names and {len(dates_data)} date cells.")

    url = "https://www.leepa.org/Search/PropertySearch.aspx"

    # Verify URL availability before launching Selenium
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Error: Unable to fetch {url}. Status code: {response.status_code}")

    for i, (name_row, date_row) in enumerate(zip(names_data, dates_data), start=2):
        owner = name_row[0].strip() if name_row else ""
        sale_date = date_row[0].strip() if date_row else ""

        if sale_date or not owner:
            print(f"Skipping row {i}: sale_date={sale_date}, owner={owner}")
            continue

        print(f"Processing row {i}: Owner = {owner}")

        options = webdriver.FirefoxOptions()
        options.add_argument("--headless")

        service = Service(GECKODRIVER_PATH)  # Ensure path works in Windows
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
            except:
                print("No warning popup.")

            href = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_BodyContentPlaceHolder_WebTab1"]/div/div[1]/div[1]/table/tbody/tr/td[4]/div/div[1]/a'))
            ).get_attribute('href')
            driver.get(href)

            img_element = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '#SalesHyperLink > img'))
            )
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", img_element)
            time.sleep(1)
            driver.execute_script("arguments[0].click();", img_element)
            time.sleep(1)

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

        except Exception as e:
            print(f"Error processing row {i}: {e}")

        finally:
            driver.quit()

if __name__ == "__main__":
    fetch_data_and_update_sheet()
