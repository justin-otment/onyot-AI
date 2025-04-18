import os
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import urllib3
from urllib3.exceptions import ProtocolError
import ssl
import time
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

def make_request_with_retries(url, retries=3, backoff_factor=1):
    http = urllib3.PoolManager()
    attempt = 0
    while attempt < retries:
        try:
            response = http.request('GET', url)
            return response
        except ProtocolError as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            attempt += 1
            sleep_time = backoff_factor * (2 ** attempt)  # Exponential backoff
            print(f"Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)
    raise Exception(f"Failed to fetch {url} after {retries} attempts.")

# Example usage:
url = 'https://search.sunbiz.org/Inquiry/CorporationSearch/ByName'
response = make_request_with_retries(url)
print(response.data)


os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

# Disable SSL verification temporarily (use only for testing)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

# Google Sheets setup
SHEET_ID = '1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A'
SHEET_NAME = 'PALM BAY FINAL'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
CREDENTIALS_PATH = os.path.join(os.getcwd(), 'credentials.json')
TOKEN_PATH = os.path.join(os.getcwd(), 'token.json')

def authenticate_google_sheets():
    """Authenticate with Google Sheets API."""
    creds = None
    # Check if there are valid credentials available
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())  # Refresh the token if expired
        else:
            # If no credentials, prompt user for authentication
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    return creds

def update_sheet(credentials, data, row_index):
    # No need to use .authorize(), build automatically handles the credentials
    sheets = build('sheets', 'v4', credentials=credentials)
    range_ = f"{SHEET_NAME}!K{row_index}:O{row_index}"
    body = {'values': [data]}
    try:
        sheets.spreadsheets().values().update(
            spreadsheetId=SHEET_ID, range=range_, valueInputOption='RAW', body=body
        ).execute()
    except Exception as e:
        print(f"Error updating sheet: {e}")
        raise e

# Similarly for get_company_names, update the build to use credentials directly
def get_company_names(credentials):
    sheets = build('sheets', 'v4', credentials=credentials)
    range_ = f"{SHEET_NAME}!C2:C"
    try:
        result = sheets.spreadsheets().values().get(spreadsheetId=SHEET_ID, range=range_).execute()
        values = result.get('values', [])
        return [
            {'name': val[0].strip() if val else None, 'row_index': index + 2, 'is_business': is_business_entity(val[0].strip() if val else "")}
            for index, val in enumerate(values) if val and val[0]
        ]
    except Exception as e:
        print(f"Error fetching company names: {e}")
        raise e



# Check if the name represents a business entity
def is_business_entity(name):
    business_keywords = [" LLC", " Corp", " Inc", " Ltd", " Co", " Company", " Enterprises", " Associates", " Group"]
    return any(keyword.lower() in name.lower() for keyword in business_keywords)

# Scrape officer details from a page
def scrape_officer_details(driver):
    try:
        title = driver.find_element(By.XPATH, '//*[@id="maincontent"]/div[2]/div[6]/span[3]').text
    except:
        title = "No Title Found"

    try:
        officer_name = driver.find_element(By.XPATH, '//*[@id="maincontent"]/div[2]/div[6]').text
    except:
        officer_name = "No Name Found"

    try:
        officer_address = driver.find_element(By.XPATH, '//*[@id="maincontent"]/div[2]/div[6]/span[4]/div').text
    except:
        officer_address = "No Address Found"

    return {'title': title, 'officer_name': officer_name, 'officer_address': officer_address}

# Main script to scrape data
def main():
    # Authenticate Google Sheets
    credentials = authenticate_google_sheets()

    # Get company names
    companies = get_company_names(credentials)
    print('Retrieved companies:', companies)

    # Setup Chrome driver with headless option
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--remote-debugging-port=9222')
    driver = webdriver.Chrome(options=options)

    try:
        for company in companies:
            company_name = company['name']
            row_index = company['row_index']
            is_business = company['is_business']

            if not is_business:
                print(f"Skipping personal name: {company_name} (Row {row_index})")
                continue

            print(f"Processing: {company_name} (Row {row_index})")
            driver.get('https://search.sunbiz.org/Inquiry/CorporationSearch/ByName')
            search = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, 'SearchTerm')))
            search.send_keys(company_name, Keys.RETURN)

            try:
                WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, '#search-results table tbody tr')))
            except Exception as e:
                print(f"No search results for {company_name}")
            # Replace "auth" with "credentials" on these lines
                sheets = build('sheets', 'v4', credentials=credentials)
                continue

            rows = driver.find_elements(By.XPATH, '//*[@id="search-results"]/table/tbody/tr')
            company_found = False

            for row in rows:
                found_name = row.find_element(By.XPATH, './td[1]/a').text
                if company_name.lower() in found_name.lower():
                    row.find_element(By.XPATH, './td[1]/a').click()
                    company_found = True
                    break

            if not company_found:
                print(f"No match for {company_name}")
                # Replace "auth" with "credentials" on these lines
                sheets = build('sheets', 'v4', credentials=credentials)
                continue

            # Wait for page load and scrape data
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, 'main')))
            registered_name = driver.find_element(By.CSS_SELECTOR, '#maincontent > div.searchResultDetail > div.detailSection.corporationName > p:nth-child(2)').text
            status = driver.find_element(By.CSS_SELECTOR, '#maincontent .filingInformation span:nth-child(10)').text
            mail = driver.find_element(By.CSS_SELECTOR, '#maincontent .detailSection:nth-child(5) div').text
            agent = driver.find_element(By.CSS_SELECTOR, '#maincontent .detailSection:nth-child(6) span:nth-child(2)').text

            officer_details = scrape_officer_details(driver)

            company_data = [registered_name, status, mail, agent, f"{officer_details['title']} {officer_details['officer_name']} {officer_details['officer_address']}"]
            print(f"Officer Details: {officer_details}")
            # Replace "auth" with "credentials" on these lines
            sheets = build('sheets', 'v4', credentials=credentials)
            print(f"Logged data for {company_name}: {company_data}")
            
            update_sheet(credentials, company_data, row_index)

    except Exception as e:
        print(f"Error during execution: {e}")

    finally:
        driver.quit()

if __name__ == '__main__':
    main()
