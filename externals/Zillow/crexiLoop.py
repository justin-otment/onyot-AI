from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
from undetected_chromedriver import Chrome, ChromeOptions
from fake_useragent import UserAgent
from google.oauth2.service_account import Credentials
import gspread
import time
import os

# Constants for Google Sheets
SHEET_ID = "1IckEBCfyh-o0q7kTPBwU0Ui3eMYJNwOQOmyAysm6W5E"
SHEET_NAME = "Sheet1"

# URL to scrape
URL = "https://www.crexi.com/properties?pageSize=60&mapCenter=28.749099306735435,-82.0311664044857&mapZoom=7&showMap=true&acreageMin=2&types%5B%5D=Land"

# Setup fake user agent
ua = UserAgent()

def setup_chrome_driver():
    """Set up undetected Chrome WebDriver for headless scraping."""
    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"user-agent={ua.random}")
    return Chrome(options=options)

def is_processed(href, processed_urls):
    return href in processed_urls

def scrape_zillow_data(driver, max_pages=30):
    data = []
    processed_urls = set()

    for page in range(1, max_pages + 1):
        try:
            print(f"Scraping page {page}...")

            if page > 1:
                current_url = driver.current_url
                next_button_selector = 'span.mdc-button__label'
                next_button = WebDriverWait(driver, 60).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, next_button_selector))
                )
                driver.execute_script("arguments[0].scrollIntoView();", next_button)
                next_button.click()

                WebDriverWait(driver, 60).until(
                    EC.url_changes(current_url)
                )

            page_element = WebDriverWait(driver, 60).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.search-result-container'))
            )
            parent_elements = page_element.find_elements(By.CSS_SELECTOR, '.cui-card-cover-link')

            for parent in parent_elements:
                for attempt in range(3):
                    try:
                        driver.execute_script("arguments[0].scrollIntoView();", parent)
                        time.sleep(1)
                        address = parent.find_element(By.CSS_SELECTOR, 'address').text
                        link_element = parent.find_element(By.CSS_SELECTOR, 'a')
                        href = link_element.get_attribute('href')

                        if address and href and not is_processed(href, processed_urls):
                            data.append({"Address": address, "URL": href})
                            processed_urls.add(href)
                            print(f"✔ Address: {address}, URL: {href}")
                        break
                    except StaleElementReferenceException:
                        if attempt < 2:
                            print("Retrying due to stale element...")
                            time.sleep(1)
                        else:
                            print("Failed to handle stale element.")
        except Exception as e:
            print(f"❌ Error on page {page}: {e}")
            break

    return data

def upload_to_google_sheets(data, sheet_id, sheet_name):
    """Uploads data to Google Sheets using service account credentials."""
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "gcreds/credentials.json")

    creds = Credentials.from_service_account_file(
        credentials_path,
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(sheet_id).worksheet(sheet_name)

    # Optional: Clear existing data (comment this if you want to append)
    sheet.clear()
    sheet.append_row(["Address", "URL"])

    for row in data:
        sheet.append_row([row["Address"], row["URL"]])
    print("✅ Data uploaded to Google Sheets.")

# --- Main Script Execution ---
if __name__ == "__main__":
    driver = setup_chrome_driver()
    try:
        driver.get(URL)
        scraped_data = scrape_zillow_data(driver, max_pages=30)
        if scraped_data:
            upload_to_google_sheets(scraped_data, SHEET_ID, SHEET_NAME)
        else:
            print("⚠ No data scraped.")
    finally:
        driver.quit()
