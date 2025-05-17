import os
import json
import base64
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
import time
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Set up credentials from base64 environment variable
creds_b64 = os.getenv("GDRIVE_CREDENTIALS_BASE64")
if not creds_b64:
    raise RuntimeError("GDRIVE_CREDENTIALS_BASE64 not found in environment variables.")

creds_dict = json.loads(base64.b64decode(creds_b64).decode("utf-8"))
creds = service_account.Credentials.from_service_account_info(
    creds_dict,
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)

# Google Sheets API setup
sheets_service = build("sheets", "v4", credentials=creds)
SHEET_ID = "1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A"
SHEET_NAME = "Correct_Sheet_Name_Here"  # 🔁 Replace this after seeing printed sheet names
START_ROW = 2
END_ROW = 2500

# Range for fetching input and writing back output
NAMES_RANGE = f"{SHEET_NAME}!A{START_ROW}:A{END_ROW}"
ADDRESSES_RANGE = f"{SHEET_NAME}!B{START_ROW}:B{END_ROW}"
SALE_DATE_RANGE = f"{SHEET_NAME}!E{START_ROW}:E{END_ROW}"
SALE_AMOUNT_RANGE = f"{SHEET_NAME}!F{START_ROW}:F{END_ROW}"

def fetch_data_and_update_sheet():
    print("Authenticating with Google Sheets API...")
    try:
        # Print sheet tab names for debugging
        metadata = sheets_service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
        sheet_titles = [s["properties"]["title"] for s in metadata["sheets"]]
        print("Available sheet names:", sheet_titles)
    except Exception as e:
        raise RuntimeError(f"Failed to list sheet names: {e}")

    try:
        sheet = sheets_service.spreadsheets()

        print("Fetching sheet data...")
        names_result = sheet.values().get(spreadsheetId=SHEET_ID, range=NAMES_RANGE).execute()
        addresses_result = sheet.values().get(spreadsheetId=SHEET_ID, range=ADDRESSES_RANGE).execute()

        names = names_result.get("values", [])
        addresses = addresses_result.get("values", [])

        output_dates = []
        output_amounts = []

        for i, (name_row, address_row) in enumerate(zip(names, addresses), start=START_ROW):
            if not name_row or not address_row:
                output_dates.append([""])
                output_amounts.append([""])
                continue

            full_address = address_row[0]
            sale_date, sale_amount = scrape_sale_info(full_address)
            output_dates.append([sale_date])
            output_amounts.append([sale_amount])

            print(f"[Row {i}] Address: {full_address} | Sale Date: {sale_date} | Amount: {sale_amount}")

        print("Updating sheet with results...")
        sheet.values().update(
            spreadsheetId=SHEET_ID,
            range=SALE_DATE_RANGE,
            valueInputOption="RAW",
            body={"values": output_dates}
        ).execute()

        sheet.values().update(
            spreadsheetId=SHEET_ID,
            range=SALE_AMOUNT_RANGE,
            valueInputOption="RAW",
            body={"values": output_amounts}
        ).execute()

        print("Update completed!")

    except HttpError as e:
        raise RuntimeError(f"Google Sheets API error: {e}")

def scrape_sale_info(address):
    query = address.replace(" ", "+")
    url = f"https://www.leepa.org/Display/DisplayParcel.aspx?FolioID=&Strap=&Owner=&Addr={query}"

    options = Options()
    options.add_argument("--headless")
    driver = webdriver.Firefox(options=options)

    try:
        driver.get(url)
        time.sleep(3)  # Wait for page to load

        sale_date = sale_amount = ""

        try:
            sale_date_elem = driver.find_element(By.XPATH, '//*[@id="ctl00_ContentPlaceHolder1_lblSaleDate"]')
            sale_date = sale_date_elem.text.strip()
        except Exception:
            pass

        try:
            sale_amount_elem = driver.find_element(By.XPATH, '//*[@id="ctl00_ContentPlaceHolder1_lblSaleAmount"]')
            sale_amount = sale_amount_elem.text.strip()
        except Exception:
            pass

        return sale_date, sale_amount

    finally:
        driver.quit()

if __name__ == "__main__":
    fetch_data_and_update_sheet()