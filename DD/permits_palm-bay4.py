import os
import time
import gspread
import traceback
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")

# Authenticate Google Sheets
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
    return gspread.authorize(creds)

# Get data only if the corresponding R cell is blank
def get_sheet_data(sheet_id, range_name, check_column="R6001:R8000"):
    try:
        service = authenticate_google_sheets()
        sheet = service.open_by_key(sheet_id)
        worksheet = sheet.worksheet(range_name.split('!')[0])

        # Fetch values
        search_terms_col = worksheet.get(range_name.split('!')[1])
        check_column_values = worksheet.get(check_column)

        # Normalize list lengths
        max_len = max(len(search_terms_col), len(check_column_values))
        search_terms_col += [[]] * (max_len - len(search_terms_col))
        check_column_values += [[]] * (max_len - len(check_column_values))

        # Return terms where R column is blank
        filtered_terms = [term[0] for term, check in zip(search_terms_col, check_column_values) if term and not check]
        return filtered_terms

    except Exception as e:
        print(f"Error fetching data from Google Sheets: {e}")
        traceback.print_exc()
        return []

# Write remark to column R
def write_detection_remark(sheet_id, worksheet_name, row_index, remark="dwelling detected"):
    try:
        service = authenticate_google_sheets()
        worksheet = service.open_by_key(sheet_id).worksheet(worksheet_name)
        worksheet.update(values=[[remark]], range_name=f"R{row_index}")
    except Exception as e:
        print(f"Error writing remark to sheet: {e}")
        traceback.print_exc()

# Log in to target site
def login(driver):
    try:
        driver.get("https://ims.palmbayflorida.org/ims/Find3?cat=Permits")
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#Email"))
        ).send_keys("john@trustrealtyusa.com")

        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "#Password"))
        ).send_keys("Otment@123")

        WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "#body > form > div.form-group.text-center > div > button"))
        ).click()
        time.sleep(5)
    except Exception as e:
        print(f"Login error: {e}")
        raise

# Search one property
def search_property(driver, term):
    for attempt in range(3):
        try:
            search_box = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#find3SearchCriteria_0_SearchText"))
            )
            search_box.clear()
            search_box.send_keys(term)

            driver.find_element(By.CSS_SELECTOR, "#body > form > div.form-group > div > button").click()

            WebDriverWait(driver, 30).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'form'))
            )

            spans = driver.find_elements(By.CSS_SELECTOR, 'strong')
            return [span.text.strip().lower() for span in spans if span.text.strip()]

        except Exception as e:
            if "stale element reference" in str(e).lower():
                print(f"Stale element encountered, retrying ({attempt + 1}/3)...")
                time.sleep(2)
                continue
            print(f"Search error for '{term}': {e}")
            return []

# Perform scan & detection
def find_and_flag_matches(driver, search_terms, sheet_id, range_name):
    worksheet_name = range_name.split('!')[0]
    for index, term in enumerate(search_terms, start=6001):
        print(f"Searching for '{term}'...")

        texts = search_property(driver, term)
        if not texts:
            print(f"No results for '{term}'")
            continue

        keywords = ["residential", "commercial", "building"]

        for text in texts:
            if any(keyword in text for keyword in keywords):
                print(f" Detected dwelling for '{term}' in row {index}")
                write_detection_remark(sheet_id, worksheet_name, index)
                break

        driver.get("https://ims.palmbayflorida.org/ims/Find3?cat=Permits")

# Main routine
def main():
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-gpu')
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-extensions')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        sheet_id = "1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A"
        range_name = "Palm Bay - ArcGIS RAW!B6001:B8000"
        check_column = "R6001:R8000"

        search_terms = get_sheet_data(sheet_id, range_name, check_column)

        login(driver)
        if search_terms:
            find_and_flag_matches(driver, search_terms, sheet_id, range_name)
        else:
            print("No search terms found or all have been processed.")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
