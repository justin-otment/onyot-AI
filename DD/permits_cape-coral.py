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

def get_sheet_data(sheet_id, range_name):
    try:
        service = authenticate_google_sheets()
        sheet = service.open_by_key(sheet_id)
        worksheet = sheet.worksheet(range_name.split('!')[0])
        data = worksheet.get(range_name.split('!')[1])
        return [cell[0] for cell in data if cell]
    except Exception as e:
        print(f"Error fetching data from Google Sheets: {e}")
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
    for attempt in range(3):  # Retry max 3 times if stale element occurs
        try:
            driver.get("https://energovweb.capecoral.gov/EnerGovProd/selfservice#/search")

            search_box = WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#SearchKeyword"))
            )
            search_box.clear()
            search_box.send_keys(term)

            WebDriverWait(driver, 60).until(
                EC.invisibility_of_element((By.CSS_SELECTOR, "#overlay"))
            )

            search_button = driver.find_element(By.CSS_SELECTOR, "#button-Search")
            search_button.click()

            hidden_element_selector = "#energovSearchForm > div:nth-child(5) > div.col-md-10 > div:nth-child(1)"
            driver.execute_script(
                "document.querySelector(arguments[0]).classList.remove('hidden-print', 'hidden-xs', 'hidden-sm');",
                hidden_element_selector
            )

            WebDriverWait(driver, 60).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'div.row:nth-of-type(n+10)'))
            )

            spans = driver.find_elements(By.CSS_SELECTOR, 'span.margin-md-left')
            print(f"Found {len(spans)} spans for '{term}'")

            texts = []
            for span in spans:
                driver.execute_script("arguments[0].scrollIntoView(true);", span)
                time.sleep(0.5)
                if span.is_displayed():
                    text = span.text.strip().lower()
                    texts.append(text)
            return texts

        except Exception as e:
            if "stale element reference" in str(e).lower():
                print(f"Stale element encountered for '{term}'. Retrying ({attempt + 1}/3)...")
                time.sleep(3)
                driver.refresh()
                continue
            else:
                print(f"Error during search for '{term}':")
                traceback.print_exc()
                return []

async def find_best_match(driver, search_terms, sheet_id, range_name):
    worksheet_name = range_name.split('!')[0]

    for index, term in enumerate(search_terms, start=2):  # Google Sheets is 1-indexed, starts at row 2
        print(f"Searching for '{term}'...")
        texts = await search_property(driver, term)
        if not texts:
            continue

        keywords = ["bld", "blc", "new construction", "new single family residence", "new", "rnt"]
        for text in texts:
            if any(keyword in text for keyword in keywords):
                print(f"Detected dwelling for '{term}' in row {index}")
                write_detection_remark(sheet_id, worksheet_name, index)
                break  # Stop processing further texts once a match is found

        driver.get("https://energovweb.capecoral.gov/EnerGovProd/selfservice#/search")  # Navigate back

async def main():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(options=options)

    sheet_id = "1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A"
    range_name = "Raw Cape Coral - ArcGIS (lands)!B2:B"
    search_terms = get_sheet_data(sheet_id, range_name)

    if search_terms:
        await find_best_match(driver, search_terms, sheet_id, range_name)
    else:
        print("No search terms found in the specified range.")

    driver.quit()

    await asyncio.sleep(0)
    await asyncio.get_event_loop().shutdown_asyncgens()

asyncio.run(main())
