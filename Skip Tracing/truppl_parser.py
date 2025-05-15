import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import urllib3
from urllib3.exceptions import ProtocolError
import ssl
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import os
credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
print(f"Credentials Path: {credentials_path}")

# Define constants
GECKODRIVER_PATH = "/usr/local/bin/geckodriver"

# Request with retries
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
    creds = None
    token_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if token_path and os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, ['https://www.googleapis.com/auth/spreadsheets'])

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise Exception("Google Sheets authentication failed.")

    return build("sheets", "v4", credentials=creds)

def fetch_data_and_update_sheet():
    try:
        sheets_service = authenticate_google_sheets()
        sheet = sheets_service.spreadsheets()

        names_range = f"{SHEET_NAME}!A2:A"
        dates_range = f"{SHEET_NAME}!E2:E"

        names_result = sheet.values().get(spreadsheetId=SHEET_ID, range=names_range).execute()
        dates_result = sheet.values().get(spreadsheetId=SHEET_ID, range=dates_range).execute()

        names_data = names_result.get("values", [])
        dates_data = dates_result.get("values", [])

        print(f"Fetched {len(names_data)} names and {len(dates_data)} date cells.")

    except Exception as e:
        print(f"Error fetching data from Google Sheets: {e}")
        return

    url = 'https://www.leepa.org/Search/PropertySearch.aspx'

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
            strap_input = WebDriverWait(driver, 60).until(
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

            sale_date = WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="SalesDetails"]/div[3]/table/tbody/tr[2]/td[2]'))
            ).text
            sale_amount = WebDriverWait(driver, 60).until(
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
