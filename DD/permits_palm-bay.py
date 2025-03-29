import os
import time
import random
import gspread
import asyncio
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from gspread_formatting import *
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")

# Google Sheets Authentication
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

# Fetch data from Google Sheets
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

# Update color for matched rows
def update_sheet_color(sheet_id, range_name, row):
    try:
        service = authenticate_google_sheets()
        sheet = service.open_by_key(sheet_id)
        worksheet = sheet.worksheet(range_name.split('!')[0])
        cell_format = CellFormat(backgroundColor=Color(1, 0, 0))
        format_cell_range(worksheet, f"{row}:{row}", cell_format)
    except Exception as e:
        print(f"Error updating sheet color: {e}")

# Login to the website
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

def search_property(driver, term):
    for attempt in range(5):
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
            print(f"Error encountered: {e}")
            if "stale element reference" in str(e).lower():
                print(f"Stale element encountered, retrying ({attempt + 1}/5)...")
                time.sleep(2)
                continue
            else:
                return []

def find_best_match(driver, search_terms, sheet_id, range_name):
    for index, term in enumerate(search_terms, start=2):
        print(f"Searching for '{term}'...")
        texts = search_property(driver, term)
        if not texts:
            continue

        keywords = ["residential", "commercial", "building"]
        matched_keywords = [text for text in texts if any(keyword in text for keyword in keywords)]

        if matched_keywords:
            print(f"Matched keywords in row {index}: {matched_keywords}")
            update_sheet_color(sheet_id, range_name, index)
        else:
            print(f"No matched keywords found for '{term}'")
        driver.get("https://ims.palmbayflorida.org/ims/Find3?cat=Permits")  # Navigate back

# Main execution
def main():
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-gpu')
    options.add_argument('--headless')  # Run in headless mode
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-extensions')  # Disable extensions for stability

    # Use webdriver_manager to ensure the correct version of ChromeDriver is used
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    try:
        sheet_id = "1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A"
        range_name = "Palm Bay - ArcGIS RAW!B2:B"
        search_terms = get_sheet_data(sheet_id, range_name)
        login(driver)

        if search_terms:
            find_best_match(driver, search_terms, sheet_id, range_name)
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
