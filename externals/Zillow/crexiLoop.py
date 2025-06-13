import os
import time
import logging
import gspread
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Paths to the credentials files created by the GitHub actions workflow
TOKEN_PATH = "gcreds/token.json"
CREDS_PATH = "gcreds/credentials.json"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

def get_credentials():
    """
    Load and refresh Google API credentials.
    
    The function loads credentials from TOKEN_PATH and, if they are expired
    and a refresh token is present, attempts to refresh the token.
    The refreshed token is written back to TOKEN_PATH.
    """
    if not os.path.exists(TOKEN_PATH):
        raise FileNotFoundError(f"{TOKEN_PATH} not found! Ensure workflow decoded and placed it.")

    try:
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, scopes=SCOPES)
    except Exception as e:
        logger.error("❌ Failed to load credentials from file: %s", e)
        raise

    # Refresh token if needed
    if creds and creds.expired and creds.refresh_token:
        logger.info("🔄 Token is expired or invalid. Refreshing access token...")
        try:
            creds.refresh(Request())
        except Exception as refresh_error:
            logger.error("❌ Failed to refresh token: %s", refresh_error)
            raise
        else:
            with open(TOKEN_PATH, 'w') as token_file:
                token_file.write(creds.to_json())
            logger.info("✅ Token refreshed and saved. New expiry: %s", creds.expiry)

    return creds

def setup_gspread():
    """
    Authorize gspread with refreshed credentials.
    """
    creds = get_credentials()
    try:
        client = gspread.authorize(creds)
        logger.info("✅ Google Sheets client initialized.")
    except Exception as e:
        logger.error("❌ Failed to authorize gspread: %s", e)
        raise
    return client

def setup_firefox_driver():
    """
    Start headless Firefox WebDriver.
    """
    options = FirefoxOptions()
    options.headless = True
    # Disable automation flags to reduce detection likelihood.
    options.set_preference("dom.webdriver.enabled", False)
    options.set_preference("useAutomationExtension", False)
    service = FirefoxService()
    try:
        driver = webdriver.Firefox(service=service, options=options)
        logger.info("🦊 Firefox driver initialized.")
    except Exception as e:
        logger.error("❌ Failed to initialize Firefox driver: %s", e)
        raise
    return driver

def safe_text(driver, selector):
    """
    Safely returns text content for a given CSS selector.
    """
    try:
        return driver.find_element(By.CSS_SELECTOR, selector).text
    except Exception as e:
        logger.debug("Selector '%s' not found: %s", selector, e)
        return "N/A"

def wait_for_all_results_to_load(driver, timeout=30, sleep_interval=2):
    """
    Dynamically scroll and load all property results.
    """
    end_time = time.time() + timeout
    prev_count = -1
    while time.time() < end_time:
        WebDriverWait(driver, sleep_interval).until(
            EC.presence_of_element_located((By.ID, "crx-property-tile-aggregate"))
        )
        results = driver.find_elements(By.ID, "crx-property-tile-aggregate")
        logger.info("🧱 Found %d result items so far.", len(results))
        if len(results) == prev_count:
            break
        prev_count = len(results)
        try:
            ActionChains(driver).move_to_element(results[-1]).perform()
        except Exception:
            pass
        time.sleep(sleep_interval)
    return results

def run_scraper():
    """
    Main scraper function.
    
    It loads Google Sheets credentials, connects to the spreadsheets,
    launches a headless browser to load listings, extracts property data,
    and classifies & writes data to specific sheets.
    """
    SHEET_RAW = "raw"
    SHEET_LHF = "low hanging fruit"
    SPREADSHEET_ID = "1IckEBCfyh-o0q7kTPBwU0Ui3eMYJNwOQOmyAysm6W5E"

    try:
        client = setup_gspread()
        sheet_raw = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_RAW)
        sheet_lhf = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_LHF)
    except Exception as e:
        logger.error("❌ Google Sheets setup failed: %s", e)
        return

    driver = setup_firefox_driver()

    try:
        driver.get("https://www.crexi.com/properties")
        logger.info("🌐 Accessing CREXi listings...")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "crx-property-tile-aggregate"))
        )

        results = wait_for_all_results_to_load(driver)
        logger.info("✅ Total results loaded: %d", len(results))

        hrefs = [e.get_attribute("href") for e in results if e.get_attribute("href")]
        logger.info("🔗 Extracted %d listing links", len(hrefs))

        for link in hrefs:
            driver.get(link)
            logger.info("🔍 Processing: %s", link)
            time.sleep(2)

            address = safe_text(driver, "h2.text")
            dom = safe_text(driver, ".pdp_updated-date-value span.ng-star-inserted")
            lot_size = safe_text(driver, "div:nth-of-type(4) span.detail-value")
            price = safe_text(driver, ".term-value span")

            try:
                classification_elem = driver.find_element(By.CSS_SELECTOR, "div > div.property-info-container:nth-of-type(1)")
                ActionChains(driver).move_to_element(classification_elem).perform()
                label_text = classification_elem.text
            except Exception:
                label_text = ""

            if "Units" in label_text:
                sheet_raw.append_row([link, address, dom, lot_size, price])
                logger.info("📥 Appended to RAW sheet")
            else:
                sheet_lhf.append_row([link, address, dom, lot_size, price])
                logger.info("📥 Appended to LOW HANGING FRUIT sheet")

    except Exception as err:
        logger.error("❌ Error during scraping: %s", err)
    finally:
        driver.quit()
        logger.info("🛑 Firefox driver closed.")

if __name__ == "__main__":
    run_scraper()
