#!/usr/bin/env python3
import os
import time
import json
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

# --- Retry helper for HTTP GETs ---
def make_request_with_retries(url, retries=3, backoff_factor=1):
    http = urllib3.PoolManager()
    for attempt in range(1, retries + 1):
        try:
            return http.request('GET', url)
        except urllib3.exceptions.ProtocolError as e:
            print(f"Attempt {attempt} failed: {e}")
            sleep_time = backoff_factor * (2 ** attempt)
            print(f"Retrying in {sleep_time}s…")
            time.sleep(sleep_time)
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts")

# Disable SSL warnings (for testing)
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

# Google Sheets config
SHEET_ID   = '1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A'
SHEET_NAME = 'Cape Coral - ArcGIS_LANDonly'
SCOPES     = ['https://www.googleapis.com/auth/spreadsheets']
SA_FILE    = os.getenv('GOOGLE_CREDENTIALS_JSON')

def authenticate_service_account():
    creds = service_account.Credentials.from_service_account_file(
        SA_FILE, scopes=SCOPES
    )
    return build('sheets', 'v4', credentials=creds)

def fetch_data_and_update_sheet():
    try:
        sheets = authenticate_service_account().spreadsheets()
        range_in = f"{SHEET_NAME}!A2:A2500"
        result = sheets.values().get(spreadsheetId=SHEET_ID, range=range_in).execute()
        rows = result.get('values', [])
        print(f"Fetched {len(rows)} rows")
    except Exception as e:
        print(f"Error fetching sheet data: {e}")
        return

    base_url = 'https://www.leepa.org/Search/PropertySearch.aspx'

    for i, row in enumerate(rows, start=2):
        owner = (row[0] or "").strip()
        if not owner:
            print(f"[Row {i}] blank → skip")
            continue

        print(f"[Row {i}] Searching for: {owner}")
        # headless Firefox
        options = webdriver.FirefoxOptions()
        options.add_argument("--headless")
        driver = webdriver.Firefox(service=Service(), options=options)

        try:
            driver.get(base_url)
            inp = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.ID,
                    "ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_STRAPTextBox"))
            )
            inp.send_keys(owner, Keys.RETURN)

            # handle warning popup if it appears
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.ID,
                        "ctl00_BodyContentPlaceHolder_pnlIssues"))
                )
                driver.find_element(By.ID,
                    "ctl00_BodyContentPlaceHolder_btnWarning").click()
            except:
                pass

            time.sleep(5)
            href = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH,
                    '//*[@id="ctl00_BodyContentPlaceHolder_WebTab1"]/div/div[1]/div[1]/table'
                    '/tbody/tr/td[4]/div/div[1]/a'))
            ).get_attribute('href')
            driver.get(href)
            time.sleep(3)

            # gather and write back various fields
            fields = {
                'C': '//*[@id="ownershipDiv"]/div/ul',
                'D': '//*[@id="divDisplayParcelOwner"]/div[1]/div/div[2]/div',
                'E': '//*[@id="valueGrid"]/tbody/tr[2]/td[4]',
                'F': '//*[@id="divDisplayParcelOwner"]/div[3]/table[1]/tbody/tr[3]/td',
                'S': '//*[@id="divDisplayParcelOwner"]/div[2]/div[3]'
            }

            # click image to reveal ownership UL
            img = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH,
                    '//*[@id="divDisplayParcelOwner"]/div[1]/div/div[1]/a[2]/img'))
            )
            img.click()

            for col, xpath in fields.items():
                try:
                    # extra click for “Values” tab
                    if col == 'E':
                        driver.find_element(By.ID, "ValuesHyperLink").click()
                    val = WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    ).text
                except Exception as ex:
                    val = f"ERR: {ex}"
                sheets.values().update(
                    spreadsheetId=SHEET_ID,
                    range=f"{SHEET_NAME}!{col}{i}",
                    valueInputOption="RAW",
                    body={"values": [[val]]}
                ).execute()
                print(f" → wrote {col}{i}: {val[:30]}")

        except Exception as e:
            print(f"[Row {i}] processing error: {e}")
        finally:
            driver.quit()

if __name__ == "__main__":
    fetch_data_and_update_sheet()
