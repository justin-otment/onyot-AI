from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from undetected_chromedriver import Chrome, ChromeOptions
from fake_useragent import UserAgent
from google.oauth2.service_account import Credentials
import gspread
import time
import os
import sys

# Google Sheets Config
SHEET_ID = "1IckEBCfyh-o0q7kTPBwU0Ui3eMYJNwOQOmyAysm6W5E"
SHEET_NAME = "raw"  # Updated from "Sheet1" to "raw"
URL = "https://www.crexi.com/properties?pageSize=60&mapCenter=28.749099306735435,-82.0311664044857&mapZoom=7&showMap=true&acreageMin=2&types%5B%5D=Land"

ua = UserAgent()

def setup_chrome_driver():
    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"user-agent={ua.random}")
    return Chrome(options=options)

def is_processed(href, processed_urls):
    return href in processed_urls

def scrape_crexi_data(driver, max_pages=30):
    data = []
    processed_urls = set()

    for page in range(1, max_pages + 1):
        try:
            print(f"--- Scraping page {page} ---")

            if page > 1:
                current_url = driver.current_url
                next_button = WebDriverWait(driver, 30).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label=\"Next Page\"]'))
                )
                driver.execute_script("arguments[0].scrollIntoView();", next_button)
                next_button.click()
                WebDriverWait(driver, 30).until(EC.url_changes(current_url))

            try:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div.search-result-container'))
                )
            except TimeoutException:
                print(f"[!] Error: Could not locate listing container on page {page}. Skipping.")
                continue

            cards = driver.find_elements(By.CSS_SELECTOR, "crx-property-tile-aggregate")

            for card in cards:
                for attempt in range(3):
                    try:
                        driver.execute_script("arguments[0].scrollIntoView();", card)
                        time.sleep(1)

                        href = card.get_attribute("href")
                        try:
                            address = card.find_element(By.CSS_SELECTOR, "address").text.strip()
                        except Exception:
                            address = "[No address found]"

                        if href and not is_processed(href, processed_urls):
                            data.append({"Address": address, "URL": href})
                            processed_urls.add(href)
                            print(f"[OK] {address}")
                        break
                    except StaleElementReferenceException:
                        if attempt < 2:
                            time.sleep(1)
                        else:
                            print("[!] Warning: Skipped a stale element.")
        except Exception as e:
            print(f"[!] WebDriver error on page {page}: {e}", file=sys.stderr)
            break

    return data

def upload_to_google_sheets(data, sheet_id, sheet_name):
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "gcreds/credentials.json")
    creds = Credentials.from_service_account_file(
        credentials_path,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(sheet_id).worksheet(sheet_name)

    sheet.clear()
    sheet.append_row(["Address", "URL"])

    rows = [[row["Address"], row["URL"]] for row in dat
            a]
    sheet.append_rows(rows)
    print("[✓] Data uploaded to Google Sheets.")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    driver = setup_chrome_driver()
    try:
        driver.get(URL)
        scraped_data = scrape_crexi_data(driver, max_pages=30)
        if scraped_data:
            upload_to_google_sheets(scraped_data, SHEET_ID, SHEET_NAME)
        else:
            print("[!] No data scraped.")
    finally:
        driver.quit()
