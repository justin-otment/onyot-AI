from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from undetected_chromedriver import Chrome, ChromeOptions
from fake_useragent import UserAgent
from google.oauth2.service_account import Credentials
import gspread
import time
import os
import logging

# -------------------------- Configuration --------------------------
SHEET_ID = "1IckEBCfyh-o0q7kTPBwU0Ui3eMYJNwOQOmyAysm6W5E"
URL = ("https://www.crexi.com/properties?pageSize=60&mapCenter="
       "28.749099306735435,-82.0311664044857&mapZoom=7&showMap=true&acreageMin=2&types%5B%5D=Land")
ua = UserAgent()

# -------------------------- Logging Setup --------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# -------------------------- Selenium Driver Setup --------------------------
def setup_chrome_driver():
    options = ChromeOptions()
    # Use headless mode with the new headless feature for stability in CI.
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"user-agent={ua.random}")
    driver = Chrome(options=options)
    logging.info("Chrome driver initialized.")
    return driver

# -------------------------- Page Load and Extraction --------------------------
def wait_for_results_container(driver):
    """ Wait until the full results container is loaded. """
    logging.info("Waiting for property tiles to load...")
    WebDriverWait(driver, 30).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#crx-property-tile-aggregate"))
    )
    logging.info("Results container loaded.")

def extract_listing_links(driver):
    """
    Extract href links from each listing item on the page
    using the known element structure.
    """
    cards = driver.find_elements(By.CSS_SELECTOR, "#crx-property-tile-aggregate a.cui-card-cover-link")
    hrefs = []
    for card in cards:
        try:
            href = card.get_attribute("href")
            if href:
                hrefs.append(href)
        except StaleElementReferenceException:
            logging.warning("Encountered a stale element during link extraction. Skipping one element.")
            continue
    logging.info(f"Found {len(hrefs)} listing links on page.")
    return hrefs

# -------------------------- Individual Listing Processing --------------------------
def classify_and_scrape_listing(driver, url):
    """
    For an individual listing URL:
      - Load the page and wait for key elements.
      - Extract required text elements:
          * Site Address: "h2.text"
          * Days on Market: ".pdp_updated-date-value span.ng-star-inserted"
          * Lot Size: "div:nth-of-type(4) span.detail-value"
          * Price: ".term-value span"
      - Scroll to property info container and classify listing based on presence of "Units".
    """
    try:
        driver.get(url)
        # Wait for the Site Address element to be present.
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h2.text"))
        )
        # Extract required elements.
        site_address = driver.find_element(By.CSS_SELECTOR, "h2.text").text.strip()
        days_on_market = driver.find_element(By.CSS_SELECTOR, ".pdp_updated-date-value span.ng-star-inserted").text.strip()
        lot_size = driver.find_element(By.CSS_SELECTOR, "div:nth-of-type(4) span.detail-value").text.strip()
        price = driver.find_element(By.CSS_SELECTOR, ".term-value span").text.strip()
        
        # Scroll into view and extract the full text from the property info container.
        info_container = driver.find_element(By.CSS_SELECTOR, "div > div.property-info-container:nth-of-type(1)")
        driver.execute_script("arguments[0].scrollIntoView();", info_container)
        info_text = info_container.text
        
        # Classify the listing based on the presence of the word "Units".
        sheet_name = "raw" if "Units" in info_text else "low hanging fruit"
        logging.info(f"Listing classified as '{sheet_name}' - {site_address}")
        
        return {
            "Site Address": site_address,
            "Days on Market": days_on_market,
            "Lot Size": lot_size,
            "Price": price,
            "URL": url,
            "Sheet": sheet_name
        }

    except Exception as e:
        logging.error(f"Error scraping {url}: {e}")
        return None

# -------------------------- Google Sheets Upload --------------------------
def upload_classified_data_to_sheets(data, sheet_id):
    """ Upload the data into two separate Google Sheets tabs based on classification. """
    try:
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "gcreds/credentials.json")
        creds = Credentials.from_service_account_file(credentials_path, scopes=["https://www.googleapis.com/auth/spreadsheets"])
        gc = gspread.authorize(creds)
        logging.info("Google Sheets credentials loaded successfully.")
    except Exception as e:
        logging.error(f"Error authenticating with Google Sheets: {e}")
        return

    grouped = {"raw": [], "low hanging fruit": []}
    for entry in data:
        grouped[entry["Sheet"]].append(entry)

    for sheet_name, rows in grouped.items():
        if not rows:
            logging.info(f"No data to upload for sheet '{sheet_name}'.")
            continue

        try:
            sheet = gc.open_by_key(sheet_id).worksheet(sheet_name)
            sheet.clear()
            sheet.append_row(["Site Address", "Days on Market", "Lot Size", "Price", "URL"])
            sheet.append_rows([
                [r["Site Address"], r["Days on Market"], r["Lot Size"], r["Price"], r["URL"]]
                for r in rows
            ])
            logging.info(f"Uploaded {len(rows)} entries to '{sheet_name}' sheet.")
        except Exception as e:
            logging.error(f"Error uploading data to sheet '{sheet_name}': {e}")

# -------------------------- Main Script Flow --------------------------
if __name__ == "__main__":
    driver = setup_chrome_driver()
    all_results = []
    try:
        driver.get(URL)
        wait_for_results_container(driver)

        # Loop though a maximum of 30 pages
        for page in range(1, 31):
            logging.info(f"--- Scraping page {page} ---")

            # Ensure results container is loaded on the current page
            wait_for_results_container(driver)
            hrefs = extract_listing_links(driver)
            for href in hrefs:
                listing = classify_and_scrape_listing(driver, href)
                if listing:
                    all_results.append(listing)

            # Navigate to next page if possible.
            try:
                next_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Next Page"]'))
                )
                driver.execute_script("arguments[0].scrollIntoView();", next_btn)
                current_url = driver.current_url
                next_btn.click()
                # Wait for URL change to confirm page navigation.
                WebDriverWait(driver, 15).until(EC.url_changes(current_url))
                logging.info(f"Navigated to next page: {driver.current_url}")
                wait_for_results_container(driver)
            except TimeoutException:
                logging.info("No more pages or next button not found. Ending pagination.")
                break

        if all_results:
            upload_classified_data_to_sheets(all_results, SHEET_ID)
        else:
            logging.error("No data scraped from pages.")

    finally:
        driver.quit()
        logging.info("Chrome driver closed.")
