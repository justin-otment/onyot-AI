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
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# Google Sheets setup
SHEET_ID = '1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A'
SHEET_NAME = 'Cape Coral - Vacant Lands'
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDENTIALS_PATH = os.path.join(os.getcwd(), "credentials.json")
TOKEN_PATH = os.path.join(os.getcwd(), "token.json")

# URL
URL = "https://www.capecoral.gov/uep/find_your_utility_extension_area.php"

def setup_edge_driver():
    """Set up Edge driver using webdriver-manager."""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")

    # Automatically download and install the Edge driver
    driver_path = EdgeChromiumDriverManager().install()

    # Setup service with the driver path
    service = Service(driver_path)

    # Return the Edge driver instance
    return webdriver.Edge(service=service, options=options)

# Perform human-like mouse movement
async def human_like_mouse_movement(driver, element):
    """Simulate human-like mouse movement to an element."""
    actions = ActionChains(driver)
    actions.move_to_element(element).perform()

def authenticate_google_sheets():
    """Authenticate and return a Google Sheets API service."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

    # Check if credentials are valid or expired
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())

    return build("sheets", "v4", credentials=creds)

def fetch_data_from_google_sheets(sheets_service):
    """Fetch data from Google Sheets."""
    sheet = sheets_service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f'{SHEET_NAME}!A2:A'
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

def navigate_and_extract(driver, url, input_value):
    """Navigate to the URL, scroll to the element, input value, and perform web text extraction."""
    driver.get(url)
    try:
        # Wait for the page to load fully
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, '/html'))
        )
        print(f"Page loaded successfully: {url}")

        # Scroll down a quarter of the page
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight / 4);")
        time.sleep(2)  # Wait for the scroll to complete

        # Locate the parent element
        parent_element = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="main"]/div/div/div[2]/section'))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", parent_element)
        time.sleep(2)  # Wait for the element to come into view
        print(f"Scrolled to parent element: {parent_element}")

        # Perform a click at coordinates (626, 454) and send keys
        print("Attempting to send keys at coordinates (626, 454)...")
        actions = webdriver.ActionChains(driver)
        actions.move_by_offset(786, 414).click()
        actions.send_keys(Keys.TAB).send_keys(input_value).perform()
        actions.send_keys(Keys.TAB).send_keys(Keys.ENTER).perform()
        print(f"Input value: {input_value}, Entered")

        submit = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, '//*[@id="Name"]/input[2]'))
        )
        driver.execute_script("arguments[0].scrollIntoView();", submit)
        human_like_mouse_movement(driver, submit) 
        submit.click()
        
        print(f"button: {submit}, successfully clicked")

    except Exception as e:
        print(f"Error navigating to {url}: {e}")
        return None

def main():
    """Main function to drive the script."""
    sheets_service = authenticate_google_sheets()
    data = fetch_data_from_google_sheets(sheets_service)
    input_data = [item[0] for item in data if item]

    driver = setup_edge_driver()

    try:
        for index, item in enumerate(input_data):
            url = URL

            # Extract data from the URL
            extracted_text = navigate_and_extract(driver, url, item)
            # Extract the text from the input element (if needed)
            extracted_text = WebDriverWait(driver, 30).until(
                EC.visibility_of_element_located((By.XPATH,'//*[@id="lblResults"]/table/tbody/tr[2]/td[2]')))
        
            print(f"Extracted text: {extracted_text}")  # Debugging line
            return extracted_text
            # Update Google Sheets with the extracted text
        if extracted_text:
                update_google_sheets(sheets_service, f'{SHEET_NAME}!AH{index + 2}', extracted_text)


    finally:
        driver.quit()

if __name__ == "__main__":
    main()
