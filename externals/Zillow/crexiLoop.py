import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import gspread
from google.oauth2.service_account import Credentials

# Set up logging
logging.basicConfig(level=logging.INFO)

# Setup Firefox WebDriver
def setup_firefox_driver():
    options = FirefoxOptions()
    options.headless = True  # Run headless for CI
    options.set_preference("dom.webdriver.enabled", False)
    options.set_preference("useAutomationExtension", False)
    service = FirefoxService()
    driver = webdriver.Firefox(service=service, options=options)
    logging.info("Firefox driver initialized.")
    return driver

# Setup Google Sheets API
def setup_gspread():
    scope = ['https://www.googleapis.com/auth/spreadsheets']
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    credentials = Credentials.from_service_account_file(creds_path, scopes=scope)
    client = gspread.authorize(credentials)
    return client

# Main scraping logic
def run_scraper():
    SHEET_NAME_RAW = 'raw'
    SHEET_NAME_LHF = 'low hanging fruit'
    SPREADSHEET_ID = '1IckEBCfyh-o0q7kTPBwU0Ui3eMYJNwOQOmyAysm6W5E'  # Replace with your actual sheet ID

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

            try:
                address = driver.find_element(By.CSS_SELECTOR, "h2.text").text
            except:
                address = "N/A"

            try:
                dom = driver.find_element(By.CSS_SELECTOR, ".pdp_updated-date-value span.ng-star-inserted").text
            except:
                dom = "N/A"

            try:
                lot_size = driver.find_element(By.CSS_SELECTOR, "div:nth-of-type(4) span.detail-value").text
            except:
                lot_size = "N/A"

            try:
                price = driver.find_element(By.CSS_SELECTOR, ".term-value span").text
            except:
                price = "N/A"

            try:
                label_text = driver.find_element(By.CSS_SELECTOR, "div > div.property-info-container:nth-of-type(1)").text
                if "Units" in label_text:
                    sheet_raw.append_row([link, address, dom, lot_size, price])
                else:
                    sheet_lhf.append_row([link, address, dom, lot_size, price])
            except:
                sheet_lhf.append_row([link, address, dom, lot_size, price])

    except Exception as e:
        logging.error(f"Error during scraping: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    run_scraper()
