import os
import time
import gspread
import asyncio
import traceback
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")

def authenticate_google_sheets():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            CREDENTIALS_PATH, ["https://www.googleapis.com/auth/spreadsheets"]
        )
        creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())
    client = gspread.authorize(creds)
    return client

def get_sheet_data(sheet_id, range_name, check_column="R14001:R16000"):
    try:
        service = authenticate_google_sheets()
        sheet = service.open_by_key(sheet_id)
        worksheet = sheet.worksheet(range_name.split('!')[0])

        search_terms_col = worksheet.get(range_name.split('!')[1])
        check_column_values = worksheet.get(check_column)

        max_len = max(len(search_terms_col), len(check_column_values))
        search_terms_col += [[]] * (max_len - len(search_terms_col))
        check_column_values += [[]] * (max_len - len(check_column_values))

        filtered_terms = [term[0] for term, check in zip(search_terms_col, check_column_values) if term and not check]
        return filtered_terms

    except Exception as e:
        print(f"Error fetching data from Google Sheets: {e}")
        traceback.print_exc()
        return []

def write_detection_remark(sheet_id, worksheet_name, row_index, remark="dwelling detected"):
    try:
        service = authenticate_google_sheets()
        worksheet = service.open_by_key(sheet_id).worksheet(worksheet_name)
        worksheet.update(values=[[remark]], range_name=f"Z{row_index}")
    except Exception as e:
        print(f"Error writing remark to sheet: {e}")
        traceback.print_exc()

async def search_property(driver, term):
    for attempt in range(3):
        try:
            driver.get("https://energovweb.capecoral.gov/EnerGovProd/selfservice#/search")

            try:
                search_box = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#SearchKeyword"))
                )
            except:
                print(f"[Timeout] Search box not found for term '{term}'")
                raise

            search_box.clear()
            search_box.send_keys(term)

            try:
                WebDriverWait(driver, 30).until(
                    EC.invisibility_of_element_located((By.CSS_SELECTOR, "#overlay"))
                )
            except:
                print(f"[Timeout] Overlay still visible after search for '{term}'")

            search_button = driver.find_element(By.CSS_SELECTOR, "#button-Search")
            search_button.click()

            try:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.row"))
                )
            except:
                print(f"[No Results Timeout] Waiting for results div for '{term}'")
                return []

            no_results = driver.find_elements(By.XPATH, "//*[contains(text(), 'No results found')]")
            if no_results:
                print(f"[No Match] No results found for '{term}'")
                return []

            spans = driver.find_elements(By.CSS_SELECTOR, 'span.margin-md-left')
            print(f"Found {len(spans)} spans for '{term}'")

            texts = []
            for span in spans:
                try:
                    driver.execute_script("arguments[0].scrollIntoView(true);", span)
                    time.sleep(0.3)
                    if span.is_displayed():
                        text = span.text.strip().lower()
                        if text:
                            texts.append(text)
                except:
                    continue

            return texts

        except Exception as e:
            if "stale element reference" in str(e).lower():
                print(f"Stale element encountered for '{term}'. Retrying ({attempt + 1}/3)...")
                time.sleep(3)
                driver.refresh()
                continue
            else:
                print(f"Error during search for '{term}':")
                html_path = os.path.join(BASE_DIR, f"error_page_{term.replace(' ', '_')}.html")
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print(f"Saved error snapshot to {html_path}")
                traceback.print_exc()
                return []

    return []

async def find_best_match(driver, search_terms, sheet_id, range_name):
    worksheet_name = range_name.split('!')[0]

    for index, term in enumerate(search_terms, start=14001):
        print(f"\nSearching for '{term}'...")
        texts = await search_property(driver, term)
        if not texts:
            continue

        keywords = ["bld", "blc", "new construction", "new single family residence", "new", "rnt"]
        for text in texts:
            if any(keyword in text for keyword in keywords):
                print(f"Detected dwelling for '{term}' in row {index}")
                write_detection_remark(sheet_id, worksheet_name, index)
                break

        driver.get("https://energovweb.capecoral.gov/EnerGovProd/selfservice#/search")

async def main():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(options=options)

    sheet_id = "1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A"
    range_name = "Raw Cape Coral - ArcGIS (lands)!B14001:B16000"
    search_terms = get_sheet_data(sheet_id, range_name, check_column="R14001:R16000")

    if search_terms:
        await find_best_match(driver, search_terms, sheet_id, range_name)
    else:
        print("No search terms found in the specified range.")

    driver.quit()
    await asyncio.sleep(0)
    await asyncio.get_event_loop().shutdown_asyncgens()

if __name__ == "__main__":
    asyncio.run(main())
