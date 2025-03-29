from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import cloudscraper
import time
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from webdriver_manager.chrome import ChromeDriverManager


def setup_google_sheets():
    """Set up Google Sheets API client."""
    SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
    SERVICE_ACCOUNT_FILE = 'C:\\Users\\DELL\\Documents\\Onyot.ai\\Lead_List-Generator\\python tests\\credentials.json'

    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)

    service = build('sheets', 'v4', credentials=creds)
    return service


def update_google_sheet(service, sheet_id, sheet_name, cell, value):
    """Update the specified cell in the Google Sheet."""
    range_name = f'{sheet_name}!{cell}'
    body = {
        'values': [[value]]
    }
    result = service.spreadsheets().values().update(
        spreadsheetId=sheet_id, range=range_name,
        valueInputOption='RAW', body=body).execute()
    print(f'{result.get("updatedCells")} cells updated.')


def extract_data_from_website(url):
    """Extract data from website using cloudscraper and Selenium."""
    scraper = cloudscraper.create_scraper()
    try:
        response = scraper.get(url)
        response.raise_for_status()

        # Extract cookies from cloudscraper's response
        cookies = response.cookies.get_dict()

        # Step 2: Set up Selenium with extracted cookies
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")

        # Use WebDriver Manager to download and set up ChromeDriver
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

        # Open the URL with Selenium
        driver.get(url)

        # Add the cookies from cloudscraper to Selenium
        for cookie_name, cookie_value in cookies.items():
            driver.add_cookie({"name": cookie_name, "value": cookie_value, "domain": "county-taxes.net"})

        # Refresh the page after setting cookies
        driver.refresh()

        # Wait for the page to load and extract the data
        extracted_element = WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'span#text'))
        )
        print(f"element found")
        
        # Scroll the target element into view
        driver.execute_script("arguments[0].scrollIntoView(true);", extracted_element)

        # Wait for the element to be fully visible
        time.sleep(3)  # Optional: wait for 1 second after scrolling

        # Extract the text from the element
        extracted_text = extracted_element.text
        print(f"Extracted text: {extracted_text}")

    except Exception as e:
        print("An error occurred while extracting data:", e)
        return None

    finally:
        # Clean up WebDriver to ensure proper closure
        try:
            driver.quit()
        except NameError:
            print("Driver was not initialized.")


def main():
    url = "https://county-taxes.net/fl-lee/property-tax?search_query=07-43-23-C4-06102.0530"
    
    # Extract data from the website
    extracted_text = extract_data_from_website(url)
    
    if extracted_text:
        # Set up Google Sheets API client
        sheets_service = setup_google_sheets()

        # Update the Google Sheet with the extracted text
        sheet_id = "1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A"
        sheet_name = "PA Data - Cape Coral Dry Lots"
        cell = "M2"  # Update this to the correct cell as needed
        update_google_sheet(sheets_service, sheet_id, sheet_name, cell, extracted_text)


if __name__ == "__main__":
    main()
