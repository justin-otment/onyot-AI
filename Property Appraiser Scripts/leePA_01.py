#!/usr/bin/env python3
import os
import time
import ssl
import urllib3

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from google.oauth2 import service_account
from googleapiclient.discovery import build

# ── HTTP GET with retries ──────────────────────────────────────────────────────
def make_request_with_retries(url, retries=3, backoff=1):
    http = urllib3.PoolManager()
    for attempt in range(1, retries + 1):
        try:
            return http.request('GET', url)
        except urllib3.exceptions.ProtocolError as e:
            wait = backoff * (2 ** attempt)
            print(f"GET {url} failed (attempt {attempt}): {e}. Retrying in {wait}s…")
            time.sleep(wait)
    raise RuntimeError(f"Could not fetch {url} after {retries} attempts")

# ── Disable SSL checks (for testing only) ────────────────────────────────────
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode   = ssl.CERT_NONE

# ── Sheet configuration ────────────────────────────────────────────────────────
SHEET_ID   = '1IckEBCfyh-o0q7kTPBwU0Ui3eMYJNwOQOmyAysm6W5E'  # your sheet
SHEET_NAME = 'raw'
SCOPES     = ['https://www.googleapis.com/auth/spreadsheets']
SA_FILE    = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')        # set by GH Action

def authenticate_service_account():
    """Load Service Account creds and return a sheets API client."""
    creds = service_account.Credentials.from_service_account_file(
        SA_FILE, scopes=SCOPES
    )
    return build('sheets', 'v4', credentials=creds)

def fetch_data_and_update_sheet():
    # 1) Fetch column A (owners) and E (sale_date)
    try:
        sheets = authenticate_service_account().spreadsheets()
        names = sheets.values().get(spreadsheetId=SHEET_ID,
                                   range=f"{SHEET_NAME}!A2:A").execute().get('values', [])
        dates = sheets.values().get(spreadsheetId=SHEET_ID,
                                   range=f"{SHEET_NAME}!E2:E").execute().get('values', [])
        print(f"Got {len(names)} owners and {len(dates)} existing dates.")
    except Exception as e:
        print(f"ERROR: fetching sheet data → {e}")
        return

    # 2) Loop rows
    base_url = 'https://www.crexi.com/properties?pageSize=60&mapCenter=28.749099306735435,-82.0311664044857&mapZoom=7&showMap=true&acreageMin=2&types%5B%5D=Land'
    for i, (name_row, date_row) in enumerate(zip(names, dates), start=2):
        owner     = name_row[0].strip() if name_row else ""
        sale_date = date_row[0].strip() if date_row else ""

        if not owner:
            print(f"[Row {i}] no owner → skip")
            continue
        if sale_date:
            print(f"[Row {i}] already has date ({sale_date}) → skip")
            continue

        print(f"[Row {i}] searching owner: {owner}")
        # ── Selenium headless Firefox ────────────────────────────────────────
        opts   = webdriver.FirefoxOptions()
        opts.add_argument("--headless")
        driver = webdriver.Firefox(service=Service(), options=opts)

        try:
            driver.get(base_url)
            inp = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID,
                    "ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_STRAPTextBox"))
            )
            inp.send_keys(owner, Keys.RETURN)

            # optional warning popup
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID,
                        "ctl00_BodyContentPlaceHolder_pnlIssues"))
                )
                driver.find_element(By.ID,
                    "ctl00_BodyContentPlaceHolder_btnWarning").click()
            except:
                pass

            # click into the first result
            href = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH,
                    '//*[@id="ctl00_BodyContentPlaceHolder_WebTab1"]/div/div[1]/div[1]/table'
                    '/tbody/tr/td[4]/div/div[1]/a'))
            ).get_attribute('href')
            driver.get(href)

            # click Sales image → extract date & amount
            img = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '#SalesHyperLink > img'))
            )
            driver.execute_script("arguments[0].click();", img)

            sale_date   = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH,
                    '//*[@id="SalesDetails"]/div[3]/table/tbody/tr[2]/td[2]'))
            ).text
            sale_amount = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH,
                    '//*[@id="SalesDetails"]/div[3]/table/tbody/tr[2]/td[1]'))
            ).text

            # 3) Write back into columns E and F
            for col, val in (('E', sale_date), ('F', sale_amount)):
                sheets.values().update(
                    spreadsheetId=SHEET_ID,
                    range=f"{SHEET_NAME}!{col}{i}",
                    valueInputOption="RAW",
                    body={"values": [[val]]}
                ).execute()
                print(f" → wrote {col}{i}: {val}")

        except Exception as err:
            print(f"[Row {i}] ERROR: {err}")
        finally:
            driver.quit()

if __name__ == "__main__":
    fetch_data_and_update_sheet()
