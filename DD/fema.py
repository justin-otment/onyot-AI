import os
import time
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from webdriver_manager.microsoft import EdgeChromiumDriverManager
from selenium.webdriver.edge.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import urllib3
from urllib3.exceptions import ProtocolError
import ssl
import time

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
url = 'https://hazards-fema.maps.arcgis.com/apps/webappviewer/index.html?id=8b0adb51996444d4879338b5529aa9cd'
response = make_request_with_retries(url)
print(response.data)


os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

# Disable SSL verification temporarily (use only for testing)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

SHEET_ID = "1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A"
SHEET_NAME = "Cape Coral - ArcGIS"
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
CREDENTIALS_PATH = os.path.join(os.getcwd(), "credentials.json")
TOKEN_PATH = os.path.join(os.getcwd(), "token.json")
URL = "https://hazards-fema.maps.arcgis.com/apps/webappviewer/index.html?id=8b0adb51996444d4879338b5529aa9cd"


def setup_edge_driver():
    """Set up Edge driver using webdriver-manager."""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--enable-unsafe-swiftshader")

    # Automatically download and install the Edge driver
    driver_path = EdgeChromiumDriverManager().install()

    # Setup service with the driver path
    service = Service(driver_path)

    # Return the Edge driver instance
    return webdriver.Edge(service=service, options=options)


def authenticate_google_sheets():
    """Authenticate and return a Google Sheets API service."""
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
        creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, "w") as token_file:
            token_file.write(creds.to_json())
    return build("sheets", "v4", credentials=creds)


def human_like_mouse_movement(driver, element):
    """Simulate human-like mouse movement to an element."""
    actions = ActionChains(driver)
    actions.move_to_element(element).perform()


def fetch_data_and_update_sheet():
    sheets = authenticate_google_sheets()
    sheet = sheets.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f'{SHEET_NAME}!B2:B'
    ).execute()
    sheet_data = sheet.get('values', [])

    # Initialize the WebDriver once
    driver = setup_edge_driver()  # Replace with undetected Chrome driver setup if needed
    driver.get(URL)

    for i, row in enumerate(sheet_data):
        site = row[0] if row else None
        if not site or not site.strip():
            print(f"Skipping empty or blank cell at row {i + 2}")
            continue

        try:
            # Navigate back to the initial URL for the next sequence
            driver.get(URL)
            print(f"Processing row {i + 2} with site: {site}")

            try:
                site_input = WebDriverWait(driver, 60).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="esri_dijit_Search_0_input"]'))
                )
                site_input.send_keys(site)
                site_input.send_keys(Keys.RETURN)
            except Exception as e:
                print(f"Error processing row {i + 2}: {e}")
                continue  # Skip to the next iteration

            # Dismiss warning if present
            try:
                warning_button = WebDriverWait(driver, 60).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="widgets_Splash_Widget_14"]/div[2]/div[2]/div[2]/button'))
                )
                human_like_mouse_movement(driver, warning_button)
                warning_button.click()
                time.sleep(3)
                print("Warning dismissed successfully.")
            except Exception as e:
                print("Warning button not found or clickable, continuing...")

            try:
                close_other = WebDriverWait(driver, 60).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="_7_panel"]/div[1]/div/div[3]'))
                )
                human_like_mouse_movement(driver, close_other)
                close_other.click()
                print("Closed other pop-up.")
            except Exception as e:
                print("Close button not found or clickable, continuing...")

            try:
                pointer = WebDriverWait(driver, 60).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="map_graphics_layer"]'))
                )
                human_like_mouse_movement(driver, pointer)
                pointer.click()
                time.sleep(3)
                print("Pointer clicked successfully.")
            except Exception as e:
                print("Looking for the pointer.")

            try:
                # Wait for modal to appear
                modal = WebDriverWait(driver, 60).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.contentPane'))
                )
                print("Modal detected.")

                # Continuously check for the flood zone element and click the arrow button if not found
                while True:
                    try:
                        # Initialize flag to check if "FLD_ZONE" was found
                        found_fld_zone = False

                        # Print all attribute texts with the specified CSS selector
                        attribute_texts = driver.find_elements(By.CSS_SELECTOR, 'td.attrName')
                        for attribute in attribute_texts:
                            attribute_text = attribute.text
                            print(f"Attribute text: {attribute_text}")

                            # Check if the text matches "FLD_ZONE"
                            if "FLD_ZONE" in attribute_text:
                                found_fld_zone = True
                                # Perform text extraction on the sibling element with the specified CSS selector
                                flood_zone_element = attribute.find_element(By.XPATH, 'following-sibling::td[@class="attrValue"]')
                                flood_zone = flood_zone_element.text
                                print(f"Flood zone extracted: {flood_zone}")

                                # Update the Google Sheet with the extracted flood zone data
                                sheets.spreadsheets().values().update(
                                    spreadsheetId=SHEET_ID,
                                    range=f"{SHEET_NAME}!H{i + 2}",
                                    valueInputOption="RAW",
                                    body={"values": [[flood_zone]]}
                                ).execute()
                                print("Flood zone data updated in Google Sheets.")
                                break  # Exit loop once data is updated

                        # If the flood zone was found, break the loop
                        if found_fld_zone:
                            break

                        # If no matching attribute text is found, click the arrow button
                        try:
                            # Wait for the arrow button to be clickable
                            arrow_button = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((By.XPATH, '//*[@id="map_root"]/div[3]/div[1]/div[1]/div/div[4]'))
                            )

                            # Scroll to the button
                            driver.execute_script("arguments[0].scrollIntoView(true);", arrow_button)
                            print("Arrow button in view.")

                            # Debug: Take screenshot
                            driver.save_screenshot("arrow_button_debug.png")

                            # Simulate human-like movement and click
                            human_like_mouse_movement(driver, arrow_button)
                            arrow_button.click()
                            print("Arrow button clicked successfully.")

                            # Small delay to prevent rapid loop execution
                            time.sleep(1)

                        except Exception as e:
                            # Break the loop if the element is no longer present or clickable
                            print(f"Arrow button no longer clickable or present: {e}")
                            break

                    except Exception as e:
                        print(f"Flood zone label not found: {e}")

            except Exception as e:
                print(f"Error interacting with the modal or arrow button: {e}")
                driver.save_screenshot("arrow_button_error.png")  # Capture screenshot on failure




        except Exception as e:
            print(f"Error processing row {i + 2}: {e}")
        finally:
            pass

    driver.quit()


if __name__ == "__main__":
    fetch_data_and_update_sheet()
