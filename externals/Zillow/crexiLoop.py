import os
import time
import logging
import json
import base64
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import gspread
from google.oauth2.credentials import Credentials as OAuthCredentials

# Set up logging
logging.basicConfig(level=logging.INFO)

def load_json_file(file_path):
    """
    Load JSON content from a file. First attempts to decode as raw JSON.
    If that fails, it attempts to base64-decode the file content and then load as JSON.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(file_path, "r") as f:
        content = f.read().strip()
        if not content:
            raise ValueError(f"{file_path} is empty. Ensure it contains valid JSON or a base64 encoded JSON string.")
        # Attempt raw JSON load
        try:
            return json.loads(content)
        except json.JSONDecodeError as json_err:
            # Try applying base64 decoding first
            try:
                decoded = base64.b64decode(content).decode("utf-8")
                return json.loads(decoded)
            except Exception as b64_err:
                raise ValueError(
                    f"Failed to parse {file_path} as JSON. Original JSON error: {json_err}. "
                    f"Additionally, base64 decoding failed: {b64_err}"
                )

# Setup Google Sheets API using OAuth token
def setup_gspread():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    token_path = os.path.join("gcreds", "token.json")
    creds_path = os.path.join("gcreds", "credentials.json")
    
    # Load token file using the helper function
    token_info = load_json_file(token_path)
    # We load credentials if needed later; in this example, gspread uses token_info
    creds = OAuthCredentials.from_authorized_user_info(token_info, scopes=scope)
    client = gspread.authorize(creds)
    return client

# Setup Firefox WebDriver
def setup_firefox_driver():
    options = FirefoxOptions()
    options.headless = True
    options.set_preference("dom.webdriver.enabled", False)
    options.set_preference("useAutomationExtension", False)
    service = FirefoxService()
    driver = webdriver.Firefox(service=service, options=options)
    logging.info("Firefox driver initialized.")
    return driver

# Main scraping logic
def run_scraper():
    SHEET_NAME_RAW = "raw"
    SHEET_NAME_LHF = "low hanging fruit"
    SPREADSHEET_ID = "1IckEBCfyh-o0q7kTPBwU0Ui3eMYJNwOQOmyAysm6W5E"

    client = setup_gspread()
    sheet_raw = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME_RAW)
    sheet_lhf = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME_LHF)

    url = "https://www.crexi.com/properties"
    driver = setup_firefox_driver()

    try:
        driver.get(url)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "crx-property-tile-aggregate"))
        )

        tiles = driver.find_elements(By.ID, "crx-property-tile-aggregate")
        hrefs = [tile.get_attribute("href") for tile in tiles if tile.get_attribute("href")]

        for link in hrefs:
            driver.get(link)
            time.sleep(2)

            def safe_text(selector):
                try:
                    return driver.find_element(By.CSS_SELECTOR, selector).text
                except Exception:
                    return "N/A"

            address = safe_text("h2.text")
            dom = safe_text(".pdp_updated-date-value span.ng-star-inserted")
            lot_size = safe_text("div:nth-of-type(4) span.detail-value")
            price = safe_text(".term-value span")

            try:
                label_text = driver.find_element(By.CSS_SELECTOR, "div > div.property-info-container:nth-of-type(1)").text
                if "Units" in label_text:
                    sheet_raw.append_row([link, address, dom, lot_size, price])
                else:
                    sheet_lhf.append_row([link, address, dom, lot_size, price])
            except Exception:
                sheet_lhf.append_row([link, address, dom, lot_size, price])

    except Exception as e:
        logging.error(f"Error during scraping: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    run_scraper()
