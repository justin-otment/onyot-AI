import time
import os
import logging

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from fake_useragent import UserAgent
from google.oauth2.service_account import Credentials
import gspread

# -------------------------- Configuration --------------------------
SHEET_ID        = "1IckEBCfyh-o0q7kTPBwU0Ui3eMYJNwOQOmyAysm6W5E"
URL             = (
    "https://www.crexi.com/properties?"
    "pageSize=60&mapCenter=28.749099306735435,-82.0311664044857"
    "&mapZoom=7&showMap=true&acreageMin=2&types%5B%5D=Land"
)
DEFAULT_TIMEOUT = 180

# -------------------------- Logging Setup --------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# -------------------------- Selenium Driver Setup --------------------------
def setup_edge_driver():
    options = EdgeOptions()
    options.use_chromium = True
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Edge(options=options)
    logging.info("Edge driver initialized.")
    return driver

# -------------------------- Page Load and Extraction --------------------------
def wait_for_results_container(driver, timeout=DEFAULT_TIMEOUT, poll_interval=5):
    """
    1) If the Cloudflare “Just a moment…” page appears, wait for it to clear.
    2) Then wait for .updatable-content-container to be present.
    """
    logging.info("⌛ Waiting for property tiles to load (bypass Cloudflare)...")
    deadline = time.time() + timeout

    # Step 1: loop while Cloudflare challenge is present
    while time.time() < deadline:
        title   = (driver.title or "").lower()
        src     = driver.page_source or ""
        if "just a moment" in title or "#challenge-error-text" in src:
            logging.info("🔒 Detected Cloudflare challenge; sleeping %ds...", poll_interval)
            time.sleep(poll_interval)
            continue
        break

    # Step 2: wait for the real results container
    try:
        WebDriverWait(driver, max(0, deadline - time.time())).until(
            EC.presence_of_all_elements_located((By.CLASS_NAME, "updatable-content-container"))
        )
        logging.info("✅ Results container loaded.")
    except TimeoutException:
        logging.error("⏱ Timeout waiting for results container at %s", driver.current_url)
        snippet = driver.page_source[:1000] or "No page source."
        logging.error("❗️ Page snippet:\n%s", snippet)
        raise

def extract_listing_links(driver):
    """
    Pull all hrefs from elements with class name 'ng-star-inserted'
    that look like CREXi property links.
    """
    hrefs = []
    for el in driver.find_elements(By.CLASS_NAME, "ng-star-inserted"):
        try:
            href = el.get_attribute("href")
            if href and href.startswith("https://www.crexi.com/properties/"):
                hrefs.append(href)
        except StaleElementReferenceException:
            logging.warning("Stale element skipping.")
    logging.info(f"Found {len(hrefs)} links on page.")
    return hrefs

# -------------------------- Individual Listing Processing --------------------------
def classify_and_scrape_listing(driver, url):
    """
    Load a listing page, extract key fields, scroll into view
    the property-info container, and classify based on 'Units'.
    """
    try:
        driver.get(url)
        WebDriverWait(driver, DEFAULT_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h2.text"))
        )

        site_address = driver.find_element(By.CSS_SELECTOR, "h2.text").text.strip()
        dom          = driver.find_element(
            By.CSS_SELECTOR, ".pdp_updated-date-value span.ng-star-inserted"
        ).text.strip()
        lot_size     = driver.find_element(
            By.CSS_SELECTOR, "div:nth-of-type(4) span.detail-value"
        ).text.strip()
        price        = driver.find_element(
            By.CSS_SELECTOR, ".term-value span"
        ).text.strip()

        info_container = driver.find_element(
            By.CSS_SELECTOR, "div > div.property-info-container:nth-of-type(1)"
        )
        driver.execute_script("arguments[0].scrollIntoView();", info_container)
        info_text = info_container.text

        sheet_name = "raw" if "Units" in info_text else "low hanging fruit"
        logging.info(f"Classified '{site_address}' as {sheet_name}")

        return {
            "Site Address":   site_address,
            "Days on Market": dom,
            "Lot Size":       lot_size,
            "Price":          price,
            "URL":            url,
            "Sheet":          sheet_name
        }
    except Exception as e:
        logging.error(f"Error scraping {url}: {e}")
        return None

# -------------------------- Google Sheets Upload --------------------------
def upload_classified_data_to_sheets(data, sheet_id):
    """ Group by sheet and push to Google Sheets. """
    try:
        creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "gcreds/credentials.json")
        creds      = Credentials.from_service_account_file(
            creds_path,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        gc         = gspread.authorize(creds)
        logging.info("Authenticated with Google Sheets.")
    except Exception as e:
        logging.error(f"Sheets auth failed: {e}")
        return

    grouped = {"raw": [], "low hanging fruit": []}
    for row in data:
        grouped[row["Sheet"]].append(row)

    for sheet_name, rows in grouped.items():
        if not rows:
            logging.info(f"No rows for '{sheet_name}', skipping.")
            continue
        try:
            ws = gc.open_by_key(sheet_id).worksheet(sheet_name)
            ws.clear()
            ws.append_row(["Site Address", "Days on Market", "Lot Size", "Price", "URL"])
            ws.append_rows([
                [r["Site Address"], r["Days on Market"], r["Lot Size"], r["Price"], r["URL"]]
                for r in rows
            ])
            logging.info(f"Pushed {len(rows)} rows to '{sheet_name}'.")
        except Exception as e:
            logging.error(f"Failed to upload to '{sheet_name}': {e}")

# -------------------------- Main Flow --------------------------
if __name__ == "__main__":
    driver = setup_edge_driver()
    all_results = []

    try:
        driver.get(URL)
        wait_for_results_container(driver)

        for page in range(1, 31):
            logging.info(f"--- Page {page} ---")
            wait_for_results_container(driver)

            links = extract_listing_links(driver)
            for link in links:
                result = classify_and_scrape_listing(driver, link)
                if result:
                    all_results.append(result)

            # Navigate to next page
            try:
                btn = WebDriverWait(driver, DEFAULT_TIMEOUT).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Next Page"]'))
                )
                driver.execute_script("arguments[0].scrollIntoView();", btn)
                prev_url = driver.current_url
                btn.click()
                WebDriverWait(driver, DEFAULT_TIMEOUT).until(EC.url_changes(prev_url))
                logging.info(f"Moved to {driver.current_url}")
            except TimeoutException:
                logging.info("No more pages. Stopping.")
                break

        if all_results:
            upload_classified_data_to_sheets(all_results, SHEET_ID)
        else:
            logging.error("No data scraped.")

    finally:
        driver.quit()
        logging.info("Edge driver closed.")
