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
logger = logging.getLogger(__name__)

def load_json_file(file_path):
    """
    Load JSON content from a file. First, attempt to load as raw JSON.
    If that fails, try to base64-decode the file content and then load as JSON.
    
    Args:
        file_path (str): Path to the JSON file.
        
    Returns:
        dict: The decoded JSON data.
        
    Raises:
        FileNotFoundError: If the file is not found.
        ValueError: If the file is empty or contains invalid JSON.
        
    Note:
        If you trust that the YAML step decodes the files correctly,
        you may remove the base64 fallback logic.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, "r") as f:
        content = f.read().strip()
        if not content:
            raise ValueError(f"{file_path} is empty. Ensure it contains valid JSON.")
        
        # Attempt to parse as raw JSON.
        try:
            return json.loads(content)
        except json.JSONDecodeError as json_err:
            # Fallback: attempt base64 decoding then parse.
            try:
                decoded = base64.b64decode(content).decode("utf-8")
                return json.loads(decoded)
            except Exception as b64_err:
                raise ValueError(
                    f"Failed to parse {file_path} as JSON. Original JSON error: {json_err}. "
                    f"Also, base64 decoding failed: {b64_err}"
                )

def setup_gspread():
    """
    Set up and return a gspread client using an OAuth token loaded from 'gcreds/token.json'.
    
    Returns:
        gspread.Client: An authorized gspread client.
    """
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    token_path = os.path.join("gcreds", "token.json")
    
    token_info = load_json_file(token_path)
    
    # Create OAuth credentials from token_info.
    creds = OAuthCredentials.from_authorized_user_info(token_info, scopes=scope)
    client = gspread.authorize(creds)
    logger.info("Google Sheets client initialized.")
    return client

def setup_firefox_driver():
    """
    Initialize and return a headless Firefox WebDriver.
    
    Returns:
        webdriver.Firefox: The initialized Firefox driver.
    """
    options = FirefoxOptions()
    options.headless = True
    options.set_preference("dom.webdriver.enabled", False)
    options.set_preference("useAutomationExtension", False)
    service = FirefoxService()
    driver = webdriver.Firefox(service=service, options=options)
    logger.info("Firefox driver initialized.")
    return driver

def safe_text(driver, selector):
    """
    Safely extract and return the text content of an element defined by a CSS selector.
    
    Args:
        driver (webdriver.Firefox): The Selenium WebDriver instance.
        selector (str): CSS selector for the desired element.
        
    Returns:
        str: The element's text content, or "N/A" if not found.
    """
    try:
        return driver.find_element(By.CSS_SELECTOR, selector).text
    except Exception as e:
        logger.debug(f"Selector '{selector}' not found or error occurred: {e}")
        return "N/A"

def run_scraper():
    """
    Main function to run the CREXi scraper.
    It retrieves property links from the CREXi properties page, visits each link,
    extracts data, and appends information to two separate Google Sheets.
    """
    SHEET_NAME_RAW = "raw"
    SHEET_NAME_LHF = "low hanging fruit"
    SPREADSHEET_ID = "1IckEBCfyh-o0q7kTPBwU0Ui3eMYJNwOQOmyAysm6W5E"

    try:
        client = setup_gspread()
        sheet_raw = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME_RAW)
        sheet_lhf = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME_LHF)
    except Exception as e:
        logger.error(f"Error setting up Google Sheets: {e}")
        return

    url = "https://www.crexi.com/properties"
    driver = setup_firefox_driver()

    try:
        driver.get(url)
        logger.info(f"Accessing {url}")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.ID, "crx-property-tile-aggregate"))
        )
        logger.info("Properties loaded.")

        tiles = driver.find_elements(By.ID, "crx-property-tile-aggregate")
        hrefs = [tile.get_attribute("href") for tile in tiles if tile.get_attribute("href")]

        logger.info(f"Found {len(hrefs)} property links.")
        for link in hrefs:
            driver.get(link)
            logger.info(f"Processing: {link}")
            time.sleep(2)  # Pause to allow page content to load
            
            # Extract data using safe_text helper function
            address = safe_text(driver, "h2.text")
            dom = safe_text(driver, ".pdp_updated-date-value span.ng-star-inserted")
            lot_size = safe_text(driver, "div:nth-of-type(4) span.detail-value")
            price = safe_text(driver, ".term-value span")
            
            # Determine target sheet based on property info.
            try:
                label_text = safe_text(driver, "div > div.property-info-container:nth-of-type(1)")
                if "Units" in label_text:
                    sheet_raw.append_row([link, address, dom, lot_size, price])
                    logger.info("Data appended to raw sheet.")
                else:
                    sheet_lhf.append_row([link, address, dom, lot_size, price])
                    logger.info("Data appended to LHF sheet.")
            except Exception as ex:
                sheet_lhf.append_row([link, address, dom, lot_size, price])
                logger.error(f"Error determining sheet for data from {link}: {ex}")

    except Exception as err:
        logger.error(f"Error during scraping: {err}")
    finally:
        driver.quit()
        logger.info("Firefox driver closed.")

if __name__ == "__main__":
    run_scraper()
