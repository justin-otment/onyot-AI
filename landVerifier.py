import os
import random
import asyncio
from selenium.webdriver.chrome.options import Options
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from selenium import webdriver
import gspread
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import csv


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")

SHEET_ID = "1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A"

# Authenticate with Google Sheets API
def authenticate_google_sheets():
    """Authenticate with Google Sheets API for gspread."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(
            TOKEN_PATH, ["https://www.googleapis.com/auth/spreadsheets"]
        )
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_PATH, ["https://www.googleapis.com/auth/spreadsheets"]
            )
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as token:
            token.write(creds.to_json())
    return creds


# Load Google Sheet
def load_google_sheet(sheet_id):
    """Fetch a Google Sheets workbook using gspread."""
    try:
        creds = authenticate_google_sheets()
        client = gspread.authorize(creds)
        return client.open_by_key(sheet_id)
    except Exception as e:
        print(f"Error loading Google Sheets: {e}")
        return None

def extract_text(driver, fields):
    """Extract text from webpage using Xpath IDs."""
    data = {}
    for field_name, xpath in fields.items():
        if xpath:
            try:
                element = WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                data[field_name] = element.text
            except Exception:
                data[field_name] = None
    return data

def log_to_csv(data, fieldnames):
    """
    Log the data to a CSV file, ensuring proper handling of commas, newlines, and quotes.
    """
    try:
        file_path = "processed_leads.csv"
        # Open CSV file in append mode (or create it if it doesn't exist)
        with open(file_path, mode='a', newline='', encoding='utf-8') as csv_file:
            csv_writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

            # Write header only if file is empty
            if csv_file.tell() == 0:
                csv_writer.writeheader()

            # Clean data before writing (to handle multiline and quotes)
            cleaned_data = {key: clean_data(value) for key, value in data.items()}

            # Write the row
            csv_writer.writerow(cleaned_data)

        print(f"Data successfully logged to {file_path}")
    except Exception as e:
        print(f"Error logging data to CSV: {e}")


def clean_data(value):
    """Clean the extracted data by replacing newline characters with a comma and space."""
    if isinstance(value, str):
        return value.replace("\n", ", ")
    return value

def process_sheet(sheet, legend, driver):
    county_col = sheet.find("County").col
    county_data = sheet.col_values(county_col)[1:]  # Skip header

    for row_index, county_name in enumerate(county_data, start=2):  # Start from row 2
        print(f"Processing County: {county_name}")

        # Search for the county in the legend sheet
        legend_cell = legend.find(county_name)
        if legend_cell is None:
            print(f"County {county_name} not found in the legend sheet. Skipping...")
            continue

        legend_row = legend_cell.row
        web_url = legend.cell(legend_row, legend.find("County PA").col).value

        print(f"URL for County: {web_url}")
        driver.get(web_url)

        # Process APN value
        apn_col = sheet.find("APN").col
        apn_value_raw = sheet.cell(row_index, apn_col).value
        if apn_value_raw is None:
            print(f"APN value is missing for row {row_index}. Skipping...")
            continue

        apn_value = apn_value_raw  # Use APN value directly

        # Fetch other values from the legend sheet
        submit_button_xpath = legend.cell(legend_row, legend.find("Submit Button xpath").col).value
        select_record_css = legend.cell(legend_row, legend.find("Select Record CSS").col).value
        tnc_css = legend.cell(legend_row, legend.find("T&C CSS").col).value if legend.find("T&C CSS") else None

        extraction_fields_primary = {
            "DOR": legend.cell(legend_row, legend.find("DOR - xpath").col).value,
            "Owner Mail Street": legend.cell(legend_row, legend.find("Owner Mail Street- xpath").col).value,
            "Owner Mail City, State & Zip": legend.cell(legend_row, legend.find("Owner Mail City, State & Zip - xpath").col).value,
            "Site Address": legend.cell(legend_row, legend.find("Site Addres - xpath").col).value,
            "Folio ID": legend.cell(legend_row, legend.find("Folio ID - xpath").col).value,
        }

        # Ensure you are correctly fetching the "Has Bldg: Y/N" and "Bldg Info"
        print(f"Fetching 'Has Bldg: Y/N' column: {legend.find('Has Bldg: Y/N')}")
        print(f"Fetching 'Bldg Info' column: {legend.find('Bldg Info')}")
        
        extraction_fields_secondary = {
            "Has Bldg: Y/N": legend.cell(legend_row, legend.find("Has Bldg: Y/N").col).value,
            "Bldg Info": legend.cell(legend_row, legend.find("Bldg Info").col).value,
            "Lot Size": legend.cell(legend_row, legend.find("Lot Size").col).value,
            "Optional Property Details": legend.cell(legend_row, legend.find("(optional: property click details)").col).value,
        }

        extraction_fields_sales = {
            "Last Sale Date": legend.cell(legend_row, legend.find("Last Sale Date").col).value,
            "Last Sale Price": legend.cell(legend_row, legend.find("Last Sale Price").col).value,
            "OR Book & Page No": legend.cell(legend_row, legend.find("OR Book & Page No").col).value,
            "Optional Sales Details": legend.cell(legend_row, legend.find("(optional: sales click details)").col).value,
        }

        try:
            # Locate and fill APN search field
            search_apn_xpath = legend.cell(legend_row, legend.find("Search Type 1 - xpath ID(sendKey)").col).value
            apn_search_element = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, search_apn_xpath))
            )
            apn_search_element.send_keys(apn_value)

            # Locate and click the submit button
            submit_button_element = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.XPATH, submit_button_xpath))
            )
            submit_button_element.click()
            print("Submit button clicked.")
            time.sleep(1.5)

            # Locate and click the record
            record_element = WebDriverWait(driver, 30).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, select_record_css))
            )
            record_element.click()
            print(f"Record selected for County: {county_name}")
            time.sleep(1.5)

            # Switch to the new tab
            driver.switch_to.window(driver.window_handles[-1])
            print("Switched to the new tab.")

            # Handle pop-up if present
            if tnc_css:
                try:
                    tnc_element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, tnc_css))
                    )
                    tnc_element.click()
                    print("T&C pop-up handled.")
                except Exception:
                    print("No T&C pop-up present.")

            # Extract primary text data
            data_primary = extract_text(driver, extraction_fields_primary)
            print(f"Primary data extracted: {data_primary}")

            # Clean the data
            data_primary_cleaned = {key: clean_data(value) for key, value in data_primary.items()}
            print(f"Cleaned primary data: {data_primary_cleaned}")

            # Extract secondary text data
            secondary_data = extract_text(driver, extraction_fields_secondary)
            print(f"Secondary data extracted: {secondary_data}")

            # Clean the secondary data
            secondary_data_cleaned = {key: clean_data(value) for key, value in secondary_data.items()}
            print(f"Cleaned secondary data: {secondary_data_cleaned}")

            # Extract sales text data
            sales_data = extract_text(driver, extraction_fields_sales)
            print(f"Sales data extracted: {sales_data}")

            # Clean the sales data
            sales_data_cleaned = {key: clean_data(value) for key, value in sales_data.items()}
            print(f"Cleaned sales data: {sales_data_cleaned}")

            # Prepare data for CSV logging
            data_to_log = {
                "County": county_name,
                **data_primary_cleaned,
                **secondary_data_cleaned,
                **sales_data_cleaned,
            }

            # Update the csv_headers to include the missing fields
            csv_headers = [
                "County",
                "DOR",
                "Owner Mail Street",
                "Owner Mail City, State & Zip",
                "Site Address",
                "Folio ID",
                "Has Bldg: Y/N",
                "Bldg Info",
                "Lot Size",
                "Last Sale Date",
                "Last Sale Price",
                "OR Book & Page No",
                "Optional Property Details",  # Add this
                "Optional Sales Details",     # Add this
            ]

            # Log the data to CSV
            log_to_csv(data_to_log, csv_headers)

            # Close the current tab and switch back to the original
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            print("Closed the current tab and returned to the original tab.")

        except Exception as e:
            print(f"Error processing APN search for {county_name}: {e}")
            continue


def main():
    SHEET_ID = "1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A"
    sheet_name_legend = "Legend"

    # Load Google Sheets
    workbook = load_google_sheet(SHEET_ID)
    legend_sheet = workbook.worksheet(sheet_name_legend)

    # Initialize Selenium WebDriver
    driver = webdriver.Chrome()

    # Get all sheet names and process them in order
    sheet_names = [sheet.title for sheet in workbook.worksheets()]

    # Process sheets in chronological order (or any order you prefer)
    for sheet_name in sheet_names:
        # Skip the legend sheet
        if sheet_name == sheet_name_legend:
            continue

        sheet = workbook.worksheet(sheet_name)
        print(f"Processing sheet: {sheet_name}")

        # Process each row in the sheet
        process_sheet(sheet, legend_sheet, driver)

    driver.quit()

if __name__ == "__main__":
    main()