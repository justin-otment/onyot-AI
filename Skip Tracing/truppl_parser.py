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
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Define constants
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GECKODRIVER_PATH = "C:\\GeckoDriver\\geckodriver.exe"

# Disable SSL verification temporarily (use only for testing)
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

SERVICE_ACCOUNT_PATH = os.path.join(BASE_DIR, "service-account.json")  # Path to your service account file

def authenticate_google_sheets():
    if not os.path.exists(SERVICE_ACCOUNT_PATH):
        raise Exception(f"Google Sheets authentication failed: Service account file not found at {SERVICE_ACCOUNT_PATH}")

    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    
    return build("sheets", "v4", credentials=creds)

# Fetch and update data in Google Sheets
def fetch_data_and_update_sheet():
    print("Authenticating with Google Sheets API...")
    sheets_service = authenticate_google_sheets()
    print("Authentication successful!")
    sheet = sheets_service.spreadsheets()

    names_range = "Cape Coral - ArcGIS_LANDonly!A2:A2500"
    dates_range = "Cape Coral - ArcGIS_LANDonly!E2:E2500"

    try:
        print("Fetching data from Google Sheets...")
        names_result = sheet.values().get(spreadsheetId="1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A", range=names_range).execute()
        dates_result = sheet.values().get(spreadsheetId="1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A", range=dates_range).execute()
    except Exception as e:
        print(f"Error fetching data from Google Sheets: {e}")
        return

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
            except:
                print("No warning popup.")

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
                spreadsheetId="1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A",
                range=f"Cape Coral - ArcGIS_LANDonly!E{i}",
                valueInputOption="RAW",
                body={"values": [[sale_date]]}
            ).execute()

            sheet.values().update(
                spreadsheetId="1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A",
                range=f"Cape Coral - ArcGIS_LANDonly!F{i}",
                valueInputOption="RAW",
                body={"values": [[sale_amount]]}
            ).execute()

        except Exception as e:
            print(f"Error processing row {i}: {e}")

        finally:
            driver.quit()

if __name__ == "__main__":
    fetch_data_and_update_sheet()
