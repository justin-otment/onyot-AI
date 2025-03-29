import os
import random
import asyncio
from undetected_chromedriver import Chrome, ChromeOptions
from performSearch_FastPpl import perform_search, find_best_match
from utilities import increment_value_randomly, get_safe, random_delay
from extractionProcess_beta import extract_comprehensive_data
from csvHandler_beta import initialize_csv, append_to_csv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import re
import urllib3
import ssl
import time
from urllib3.exceptions import ProtocolError
import requests
from fake_useragent import UserAgent


# Initialize the UserAgent object
ua = UserAgent()

# Function to make a request with a random user agent
def fetch_url(url):
    headers = {
        'User-Agent': ua.random  # Generate a random user agent
    }
    response = requests.get(url, headers=headers)
    return response

# Example usage
url = 'https://www.fastpeoplesearch.com/'
response = fetch_url(url)
print(f"Status Code: {response.status_code}")
print(f"Response Text (First 500 chars):\n{response.text[:500]}")

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
url = 'https://www.fastpeoplesearch.com/'
response = make_request_with_retries(url)
print(response.data)

os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

# Disable SSL verification temporarily (use only for testing)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

# Define file paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")

# Constants
USER_DATA_DIR = "C:\\Users\\DELL\\AppData\\Local\\Google\\Chrome\\User Data"
PROFILE_DIRECTORY = "Profile 1"
SHEET_ID = "1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A"

def setup_chrome_driver():
    """Set up Chrome driver with custom options."""
    options = ChromeOptions()
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument(f"--remote-debugging-port=53221")
    options.add_argument(f"--profile-directory={PROFILE_DIRECTORY}")
    options.add_argument(f"--start-maximized")
    return Chrome(options=options)

def authenticate_google_sheets():
    """Authenticate with Google Sheets API."""
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
            creds = flow.run_local_server(port=53221)
            with open(TOKEN_PATH, "w") as token:
                token.write(creds.to_json())
    return build("sheets", "v4", credentials=creds)

def get_sheet_data(sheet_id, range_name):
    """Fetch data from a Google Sheets range."""
    try:
        service = authenticate_google_sheets()
        sheet = service.spreadsheets()
        result = sheet.values().get(spreadsheetId=sheet_id, range=range_name).execute()
        return result.get("values", [])
    except Exception as e:
        print(f"Error fetching data from Google Sheets: {e}")
        return []

def get_safe(data_list, index, key=None):
    """Safely access an element in a list or dictionary."""
    if data_list and len(data_list) > index:
        return data_list[index] if key is None else data_list[index].get(key, '')
    return ''

def get_safe_email(email_data, index):
    """Safely access an email from the list."""
    if email_data and len(email_data) > index:
        return email_data[index]
    return ''

def limit_emails(email_data, max_emails=3):
    """Limit the number of emails to a specified max count."""
    return email_data[:max_emails]

