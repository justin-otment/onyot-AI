import re
import time
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import urllib3
from urllib3.exceptions import ProtocolError
import ssl
import time

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
url = 'https://egov.capecoral.gov/estpayoff/estpayoff.aspx?Strap='
response = make_request_with_retries(url)
print(response.data)


os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

# Disable SSL verification temporarily (use only for testing)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

# Google Sheets setup
SHEET_ID = '1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A'
SHEET_NAME = 'On-Market(Cape Coral Lots)'
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDENTIALS_PATH = os.path.join(os.getcwd(), "credentials.json")
TOKEN_PATH = os.path.join(os.getcwd(), "token.json")

# URLs
URL_1 = "https://egov.capecoral.gov/estpayoff/estpayoff.aspx?Strap="
URL_2 = "https://egov.capecoral.gov/estpayoff/PropertyRestrictions.aspx?STRAP="

def setup_edge_driver():
    """Set up Edge driver using webdriver-manager."""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")


    # Automatically download and install the Edge driver
    driver_path = EdgeChromiumDriverManager().install()

    # Setup service with the driver path
    service = Service(driver_path)

    # Return the Edge driver instance
    return webdriver.Edge(service=service, options=options)

def authenticate_google_sheets():
    """Authenticate and return a Google Sheets API service."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())
    return build("sheets", "v4", credentials=creds)

def clean_data(data):
    """Remove non-alphanumeric characters from the data."""
    return re.sub(r'[^a-zA-Z0-9]', '', data)

def fetch_data_from_google_sheets(sheets_service):
    """Fetch data from Google Sheets."""
    sheet = sheets_service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f'{SHEET_NAME}!A2:A179' 
    ).execute()
    return sheet.get('values', [])

def update_google_sheets(sheets_service, cell, value):
    """Update Google Sheets with the given value."""
    sheets_service.spreadsheets().values().update(
        spreadsheetId=SHEET_ID,
        range=cell,
        valueInputOption="RAW",
        body={"values": [[value]]}
    ).execute()


def navigate_and_extract(driver, url, xpath):
    """Navigate to the URL and perform web text extraction."""
    driver.get(url)
    try:
        # Wait for the page to load fully
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.XPATH, '/html'))
        )
        print(f"Page loaded successfully: {url}")

        # Extract multiple elements based on the provided XPath
        elements = driver.find_elements(By.XPATH, xpath)
        extracted_texts = [element.text for element in elements]
        print(f"Extracted texts: {extracted_texts}")  # Debugging line
        return extracted_texts

    except Exception as e:
        print(f"Error navigating to {url}: {e}")
        return []

def main():
    """Main function to drive the script."""
    sheets_service = authenticate_google_sheets()
    data = fetch_data_from_google_sheets(sheets_service)
    cleaned_data = [clean_data(item[0]) for item in data if item]

    driver = setup_edge_driver()

    try:
        for index, item in enumerate(cleaned_data):
            url1 = URL_1 + item
            url2 = URL_2 + item

            # Extract data from URL 1
            extracted_texts_url1 = navigate_and_extract(driver, url1, '//td[5]')
            total_sum = sum(float(re.sub(r'[^\d.]', '', text)) for text in extracted_texts_url1 if re.sub(r'[^\d.]', '', text))
            print(f"Total sum for {item}: {total_sum}")  # Debugging line
            update_google_sheets(sheets_service, f'{SHEET_NAME}!D{index + 2}', total_sum)

            # Extract data from URL 2
            extracted_texts_url2 = navigate_and_extract(driver, url2, '//*[@id="RadGrid1_ctl00__0"]/td[4]')
            if extracted_texts_url2:
                update_google_sheets(sheets_service, f'{SHEET_NAME}!I{index + 2}', extracted_texts_url2[0])

            # Optional: Add a delay between requests to avoid overwhelming the server
            time.sleep(2)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
