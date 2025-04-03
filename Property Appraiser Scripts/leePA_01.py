import os
import time
import json
import ssl
import urllib3
import random
from urllib3.exceptions import ProtocolError
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

# Google Sheets API Setup
SHEET_ID = '1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A'
SHEET_NAME = 'Cape Coral - ArcGIS_LANDonly'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# File Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")

# Disable SSL verification temporarily (for testing only)
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Authenticate with Google Sheets API
def authenticate_google_sheets():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    return build("sheets", "v4", credentials=creds)

# Fetch Google Sheets data
def fetch_google_sheets_data():
    try:
        sheets_service = authenticate_google_sheets()
        sheet = sheets_service.spreadsheets()
        result = sheet.values().get(spreadsheetId=SHEET_ID, range=f"{SHEET_NAME}!A2:A2500").execute()
        return result.get("values", [])
    except Exception as e:
        print(f"Error fetching data from Google Sheets: {e}")
        return []

# Initialize Selenium WebDriver
def setup_driver():
    options = webdriver.FirefoxOptions()
    options.add_argument("--headless")
    return webdriver.Firefox(service=Service(), options=options)

# Extract property details
def extract_property_details(driver, owner):
    url = "https://www.leepa.org/Search/PropertySearch.aspx"
    driver.get(url)

    try:
        strap_input = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_STRAPTextBox"))
        )
        strap_input.send_keys(owner, Keys.RETURN)

        # Handle warning pop-up if it appears
        try:
            WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.ID, "ctl00_BodyContentPlaceHolder_pnlIssues"))
            )
            driver.find_element(By.ID, "ctl00_BodyContentPlaceHolder_btnWarning").click()
        except:
            pass  # No pop-up found

        # Click the first property link
        href = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_BodyContentPlaceHolder_WebTab1"]/div/div[1]/div[1]/table/tbody/tr/td[4]/div/div[1]/a'))
        ).get_attribute('href')
        driver.get(href)

        # Extract ownership details
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "ownershipDiv")))
        driver.find_element(By.XPATH, '//*[@id="divDisplayParcelOwner"]/div[1]/div/div[1]/a[2]/img').click()
        ownership_text = driver.find_element(By.XPATH, '//*[@id="ownershipDiv"]/div/ul').text or ""
        additional_text = driver.find_element(By.XPATH, '//*[@id="divDisplayParcelOwner"]/div[1]/div/div[2]/div').text or ""

        # Extract property value
        driver.find_element(By.ID, "ValuesHyperLink").click()
        property_value = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="valueGrid"]/tbody/tr[2]/td[4]'))
        ).text or ""

        # Extract building and full site info
        building_info = driver.find_element(By.XPATH, '//*[@id="divDisplayParcelOwner"]/div[3]/table[1]/tbody/tr[3]/td').text or ""
        full_site = driver.find_element(By.XPATH, '//*[@id="divDisplayParcelOwner"]/div[2]/div[3]').text or ""

        return ownership_text, additional_text, property_value, building_info, full_site

    except Exception as e:
        print(f"Error extracting data for {owner}: {e}")
        return "", "", "", "", ""

# Batch update Google Sheets
def update_google_sheets(sheets_service, updates):
    body = {
        "valueInputOption": "RAW",
        "data": updates
    }

    for attempt in range(3):  # Retry up to 3 times
        try:
            sheets_service.spreadsheets().values().batchUpdate(
                spreadsheetId=SHEET_ID, body=body
            ).execute()
            return
        except Exception as e:
            print(f"Error updating Google Sheets, attempt {attempt+1}: {e}")
            time.sleep(2 + random.uniform(0, 2))  # Add slight randomness to avoid throttling

# Main function
def fetch_data_and_update_sheet():
    data = fetch_google_sheets_data()
    if not data:
        print("No data found in Google Sheets.")
        return

    driver = setup_driver()
    sheets_service = authenticate_google_sheets()
    updates = []

    for i, row in enumerate(data, start=2):
        owner = row[0].strip() if row else None
        if not owner:
            print(f"Skipping empty row {i}")
            continue

        print(f"Processing: {owner}")

        ownership_text, additional_text, property_value, building_info, full_site = extract_property_details(driver, owner)

        if any([ownership_text, additional_text, property_value, building_info, full_site]):
            updates.append({
                "range": f"{SHEET_NAME}!C{i}:G{i}",  # Adjust based on required columns
                "majorDimension": "ROWS",
                "values": [[ownership_text, additional_text, property_value, building_info, full_site]]
            })
            print(f"Queued update for row {i}")

    if updates:
        update_google_sheets(sheets_service, updates)
        print("Google Sheets updated successfully.")

    driver.quit()

# Run the script
if __name__ == "__main__":
    fetch_data_and_update_sheet()