async def process_row(driver, street, zipcode, target_name_set, fallback_street_data, fallback_zip_data, processed_queries, i):
    try:
        # Perform the search for the current row
        await perform_search(driver, street, zipcode)
        await random_delay(1, 5)  # Add random delay

        # Find the best match
        match_found = await find_best_match(
            driver, target_name_set, fallback_street_data[0][0], street, zipcode, fallback_zip_data
        )
        await random_delay(1, 5)  # Add random delay

        if not match_found:
            print(f"No match found for row {i + 2}. Skipping.")
            return

        # Extract full data from the matched page
        extracted_data = await extract_comprehensive_data(driver, target_name_set)
        await random_delay(1, 5)  # Add random delay

        if not isinstance(extracted_data, dict):
            print(f"Invalid data format for row {i + 2}. Expected a dictionary.")
            return

        # Extract phone numbers, types, and email data
        phone_numbers = extracted_data.get('phone_numbers', [])
        phone_types = extracted_data.get('phone_types', [])
        email_data = extracted_data.get('email_data', [])

        # Ensure phone numbers and types are consistent in length
        max_length = max(len(phone_numbers), len(phone_types))
        phone_numbers.extend([''] * (max_length - len(phone_numbers)))
        phone_types.extend([''] * (max_length - len(phone_types)))

        # Prepare the data to be written to CSV
        data_to_write = {
            "Mailing Address": extracted_data.get('current_mailing_address', ''),
            "Subject Property": fallback_street_data[0][i][0] if len(fallback_street_data[0]) > i and fallback_street_data[0][i] else '',
            "City": extracted_data.get("city", ""),
            "State": extracted_data.get("state", ""),
            "Zipcode": fallback_zip_data[0][i][0] if len(fallback_zip_data[0]) > i and fallback_zip_data[0][i] else '',
            "First Name": extracted_data.get('first_name', ''),
            "Last Name": extracted_data.get('last_name', ''),
            "Phone 1": phone_numbers[0] if len(phone_numbers) > 0 else '',
            "Phone Type 1": phone_types[0] if len(phone_types) > 0 else '',
            "Phone 2": phone_numbers[1] if len(phone_numbers) > 1 else '',
            "Phone Type 2": phone_types[1] if len(phone_types) > 1 else '',
            "Phone 3": phone_numbers[2] if len(phone_numbers) > 2 else '',
            "Phone Type 3": phone_types[2] if len(phone_types) > 2 else '',
            "Phone 4": phone_numbers[3] if len(phone_numbers) > 3 else '',
            "Phone Type 4": phone_types[3] if len(phone_types) > 3 else '',
            "Phone 5": phone_numbers[4] if len(phone_numbers) > 4 else '',
            "Phone Type 5": phone_types[4] if len(phone_types) > 4 else '',
            "Email": email_data[0] if len(email_data) > 0 else '',
            "Email 2": email_data[1] if len(email_data) > 1 else '',
            "Email 3": email_data[2] if len(email_data) > 2 else '',
            "Relative First Name": extracted_data.get('relativeFirstName', ''),
            "Relative Last Name": extracted_data.get('relativeLastName', ''),
            "Relative Phone 1": get_safe(extracted_data.get('relativePhoneNumbers', []), 0),
            "Relative Phone Type 1": get_safe(extracted_data.get('relativePhoneTypes', []), 0),
            "Relative Phone 2": get_safe(extracted_data.get('relativePhoneNumbers', []), 1),
            "Relative Phone Type 2": get_safe(extracted_data.get('relativePhoneTypes', []), 1),
            "Relative Phone 3": get_safe(extracted_data.get('relativePhoneNumbers', []), 2),
            "Relative Phone Type 3": get_safe(extracted_data.get('relativePhoneTypes', []), 2),
            "Relative Email 1": get_safe_email(extracted_data.get('relativeEmails', []), 0),
            "Relative Email 2": get_safe_email(extracted_data.get('relativeEmails', []), 1),
            "Relative Email 3": get_safe_email(extracted_data.get('relativeEmails', []), 2),
        }

        # Write the extracted data to the CSV file
        append_to_csv(data_to_write, 'arcGIS_cape2.csv')

        print(f"Row {i + 2} processed successfully.")

    except Exception as e:
        print(f"Error occurred in row {i + 2}: {e}")

# Helper functions
async def increment_value_randomly(min_value, max_value, step):
    """Randomly increments a value."""
    value = random.randint(min_value, max_value)
    incremented_value = value + step
    await asyncio.sleep(1)  # Simulate async operation
    return incremented_value

def delete_cookies(driver):
    """Deletes all cookies in the current browser session."""
    try:
        driver.delete_all_cookies()
        print("Cookies deleted successfully.")
    except Exception as e:
        print(f"Error while deleting cookies: {e}")

def is_business_name(name):
    """Determine if the given name is a business."""
    business_keywords = [" LLC", " Inc", " Corp", " Co", " Ltd", " Enterprises", " Properties", " Group", " Grp"]
    return any(keyword.lower() in name.lower() for keyword in business_keywords)

def extract_officer_details(details_text):
    """Extract names, street addresses, and zip codes from officer details text."""
    officer_details = []
    sections = re.split(r"Title\s", details_text)

    for section in sections:
        if not section.strip():
            continue

        name_match = re.search(r"([A-Za-z]+,\s[A-Za-z]+)", section)
        name = name_match.group(1).strip() if name_match else None

        street_match = re.search(
            r"(\d{1,5}\s[\w\s.]+(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Blvd))", 
            section, re.IGNORECASE
        )
        street = street_match.group(1).strip() if street_match else None

        zip_match = re.search(r"\b\d{5}\b", section)
        zip_code = zip_match.group(0).strip() if zip_match else None

        if name and street and zip_code:
            officer_details.append({"name": name, "street": street, "zip": zip_code})

    return officer_details

def split_target_names(target_data, delimiters=[",", ";", "&"]):
    """Splits target names within each cell into individual names."""
    delimiter_pattern = "|".join(map(re.escape, delimiters))
    split_data = []

    for row in target_data:
        if row and row[0]:
            names = re.split(delimiter_pattern, row[0])
            split_data.append([name.strip() for name in names if name.strip()])
        else:
            split_data.append([])

    return split_data

