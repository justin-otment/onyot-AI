from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from undetected_chromedriver import Chrome, ChromeOptions
from fake_useragent import UserAgent
from google.oauth2.service_account import Credentials
import gspread
import time
import os
import sys

# Constants
SHEET_ID = "1IckEBCfyh-o0q7kTPBwU0Ui3eMYJNwOQOmyAysm6W5E"
SHEET_NAME = "raw"
URL = "https://www.crexi.com/properties?pageSize=60&mapCenter=28.749099306735435,-82.0311664044857&mapZoom=7&showMap=true&acreageMin=2&types%5B%5D=Land"

ua = UserAgent()


def setup_chrome_driver():
    options = ChromeOptions()
    # Uncomment below for CI testing in GUI mode
    # options.add_argument("--headless=new")
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
            print(f"\n--- Scraping page {page} ---")

            if page > 1:
                current_url = driver.current_url
                next_button = WebDriverWait(driver, 30).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Next Page"]'))
                )
                driver.execute_script("arguments[0].scrollIntoView();", next_button)
                next_button.click()
                WebDriverWait(driver, 30).until(EC.url_changes(current_url))

            # Wait for card links to appear
            try:
                parent_elements = WebDriverWait(driver, 30).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a.cui-card-cover-link'))
                )
            except TimeoutException:
                print(f"❗ Page {page} timed out: listings not found.")
                driver.save_screenshot(f"crexi_page_{page}_error.png")
                with open(f"crexi_page_{page}.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                continue

            for element in parent_elements:
                for attempt in range(3):
                    try:
                        driver.execute_script("arguments[0].scrollIntoView();", element)
                        time.sleep(1)

                        href = element.get_attribute("href")
                        try:
                            address = element.find_element(By.TAG_NAME, "address").text
                        except:
                            address = "[No address found]"

                        if href and not is_processed(href, processed_urls):
                            data.append({"Address": address, "URL": href})
                            processed_urls.add(href)
                            print(f"[✓] {address}")
                        break
                    except StaleElementReferenceException:
                        if attempt < 2:
                            time.sleep(1)
                        else:
                            print("⚠️ Skipped a stale element.")
        except WebDriverException as e:
            print(f"🚫 WebDriver error on page {page}: {e}", file=sys.stderr)
            driver.save_screenshot(f"crexi_page_{page}_webdriver_error.png")
            with open(f"crexi_page_{page}_webdriver.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            break
        except Exception as e:
            print(f"🚫 Unexpected error on page {page}: {e}", file=sys.stderr)
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
    rows = [[row["Address"], row["URL"]] for row in data]
    sheet.append_rows(rows)
    print(f"✅ Uploaded {len(rows)} rows to Google Sheets.")


# --- MAIN ---
if __name__ == "__main__":
    driver = setup_chrome_driver()
    try:
        driver.get(URL)
        time.sleep(3)  # let JS fully load
        scraped_data = scrape_crexi_data(driver, max_pages=30)
        if scraped_data:
            upload_to_google_sheets(scraped_data, SHEET_ID, SHEET_NAME)
        else:
            print("⚠ No data scraped.")
    finally:
        driver.quit()
