import time
import subprocess
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from undetected_chromedriver import Chrome, ChromeOptions
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import os
from googleapiclient.errors import HttpError



# Filepath for AHK script to activate NordVPN extension
NORD_AHK_SCRIPT = "C:\\Users\\DELL\\Documents\\Onyot.ai\\Lead_List-Generator\\python tests\\externals\\VPNs\\nord.ahk"

# Function to trigger NordVPN Chrome extension via AHK
def trigger_nordvpn_extension():
    """Run the AHK script to activate the NordVPN Chrome extension."""
    try:
        subprocess.run(["C:\\Program Files\\AutoHotkey\\AutoHotkey.exe", NORD_AHK_SCRIPT], check=True)
        print("🔐 NordVPN Chrome extension triggered successfully.")
        time.sleep(10)  # Give it time to connect
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Failed to trigger NordVPN extension - {e}")
        raise

# Constants
SHEET_ID = '1QoXt-xWWbWJ9MoHM3WbjGR9q33u85dbXF6RsQ2-qdqw'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
CREDENTIALS_PATH = r'C:\Users\DELL\Documents\Onyot.ai\Lead_List-Generator\python tests\externals\Zillow\credentials.json'
TOKEN_PATH = r'C:\Users\DELL\Documents\Onyot.ai\Lead_List-Generator\python tests\externals\Zillow\token.json'


def get_credentials():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    return creds

def fetch_google_sheet_data(sheetID):
    creds = get_credentials()
    service = build('sheets', 'v4', credentials=creds)
    try:
        result = service.spreadsheets().values().get(spreadsheetId=SHEET_ID, range='A2:D20000').execute()
        return result.get('values', [])
    except HttpError as error:
        print(f"Error fetching Google Sheets data: {error}")
        return []

# Set up Chrome WebDriver with custom user profile
USER_DATA_DIR = "C:\\Users\\DELL\\AppData\\Local\\Google\\Chrome\\User Data"
PROFILE_DIRECTORY = "Profile 1"

def setup_chrome_driver():
    """Set up Chrome driver with user profile (for Chrome extension use)."""
    options = ChromeOptions()
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument(f"--profile-directory={PROFILE_DIRECTORY}")
    options.add_argument("--remote-debugging-port=53221")
    options.add_argument("--start-maximized")
    driver = Chrome(options=options)
    return driver

# Selenium wait utility
def wait_for_element(driver, css_selector, timeout=60):
    """Wait for element to be clickable."""
    return WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((By.CSS_SELECTOR, css_selector)))

# Perform the selenium actions to fill and submit the petition form
def perform_selenium_actions(driver, first_name, last_name, email, zip_code):
    """Perform the Selenium actions to fill out and submit the form."""
    driver.get("https://www.change.org/p/make-miami-affordable")

    # Fill the form
    wait_for_element(driver, "#signform-first-name-input").send_keys(first_name)
    wait_for_element(driver, "#signform-last-name-input").send_keys(last_name)
    wait_for_element(driver, "#signform-email-input").send_keys(email)
    wait_for_element(driver, "#signform-city-input").send_keys("Miami")
    wait_for_element(driver, "#signform-postal-code-input").send_keys(zip_code)

    # Open the state dropdown and select Florida (11th option)
    wait_for_element(driver, "#rootApp > div.corgi-1yz7e9k > div > div > div > div:nth-child(1) > div.corgi-bpqmx0 > div.corgi-1b6lf06 > div.corgi-1dpcosh > div > form > div:nth-child(4) > div > button > span > svg").click()
    wait_for_element(driver, "#signform-state-input > option:nth-child(11)").click()

    # Submit the form
    wait_for_element(driver, "#rootApp > div.corgi-1yz7e9k > div > div > div > div:nth-child(1) > div.corgi-bpqmx0 > div.corgi-1b6lf06 > div.corgi-1dpcosh > div > form > div.change-ds-theme.flex > button > span > div").click()

def main():
    sheet_id = "1T23UUMdjZBkzvsuk5T2C8fwQp4P05ov4"
    data = fetch_google_sheet_data(sheet_id)

    cities_to_cycle = ["Chicago", "Dallas", "Miami"]  # Just an example, cities you want to rotate.

    driver = setup_chrome_driver()

    try:
        for index, row in enumerate(data):
            first_name, last_name, email, zip_code = row[0], row[1], row[2], row[3]

            print(f"\n🔄 Starting sequence {index + 1}...")

            # Trigger the AHK script to activate NordVPN extension for the current city
            city = cities_to_cycle[index % len(cities_to_cycle)]  # Rotate cities
            print(f"🌐 Switching VPN to: {city} using NordVPN extension")
            trigger_nordvpn_extension()

            # Perform web automation
            perform_selenium_actions(driver, first_name, last_name, email, zip_code)

            print(f"✅ Sequence {index + 1} completed.")
            time.sleep(5)  # Short cooldown between sequences

    finally:
        driver.quit()
        print("🛑 All sequences completed. Browser closed.")

if __name__ == "__main__":
    main()
