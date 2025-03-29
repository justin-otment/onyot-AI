import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Constants for CSS selectors
RESULTS_CONTAINER = "#SRMsU6YuSJ6u\\+w2rKH71ew\\=\\= > div > ul"
TARGET_NAME = "#SRMsU6YuSJ6u\\+w2rKH71ew\\=\\= > div > ul > li:nth-child(1) > div > div > div > div.chXVZRXgneBMTAIABThAmJbGvGgFCRKUXBLS.GcnfgjNjmjTmhCjuedvjeqlKFxSYfQNENKHo.pt3.pb3.t-12.t-black--light > div.mb1 > div.t-roman.t-sans > div > span.tZTJYwWRWJZLHlVLGHWbBvtzGJccdraut.HYhMfXmQJrGYjZetktQgGxbmViMILOQOFw > span > a"
MESSAGE_BUTTON = "#ember420 > span"
MESSAGE_INPUT = "#msg-form-ember496 > div.msg-form__msg-content-container.msg-form__message-texteditor.relative.flex-grow-1.display-flex > div.msg-form__msg-content-container--scrollable.scrollable.relative > div > div.msg-form__contenteditable.t-14.t-black--light.t-normal.flex-grow-1.full-height.notranslate > p"
CLOSE_CHAT = "#ember530 > svg > use"
NEXT_PAGE = "#ember469 > span"

# Constants for Chrome user data directory and profile
USER_DATA_DIR = "C:\\Users\\DELL\\AppData\\Local\\Google\\Chrome\\User Data"
PROFILE_DIRECTORY = "Profile 1"

def setup_chrome_driver():
    """Set up Chrome driver with custom options."""
    options = webdriver.ChromeOptions()
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument(f"--remote-debugging-port=62303")
    options.add_argument(f"--profile-directory={PROFILE_DIRECTORY}")
    options.add_argument(f"--start-maximized")
    return webdriver.Chrome(options=options)

# Initialize WebDriver
driver = setup_chrome_driver()

def wait_for_element(css_selector, timeout=20):
    """Wait for an element to be visible on the page."""
    return WebDriverWait(driver, timeout).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, css_selector))
    )

def process_target():
    """Perform the messaging workflow for each target."""
    try:
        # Extract the target name
        target_element = wait_for_element(TARGET_NAME)
        target_name = target_element.text
        first_name, last_name = target_name.split(' ', 1)

        # Click the message button
        message_button = wait_for_element(MESSAGE_BUTTON)
        message_button.click()

        # Find and type the message
        message_input = wait_for_element(MESSAGE_INPUT)
        message = (f"Hi {first_name},\n"
                   "I'm a Virtual Real Estate Professional based in the Philippines, with over 8 years of experience in the US Real Estate Market. "
                   "I hope I am and this message is finding you at such a good timing. Are you by any chance looking or perhaps thinking of outsourcing some of your tasks, "
                   "if not maybe delegate some of your business operation's deliverables at a much cost efficient rate? Please let me know. "
                   "I'd love to have the opportunity of bringing some real value to your table and to your real estate business. Thank you.")
        message_input.send_keys(message)

        # Close the chat
        close_chat_button = wait_for_element(CLOSE_CHAT)
        close_chat_button.click()

        print(f"Message sent to {target_name}.")
    except Exception as e:
        print(f"Error processing target: {e}")

def navigate_pages():
    """Navigate through LinkedIn search result pages."""
    while True:
        try:
            # Wait for results container to load
            wait_for_element(RESULTS_CONTAINER)

            # Process each target in the results container
            process_target()

            # Click the next page button
            next_page_button = wait_for_element(NEXT_PAGE)
            next_page_button.click()
            time.sleep(2)  # Pause to let the next page load

        except NoSuchElementException:
            print("No more pages to navigate.")
            break
        except TimeoutException:
            print("Timed out waiting for elements.")
            break

# Main script execution
try:
    driver.get("https://www.linkedin.com/search/results/people/?geoUrn=%5B%22103644278%22%5D&keywords=real%20estate&network=%5B%22F%22%5D&origin=GLOBAL_SEARCH_HEADER&sid=Q8D")
    navigate_pages()

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    driver.quit()  # Close the browser after execution
