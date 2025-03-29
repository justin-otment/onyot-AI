from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

# Google Sheets API setup
SHEET_ID = '1yKNlPlKz88-LTdUr54gWpconmUJFrXvtEuN4ou07vHo'
SHEET_NAME = 'Warm-Hot Leads'

SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
CREDENTIALS_FILE = 'credentials.json'  # Path to your credentials.json file

# Setup Google Sheets API
credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, SCOPES)
gc = gspread.authorize(credentials)
sheet = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)

# Fetch Zillow links from Column M (13th column)
zillow_links = sheet.col_values(13)[1:]  # Skip header

# Setup WebDriver options
chrome_options = Options()
chrome_options.add_argument("--start-maximized")
driver = webdriver.Chrome(options=chrome_options)

# Function to scroll into view
def scroll_into_view(element):
    driver.execute_script("arguments[0].scrollIntoView({ behavior: 'smooth', block: 'center' });", element)

# Iterate through Zillow links
for index, url in enumerate(zillow_links, start=2):  # Start from row 2
    if not url.strip():
        continue
    try:
        driver.get(url)
        wait = WebDriverWait(driver, 60)

        # Wait for the main container
        container = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '#search-detail-lightbox > div.sc-fFRahO.ZOZib > div:nth-child(2) > div.sc-dXGMVt.eHMxTz.layout-wrapper > section > div > div.layout-content-container')))
        scroll_into_view(container)

        # Extract data
        def extract_text(selector):
            try:
                element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                scroll_into_view(element)
                return element.text.strip()
            except:
                return 'N/A'

        bedrooms = extract_text('#search-detail-lightbox > div.sc-fFRahO.ZOZib > div:nth-child(2) > div.sc-dXGMVt.eHMxTz.layout-wrapper > section > div > div.layout-content-container > div.layout-static-column-container > div > div > div:nth-child(2) > div > div > div > div > div.Flex-c11n-8-99-3__sc-n94bjd-0.BgmpZ > div.Flex-c11n-8-99-3__sc-n94bjd-0.cvmxyp > div > div:nth-child(1) > span.Text-c11n-8-99-3__sc-aiai24-0.styles__StyledValueText-fshdp-8-106-0__sc-12ivusx-1.dFxMdJ.bfIPme.--medium')
        bathrooms = extract_text('#search-detail-lightbox > div.sc-fFRahO.ZOZib > div:nth-child(2) > div.sc-dXGMVt.eHMxTz.layout-wrapper > section > div > div.layout-content-container > div.layout-static-column-container > div > div > div:nth-child(2) > div > div > div > div > div.Flex-c11n-8-99-3__sc-n94bjd-0.BgmpZ > div.Flex-c11n-8-99-3__sc-n94bjd-0.cvmxyp > div > div:nth-child(2) > span.Text-c11n-8-99-3__sc-aiai24-0.styles__StyledValueText-fshdp-8-106-0__sc-12ivusx-1.dFxMdJ.bfIPme.--medium')
        property_type = extract_text('#search-detail-lightbox > div.sc-fFRahO.ZOZib > div:nth-child(2) > div.sc-dXGMVt.eHMxTz.layout-wrapper > section > div > div.layout-content-container > div.layout-static-column-container > div > div > div:nth-child(4) > div > div > div > div:nth-child(1) > span')
        floor_size = extract_text('#search-detail-lightbox > div.sc-fFRahO.ZOZib > div:nth-child(2) > div.sc-dXGMVt.eHMxTz.layout-wrapper > section > div > div.layout-content-container > div.layout-static-column-container > div > div > div:nth-child(2) > div > div > div > div > div.Flex-c11n-8-99-3__sc-n94bjd-0.BgmpZ > div.Flex-c11n-8-99-3__sc-n94bjd-0.cvmxyp > div > div:nth-child(3) > span.Text-c11n-8-99-3__sc-aiai24-0.styles__StyledValueText-fshdp-8-106-0__sc-12ivusx-1.dFxMdJ.bfIPme.--medium')

        # Update Google Sheet
        sheet.update_cell(index, 14, bedrooms)  # Column N
        sheet.update_cell(index, 15, bathrooms)  # Column O
        sheet.update_cell(index, 16, property_type)  # Column P
        sheet.update_cell(index, 17, floor_size)  # Column Q

        print(f"Row {index} updated: {bedrooms}, {bathrooms}, {property_type}, {floor_size}")

    except Exception as e:
        print(f"Failed at row {index}: {e}")

    time.sleep(2)  # Prevent being flagged as a bot

# Close WebDriver
driver.quit()
