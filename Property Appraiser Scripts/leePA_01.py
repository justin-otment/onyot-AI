import os
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
from google.oauth2.credentials import Credentials  # Correct import for OAuth2 credentials

# Google Sheets setup
SHEET_ID = '1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A'
SHEET_NAME = 'Raw Cape Coral - ArcGIS (lands)'

# Define file paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Authenticate with Google Sheets API
def authenticate_google_sheets():
    """Authenticate and return Google Sheets API service."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())  # Refresh token if expired
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())

    return build("sheets", "v4", credentials=creds)

# Fetch data from Google Sheets
def fetch_sheet_data():
    try:
        sheets_service = authenticate_google_sheets()
        sheet = sheets_service.spreadsheets()
        range_ = f"{SHEET_NAME}!A2501:A5000"
        result = sheet.values().get(spreadsheetId=SHEET_ID, range=range_).execute()
        return result.get("values", [])
    except Exception as e:
        print(f"Error fetching data from Google Sheets: {e}")
        return []

# Update multiple rows in Google Sheets in a single request
def batch_update_sheets(sheets_service, updates):
    """Batch update Google Sheets to optimize API calls."""
    if not updates:
        return

    body = {"valueInputOption": "RAW", "data": updates}
    sheets_service.spreadsheets().values().batchUpdate(spreadsheetId=SHEET_ID, body=body).execute()

# Setup Selenium WebDriver
def setup_driver():
    """Initialize and return a Selenium WebDriver instance."""
    options = webdriver.FirefoxOptions()
    options.add_argument("--headless")
    service = Service()
    return webdriver.Firefox(service=service, options=options)

# Main function to process the data
def fetch_data_and_update_sheet():
    sheet_data = fetch_sheet_data()
    if not sheet_data:
        print("No data found in Google Sheets.")
        return

    sheets_service = authenticate_google_sheets()
    driver = setup_driver()
    url = 'https://www.leepa.org/Search/PropertySearch.aspx'
    updates = []

    for i, row in enumerate(sheet_data, start=2501):
        owner = row[0] if row else None
        if not owner or owner.strip() == '':
            print(f"Skipping empty cell at row {i}")
            continue

        print(f"Processing Name: {owner}")

        try:
            driver.get(url)

            # Enter owner name and submit
            strap_input = WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.ID, "ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_STRAPTextBox"))
            )
            strap_input.send_keys(owner, Keys.RETURN)

            # Handle potential pop-ups
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID, "ctl00_BodyContentPlaceHolder_pnlIssues"))
                )
                warning_button = driver.find_element(By.ID, "ctl00_BodyContentPlaceHolder_btnWarning")
                warning_button.click()
            except:
                pass  # No pop-up found, continue normally

            time.sleep(5)

            # Get property details link
            href = WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_BodyContentPlaceHolder_WebTab1"]/div/div[1]/div[1]/table/tbody/tr/td[4]/div/div[1]/a'))
            ).get_attribute('href')
            driver.get(href)

            time.sleep(5)

            # Click image to reveal ownership details
            img_element = WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="divDisplayParcelOwner"]/div[1]/div/div[1]/a[2]/img'))
            )
            img_element.click()

            ownership_text = driver.find_element(By.XPATH, '//*[@id="ownershipDiv"]/div/ul').text
            additional_text = driver.find_element(By.XPATH, '//*[@id="divDisplayParcelOwner"]/div[1]/div/div[2]/div').text

            # Click Value tab and extract property value
            driver.find_element(By.ID, "ValuesHyperLink").click()
            property_value = WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="valueGrid"]/tbody/tr[2]/td[4]'))
            ).text

            building_info = driver.find_element(By.XPATH, '//*[@id="divDisplayParcelOwner"]/div[3]/table[1]/tbody/tr[3]/td').text
            full_site = driver.find_element(By.XPATH, '//*[@id="divDisplayParcelOwner"]/div[2]/div[3]').text

            # Add updates in batch
            updates.append({"range": f"{SHEET_NAME}!C{i}", "values": [[ownership_text]]})
            updates.append({"range": f"{SHEET_NAME}!D{i}", "values": [[additional_text]]})
            updates.append({"range": f"{SHEET_NAME}!E{i}", "values": [[property_value]]})
            updates.append({"range": f"{SHEET_NAME}!F{i}", "values": [[building_info]]})
            updates.append({"range": f"{SHEET_NAME}!S{i}", "values": [[full_site]]})

            # Batch update in chunks of 10 for efficiency
            if len(updates) >= 10:
                batch_update_sheets(sheets_service, updates)
                updates = []  # Reset updates batch

        except Exception as e:
            print(f"Error processing row {i}: {e}")

    # Final batch update for remaining data
    if updates:
        batch_update_sheets(sheets_service, updates)

    driver.quit()

if __name__ == "__main__":
    fetch_data_and_update_sheet()