def extract_street_address(text):
    """Extract the street address from the given text."""
    lines = text.split('\n')
    for line in lines:
        if re.match(r'^\d+\s+\w+', line.strip()):
            return line.strip()
    return None

def extract_zip_code(text):
    """Extract the last 5 digits from the given text."""
    match = re.search(r'\d{5}(?!.*\d)', text)
    return match.group(0) if match else None

def is_valid_zipcode(zipcode):
    # Define the regular expression for a valid ZIP code (5 digits)
    return re.match(r"^\d{5}$", zipcode) is not None

async def main():
    driver = setup_chrome_driver()
    initialize_csv()
    processed_queries = set()

    try:
        # Fetch data from Google Sheets
        street_data = get_sheet_data(SHEET_ID, "Cape Coral - ArcGIS!D216:D")
        zip_data = get_sheet_data(SHEET_ID, "Cape Coral - ArcGIS!U216:U")
        target_names = [
            split_target_names(get_sheet_data(SHEET_ID, f"Cape Coral - ArcGIS!{col}216:{col}"))
            for col in ["C"]
        ]
        fallback_street_data = [
            get_sheet_data(SHEET_ID, f"Cape Coral - ArcGIS!{col}216:{col}")
            for col in ["B"]
        ]
        fallback_zip_data = [
            get_sheet_data(SHEET_ID, f"Cape Coral - ArcGIS!{col}216:{col}")
            for col in ["T"]
        ]
        officer_details_data = get_sheet_data(SHEET_ID, "Cape Coral - ArcGIS!R216:R")

        # Counter for tab management
        processed_count = 0

        for i, street_entry in enumerate(street_data):
            if i >= len(zip_data) or i >= len(target_names[0]):
                print(f"Skipping row {i + 2}: Missing corresponding data.")
                continue

            # Your existing code with the added validation
            street = street_entry[0] if street_entry else None
            zipcode = zip_data[i][0] if zip_data[i] else None

            if street and '\n' in street:
                street = extract_street_address(street)
            if zipcode and '\n' in zipcode:
                zipcode = extract_zip_code(zipcode)

            fallback_street = (
                fallback_street_data[0][i][0]
                if i < len(fallback_street_data[0]) and fallback_street_data[0][i]
                else None
            )
            fallback_zip = (
                fallback_zip_data[0][i][0]
                if i < len(fallback_zip_data[0]) and fallback_zip_data[0][i]
                else None
            )

            target_name_set = [
                name.strip() for name in target_names[0][i] if name
            ] if i < len(target_names[0]) else []

            # Add ZIP code validation
            if not street or not zipcode or not target_name_set or not is_valid_zipcode(zipcode):
                print(f"Skipping row {i + 2}: Invalid data or invalid ZIP code.")
                continue

            query_key = f"{street}-{zipcode}"
            if query_key in processed_queries:
                print(f"Skipping row {i + 2}: Duplicate query.")
                

            for name in target_name_set:
                if name and is_business_name(name):
                    if i >= len(officer_details_data):
                        print(f"Skipping row {i + 2}: Missing officer details.")
                        continue

                    officer_details = officer_details_data[i][0] if officer_details_data[i] else None
                    if officer_details:
                        extracted_officers = extract_officer_details(officer_details)
                        if extracted_officers:
                            officer = extracted_officers[0]
                            street = officer["street"]
                            zipcode = officer["zip"]
                            target_name_set = [officer["name"]]
                            print(f"Business identified. Using officer details for row {i + 2}: {officer}")

            await process_row(
                driver, street, zipcode, target_name_set,
                fallback_street_data, fallback_zip_data, processed_queries, i
            )

            processed_queries.add(query_key)
            delete_cookies(driver)
            await random_delay(2, 30)

            # Increment the counter
            processed_count += 1

            # Tab management: Every 10 rows, open a new tab, switch, and close the previous one
            if processed_count % 10 == 0:
                # Open a new tab
                driver.execute_script("window.open('about:blank', '_blank');")
                driver.switch_to.window(driver.window_handles[-1])  # Switch to the new tab

                # Close the previous tab
                if len(driver.window_handles) > 1:
                    driver.switch_to.window(driver.window_handles[-2])
                    driver.close()

                # Switch back to the new tab
                driver.switch_to.window(driver.window_handles[-1])

    except Exception as e:
        print(f"Error during execution: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    asyncio.run(main())