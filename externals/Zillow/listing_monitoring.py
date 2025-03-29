import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from undetected_chromedriver import Chrome, ChromeOptions
import ssl
import time
import urllib3
from urllib3.exceptions import ProtocolError
from fake_useragent import UserAgent



os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

# Disable SSL verification temporarily (use only for testing)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

# Google Sheets setup
SHEET_ID = '1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A'
SHEET_NAME = 'On-Market(Cape Coral Lots)'

# Define file paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# Authenticate with Google Sheets API
def authenticate_google_sheets():
    """Authenticate with Google Sheets API."""
    creds = None
    # Check if the token file exists
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    # If no valid credentials, allow the user to login via OAuth
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())  # Refresh token if expired
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)

    # Save the credentials for the next run
    with open(TOKEN_PATH, "w") as token:
        token.write(creds.to_json())

    return build("sheets", "v4", credentials=creds)

# Fetch data from Google Sheets
def fetch_urls_from_sheet():
    sheets_service = authenticate_google_sheets()
    sheet = sheets_service.spreadsheets()
    range_ = f"{SHEET_NAME}!B2:B"
    result = sheet.values().get(spreadsheetId=SHEET_ID, range=range_).execute()
    return result.get("values", [])

# Update Google Sheets
def update_sheet(values, row, column_name):
    sheets_service = authenticate_google_sheets()
    sheet = sheets_service.spreadsheets()
    sheet.update(
        spreadsheetId=SHEET_ID,
        range=f"{SHEET_NAME}!{column_name}{row}",
        valueInputOption="RAW",
        body={"values": [[values]]}
    ).execute()

# Constants
USER_DATA_DIR = "C:\\Users\\DELL\\AppData\\Local\\Google\\Chrome\\User Data"
PROFILE_DIRECTORY = "Profile 1"

def setup_chrome_driver():
    """Set up Chrome driver with custom options."""
    options = ChromeOptions()
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument(f"--remote-debugging-port=53221")
    options.add_argument(f"--profile-directory={PROFILE_DIRECTORY}")
    options.add_argument(f"--start-maximized")
    options.add_argument('--disable-blink-features=AutomationControlled')
    return Chrome(options=options)

def scrape_and_update(urls):
    driver = setup_chrome_driver()

    for i, url in enumerate(urls, start=2):  # Skip the header row
        driver.get(url[0])
        
        # Wait for the main element to be visible
        main_element = WebDriverWait(driver,60).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#search-detail-lightbox > div.sc-kIRMQU.kirwLy > div:nth-child(2) > div.styles__StyledContentWrapper-fshdp-8-106-0__sc-112i4yx-0.lnDExK.layout-wrapper > section > div.layout-container-desktop > div.layout-content-container > div > div > div")))

        # Extract and update Listing Price
        listing_price = main_element.find_element(By.CSS_SELECTOR, "#search-detail-lightbox > div.sc-kIRMQU.kirwLy > div:nth-child(2) > div.styles__StyledContentWrapper-fshdp-8-106-0__sc-112i4yx-0.lnDExK.layout-wrapper > section > div.layout-container-desktop > div.layout-content-container > div > div > div > div:nth-child(2) > div > div > div > div > div > div:nth-child(1) > div.Flex-c11n-8-106-0__sc-n94bjd-0.gGcMoZ > span > div > span > span").text
        update_sheet(listing_price, i, "Listing Price")

        # Extract and update Lot Size
        lot_size = main_element.find_element(By.CSS_SELECTOR, "#search-detail-lightbox > div.sc-kIRMQU.kirwLy > div:nth-child(2) > div.styles__StyledContentWrapper-fshdp-8-106-0__sc-112i4yx-0.lnDExK.layout-wrapper > section > div.layout-container-desktop > div.layout-content-container > div > div > div > div:nth-child(4) > div > div > div > div:nth-child(3) > span").text
        update_sheet(lot_size, i, "Lot Size")

        # Extract and update Days on Zillow
        days_on_zillow = main_element.find_element(By.CSS_SELECTOR, "#search-detail-lightbox > div.sc-ciyUsT.BWeTa > div:nth-child(2) > div.styles__StyledContentWrapper-fshdp-8-106-0__sc-112i4yx-0.lnDExK.layout-wrapper > section > div > div.layout-content-container > div.layout-static-column-container > div > div > div:nth-child(6) > div > div > dl > dt:nth-child(1) > strong").text
        update_sheet(days_on_zillow, i, "Days on Zillow")

        # Extract and update Listing Agent
        listing_agent = main_element.find_element(By.CSS_SELECTOR, "#search-detail-lightbox > div.sc-ciyUsT.BWeTa > div:nth-child(2) > div.styles__StyledContentWrapper-fshdp-8-106-0__sc-112i4yx-0.lnDExK.layout-wrapper > section > div > div.layout-content-container > div.layout-static-column-container > div > div > div:nth-child(7) > div > div > div > div > div.Flex-c11n-8-106-0__sc-n94bjd-0.eHTvmQ > div > div > p:nth-child(1) > span:nth-child(1)").text
        update_sheet(listing_agent, i, "Listing Agent")

        # Extract and update Contact
        contact = main_element.find_element(By.CSS_SELECTOR, "#search-detail-lightbox > div.sc-ciyUsT.BWeTa > div:nth-child(2) > div.styles__StyledContentWrapper-fshdp-8-106-0__sc-112i4yx-0.lnDExK.layout-wrapper > section > div > div.layout-content-container > div.layout-static-column-container > div > div > div:nth-child(7) > div > div > div > div > div.Flex-c11n-8-106-0__sc-n94bjd-0.eHTvmQ > div > div > p:nth-child(1) > span:nth-child(2)").text
        update_sheet(contact, i, "Contact")

    driver.quit()

if __name__ == "__main__":
    urls = fetch_urls_from_sheet()
    scrape_and_update(urls)
