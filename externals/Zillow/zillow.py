from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
import csv
from undetected_chromedriver import Chrome, ChromeOptions
import ssl
import time
from urllib3.exceptions import ProtocolError
from fake_useragent import UserAgent
import os

# Initialize the UserAgent object
ua = UserAgent()

# Constants - Adjusted for Linux (GitHub CI)
USER_DATA_DIR = os.path.expanduser("~/.config/google-chrome")  # Linux Chrome profile
PROFILE_DIRECTORY = "Default"

def setup_chrome_driver():
    """Set up Chrome driver with GitHub CI-compatible options."""
    options = ChromeOptions()
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument(f"--remote-debugging-port=9222")  # Explicit port for stability
    options.add_argument(f"--profile-directory={PROFILE_DIRECTORY}")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"user-agent={ua.random if ua.random else 'Mozilla/5.0 (X11; Linux x86_64)'}")  # Prevent SSL issues with fake_useragent
    return Chrome(options=options)

# Function to check if an element has been processed
def is_processed(href, processed_urls):
    return href in processed_urls

def scrape_zillow_data(max_pages=30):
    data = []
    processed_urls = set()  # Set to store processed URLs

    for page in range(1, max_pages + 1):
        try:
            print(f"Scraping page {page}...")
            if page > 1:
                current_url = driver.current_url
                next_button_selector = 'a[title="Next page"]'
                next_button = WebDriverWait(driver, 60).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, next_button_selector))
                )
                driver.execute_script("arguments[0].scrollIntoView();", next_button)
                next_button.click()
                
                # Wait for the next page to load and URL to change
                WebDriverWait(driver, 60).until(
                    EC.url_changes(current_url)
                )
            
            page_element = WebDriverWait(driver, 60).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, 'div.result-list-container'))
            )

            parent_elements = page_element.find_elements(By.CSS_SELECTOR, 'div.StyledPropertyCardDataWrapper-c11n-8-109-1__sc-hfbvv9-0')
            
            for parent in parent_elements:
                retry_count = 3
                for attempt in range(retry_count):
                    try:
                        driver.execute_script("arguments[0].scrollIntoView();", parent)
                        time.sleep(1)

                        address = parent.find_element(By.CSS_SELECTOR, 'address').text
                        link_element = parent.find_element(By.CSS_SELECTOR, 'a')
                        href = link_element.get_attribute('href')

                        if address and href and not is_processed(href, processed_urls):
                            data.append({"Address": address, "URL": href})
                            processed_urls.add(href)  # Add to processed URLs set
                            print(f"Address: {address}, URL: {href}")
                        break
                    except StaleElementReferenceException:
                        if attempt < retry_count - 1:
                            print("Retrying stale element reference...")
                            time.sleep(1)
                        else:
                            print("Failed to recover from stale element reference.")
                            raise
        
        except Exception as e:
            print(f"An error occurred on page {page}: {e}")
            break

    return data

# Initialize the WebDriver
driver = setup_chrome_driver()

# Step 1: Navigate to the URL
url = "https://www.zillow.com/cape-coral-fl/?searchQueryState=%7B%22pagination%22%3A%7B%7D%2C%22isMapVisible%22%3Atrue%2C%22mapBounds%22%3A%7B%22west%22%3A-83.05769816406251%2C%22east%22%3A-80.93733683593751%2C%22south%22%3A25.92641469887041%2C%22north%22%3A27.391749932595488%7D%2C%22usersSearchTerm%22%3A%22Cape%20Coral%20FL%22%2C%22regionSelection%22%3A%5B%7B%22regionId%22%3A30742%7D%5D%2C%22filterState%22%3A%7B%22sort%22%3A%7B%22value%22%3A%22pricea%22%7D%2C%22price%22%3A%7B%22min%22%3Anull%2C%22max%22%3A300000%7D%2C%22mp%22%3A%7B%22min%22%3Anull%2C%22max%22%3A1528%7D%2C%22sf%22%3A%7B%22value%22%3Afalse%7D%2C%22tow%22%3A%7B%22value%22%3Afalse%7D%2C%22mf%22%3A%7B%22value%22%3Afalse%7D%2C%22con%22%3A%7B%22value%22%3Afalse%7D%2C%22apa%22%3A%7B%22value%22%3Afalse%7D%2C%22manu%22%3A%7B%22value%22%3Afalse%7D%2C%22apco%22%3A%7B%22value%22%3Afalse%7D%2C%22lot%22%3A%7B%22min%22%3A10890%2C%22max%22%3A21780%2C%22units%22%3Anull%7D%7D%2C%22isListVisible%22%3Atrue%2C%22mapZoom%22%3A9%7D"
driver.get(url)

try:
    data = scrape_zillow_data(max_pages=30)
    if not data:  # Ensure data is a list before writing to CSV
        data = []
    csv_file_path = os.path.join(os.getcwd(), "zillow_active_listings.csv")
    with open(csv_file_path, mode='w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["Address", "URL"])
        writer.writeheader()
        writer.writerows(data)
    
finally:
    driver.quit()
