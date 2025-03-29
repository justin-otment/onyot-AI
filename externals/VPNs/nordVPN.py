from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from undetected_chromedriver import Chrome, ChromeOptions
import random
import time
from urllib3.exceptions import ProtocolError
import urllib3
import ssl
import os
import subprocess  # For running the AHK script

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
url = 'https://www.google.com/'
response = make_request_with_retries(url)
print(response.data)

os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

# Disable SSL verification temporarily (use only for testing)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
context = ssl.create_default_context()
context.check_hostname = False
context.verify_mode = ssl.CERT_NONE

USER_DATA_DIR = "C:\\Users\\DELL\\AppData\\Local\\Google\\Chrome\\User Data"
PROFILE_DIRECTORY = "Profile 1"
chromedriver_path = r'C:\Users\DELL\Documents\Onyot.ai\Lead_List-Generator\python tests\chromedriver.exe'
nordvpn_extension_path = r'C:\Users\DELL\AppData\Local\\Google\Chrome\User Data\Profile 1\Extensions\\fjoaledfpmneenckfbpdfhkmimnjocfa\\4.11.0_0'

# Custom Chrome profile setup
def setup_chrome_driver():
    """Set up Chrome driver with custom options."""
    options = ChromeOptions()
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument(f"--profile-directory={PROFILE_DIRECTORY}")
    options.add_argument(f"--remote-debugging-port=53221")
    options.add_argument(f"--start-maximized")
    return Chrome(options=options)

# Initialize the WebDriver with custom profile
driver = setup_chrome_driver()

# Increase timeout settings
driver.set_page_load_timeout(60)
driver.set_script_timeout(60)

# Open a new tab
driver.execute_script("window.open('');")
time.sleep(2)

# Switch to the new tab and open the extension
driver.switch_to.window(driver.window_handles[1])
driver.get('chrome-extension://fjoaledfpmneenckfbpdfhkmimnjocfa/popup.html')

# Wait for the extension page to load
time.sleep(5)

# Call the AHK script to interact with the extension
ahk_script_path = r'C:\Users\DELL\Documents\Onyot.ai\Lead_List-Generator\python tests\externals\VPNs\nord.ahk'
subprocess.call(['C:\\Program Files\\AutoHotkey\\Compiler\\Ahk2Exe.exe', ahk_script_path])

# Verify if the IP has changed (add your verification code here)

# Close the browser
driver.quit()
