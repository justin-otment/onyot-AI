import time
import re
import undetected_chromedriver as uc
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from bs4 import BeautifulSoup

# Google Sheets setup
SHEET_ID = '1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A'
SHEET_NAME = 'Cape Coral - ArcGIS'

# Local Chrome user profile settings
USER_DATA_DIR = "C:\\Users\\DELL\\AppData\\Local\\Google\\Chrome\\User Data"
PROFILE_DIRECTORY = "Profile 1"

# Authenticate with Google Sheets
def get_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("service-account.json", scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)

def parse_contact_info(html):
    soup = BeautifulSoup(html, 'html.parser')

    phone_numbers = []
    phone_types = []
    emails = []

    # Extract phone numbers (using a regex pattern to detect phone numbers)
    phone_spans = soup.find_all('a.dt-hd.link-to-more.olnk', string=re.compile(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'))
    for span in phone_spans:
        phone_numbers.append(span.get_text(strip=True))

    # Extract corresponding phone types, which are stored in the next 'span.smaller' element after each phone number
    for phone_span in phone_spans:
        next_span = phone_span.find_next('span', class_='smaller')  # Find the next span with 'smaller' class
        if next_span:
            phone_types.append(next_span.get_text(strip=True))

    # Extract emails from div.row.pl-md-1
    email_divs = soup.select('#personDetails > div:nth-child(12) > div.col-12.col-sm-11.pl-sm-1 > div:nth-child(2)')
    for email_div in email_divs:
        email_text = email_div.get_text(strip=True)
        # Only consider the text that looks like an email
        if re.match(r"[^@]+@[^@]+\.[^@]+", email_text):
            emails.append(email_text)

    return phone_numbers, phone_types, emails

# Update Google Sheets with parsed data
def update_google_sheet(sheet, phone_numbers, phone_types, emails, row):
    # Define maximum numbers of phones, phone types, and emails we will handle
    max_phones = 5
    max_emails = 3
    
    # Prepare the data to update
    phone_numbers = phone_numbers[:max_phones]
    phone_types = phone_types[:max_phones]
    
    update_data = []
    
    # Insert phone numbers and phone types into the respective columns (G - S)
    for i in range(max_phones):
        if i < len(phone_numbers):
            update_data.append(phone_numbers[i])
        else:
            update_data.append('')
        
        if i < len(phone_types):
            update_data.append(phone_types[i])
        else:
            update_data.append('')
    
    # Add emails to the list (maximum of 3 emails)
    for i in range(max_emails):
        if i < len(emails):
            update_data.append(emails[i])
        else:
            update_data.append('')
    
    # Update the cells starting from column G (index 7) for the row
    for i, value in enumerate(update_data):
        sheet.update_cell(row, 7 + i, value)

    print(f"✅ Row {row} updated successfully!")

# Main process
def main():
    sheet = get_sheet()

    # Fetch all URLs from column B (starting at row 2)
    urls = sheet.col_values(2)[1:]

    # Set up undetected chromedriver options with local profile
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument(f"--profile-directory={PROFILE_DIRECTORY}")
    options.add_argument("--start-maximized")

    # Launch undetected Chrome with correct version_main for Chrome 133
    driver = uc.Chrome(
        options=options,
        version_main=133  # This forces compatibility with your installed Chrome version (133)
    )

    # Iterate over the URLs and fetch data
    for idx, url in enumerate(urls):
        try:
            print(f'Fetching: {url}')
            driver.get(url)
            time.sleep(10)  # Give page time to load (tune this if needed)

            html = driver.page_source

            phone_numbers, phone_types, emails = parse_contact_info(html)

            row = idx + 2  # Google Sheets rows start at 1, so add 1 to index and 1 to skip header row

            # Update the Google Sheet with extracted data
            update_google_sheet(sheet, phone_numbers, phone_types, emails, row)

        except Exception as e:
            print(f"Error processing {url}: {e}")

    driver.quit()

if __name__ == '__main__':
    main()
