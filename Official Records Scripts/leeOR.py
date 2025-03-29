import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from datetime import datetime
import os
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

# Setup Chrome options for headless mode
chrome_options = Options()
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-images")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-software-rasterizer")
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--enable-unsafe-swiftshader")

# Initialize WebDriver
driver = webdriver.Chrome(options=chrome_options)
actions = ActionChains(driver)

# Create a directory for screenshots if it doesn't exist
if not os.path.exists("screenshots"):
    os.makedirs("screenshots")

# Function to take a screenshot in case of error
def take_screenshot():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = f"screenshots/screenshot_{timestamp}.png"
    driver.save_screenshot(screenshot_path)
    print(f"Screenshot taken: {screenshot_path}")

# Function to load the page with retry mechanism
def load_page_with_retry(driver, url, retries=3, delay=5):
    for attempt in range(retries):
        try:
            driver.get(url)
            return
        except TimeoutException as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(delay)  # wait before retrying
        except WebDriverException as e:
            print(f"WebDriver error in attempt {attempt + 1}: {e}")
            time.sleep(delay)  # wait before retrying

    take_screenshot()  # Take screenshot on failure
    raise Exception("Failed to load the page after several attempts")


# data extraction from County Official Record Search
def record_date(driver):
    # Wait for all elements matching the CSS selector to be present
    record_dates = WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#doc_3785942_1 > td:nth-child(9)"))
    )
    
    # Extract text from each element
    record_date_texts = [record_date.text for record_date in record_dates]
    return record_date_texts

def doc_type(driver):
    # Wait for all elements matching the CSS selector to be present
    doc_types = WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#doc_3785942_1 > td:nth-child(10)"))
    )
    
    # Extract text from each element
    doc_type_texts = [doc_type.text for doc_type in doc_types]
    return doc_type_texts

def consideration_amount(driver):
    # Wait for all elements matching the CSS selector to be present
    consideration_amounts = WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#doc_3785942_1 > td:nth-child(5)"))
    )
    
    # Extract text from each element
    consideration_amounts_texts = [consideration_amounts.text for consideration_amounts in consideration_amounts]
    return consideration_amounts_texts

def grantor(driver):
    # Wait for all elements matching the CSS selector to be present
    grantors = WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#doc_3785942_1 > td:nth-child(7)"))
    )
    
    # Extract text from each element
    grantors_texts = [grantor.text for grantor in grantors]
    return grantors_texts

def clerk_file_number(driver):
    # Wait for all elements matching the CSS selector to be present
    clerk_file_numbers = WebDriverWait(driver, 10).until(
        EC.presence_of_all_elements_located((By.CSS_SELECTOR, "#doc_3785942_1 > td:nth-child(14)"))
    )
    
    # Extract text from each element
    clerk_file_number_texts = [clerk_file_number.text for clerk_file_number in clerk_file_numbers]
    return clerk_file_number_texts


# Main execution
try:
    load_page_with_retry(driver, "https://or.leeclerk.org/LandMarkWeb/Home/Index")

    #login first
    login_link = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#topNavLinksLogon > a"))
    )
    login_link.click()
    
    time.sleep(1)
    
    #input username
    username = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#UserName"))
    )
    username.send_keys("justinejohn.sale@gmail.com")
    
    time.sleep(1)

    #input pw
    pw = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#Password"))
    )
    pw.send_keys("w!axY^3eI8zgxX")
    
    time.sleep(1)
    
    login_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#bodySection > div > div > div > div > div:nth-child(1) > form > div > fieldset > p > input"))
    )
    login_button.click()
    
    time.sleep(1)
    
    # Click the image element
    image_element = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#bodySection > div > div > div:nth-child(4) > div > div:nth-child(1) > a > img"))
    )
    image_element.click()

    time.sleep(1)

    # Handle Terms & Conditions pop-up
    WebDriverWait(driver, 10).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "#disclaimer"))
    )

    accept_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#idAcceptYes"))
    )
    accept_button.click()
    
    time.sleep(1)
    
    driver.refresh()
    
    time.sleep(1)

    # Fill the form with the provided data
    name_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#name-Name"))
    )
    name_input.send_keys("MELENDEZ HENRY")
    
    time.sleep(1)

    begin_date_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#beginDate-Name"))
    )
    begin_date_input.click()
    actions.key_down(Keys.CONTROL).send_keys('a').key_up(Keys.CONTROL).perform()
    begin_date_input.send_keys("01/09/2004")
    
    time.sleep(1)
    
    # affirm with captcha
    captcha = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR,"#recaptcha-anchor > div.recaptcha-checkbox-border"))
    )
    time.sleep(7)
    captcha.click()
        
    time.sleep(1)

    # Submit the form
    submit_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "#submit-Name"))
    )
    submit_button.click()
    
    time.sleep(1)

    print("Form submitted successfully.")
    
    time.sleep(180)
    
    record_date(driver)
    time.sleep(1)
    doc_type(driver)
    time.sleep(1)
    consideration_amount(driver)
    time.sleep(1)
    grantor(driver)
    time.sleep(1)
    clerk_file_number(driver)
    time.sleep(1)
    
    # Fill the form with the provided data
    Lo_Li = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "#topNavLinksLogon > a"))
    )
    Lo_Li.click()

    time.sleep(1)

except Exception as e:
    print(f"An error occurred: {e}")
    take_screenshot()  # Capture a screenshot on error

finally:
    driver.quit()  # Close the browser after execution
