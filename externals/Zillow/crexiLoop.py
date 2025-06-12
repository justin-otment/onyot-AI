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

# Google Sheets Config
SHEET_ID = "1IckEBCfyh-o0q7kTPBwU0Ui3eMYJNwOQOmyAysm6W5E"
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

def wait_for_results_container(driver):
    print("[...] Waiting for property tiles to load...")
    WebDriverWait(driver, 30).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#crx-property-tile-aggregate"))
    )

def extract_listing_links(driver):
    cards = driver.find_elements(By.CSS_SELECTOR, "#crx-property-tile-aggregate a.cui-card-cover-link")
    hrefs = []
    for card in cards:
        try:
            href = card.get_attribute("href")
            if href:
                hrefs.append(href)
        except StaleElementReferenceException:
            continue
    return hrefs

def classify_and_scrape_listing(driver, url):
    try:
        driver.get(url)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h2.text"))
        )

        site_address = driver.find_element(By.CSS_SELECTOR, "h2.text").text.strip()
        days_on_market = driver.find_element(By.CSS_SELECTOR, ".pdp_updated-date-value span.ng-star-inserted").text.strip()
        lot_size = driver.find_element(By.CSS_SELECTOR, "div:nth-of-type(4) span.detail-value").text.strip()
        price = driver.find_element(By.CSS_SELECTOR, ".term-value span").text.strip()

        info_container = driver.find_element(By.CSS_SELECTOR, "div > div.property-info-container:nth-of-type(1)")
        driver.execute_script("arguments[0].scrollIntoView();", info_container)
        info_text = info_container.text

        sheet_name = "raw" if "Units" in info_text else "low hanging fruit"

        return {
            "Site Address": site_address,
            "Days on Market": days_on_market,
            "Lot Size": lot_size,
            "Price": price,
            "URL": url,
            "Sheet": sheet_name
        }

    except Exception as e:
        print(f"[!] Error scraping {url}: {e}")
        return None

def upload_classified_data_to_sheets(data, sheet_id):
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "gcreds/credentials.json")
    creds = Credentials.from_service_account_file(credentials_path, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    gc = gspread.authorize(creds)

    grouped = {"raw": [], "low hanging fruit": []}
    for entry in data:
        grouped[entry["Sheet"]].append(entry)

    for sheet_name, rows in grouped.items():
        if not rows:
            continue
        sheet = gc.open_by_key(sheet_id).worksheet(sheet_name)
        sheet.clear()
        sheet.append_row(["Site Address", "Days on Market", "Lot Size", "Price", "URL"])
        sheet.append_rows([
            [r["Site Address"], r["Days on Market"], r["Lot Size"], r["Price"], r["URL"]]
            for r in rows
        ])
        print(f"[✓] Uploaded {len(rows)} entries to '{sheet_name}'")

if __name__ == "__main__":
    driver = setup_chrome_driver()
    try:
        driver.get(URL)
        wait_for_results_container(driver)

        all_results = []
        for page in range(1, 31):
            print(f"--- Scraping page {page} ---")

            hrefs = extract_listing_links(driver)
            for href in hrefs:
                listing = classify_and_scrape_listing(driver, href)
                if listing:
                    all_results.append(listing)

            try:
                next_btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[aria-label="Next Page"]'))
                )
                driver.execute_script("arguments[0].scrollIntoView();", next_btn)
                current_url = driver.current_url
                next_btn.click()
                WebDriverWait(driver, 15).until(EC.url_changes(current_url))
                wait_for_results_container(driver)
            except TimeoutException:
                print("[!] No more pages or next button not found.")
                break

        if all_results:
            upload_classified_data_to_sheets(all_results, SHEET_ID)
        else:
            print("[!] No data scraped.")

    finally:
        driver.quit()
