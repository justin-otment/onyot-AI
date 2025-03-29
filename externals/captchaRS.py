import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, StaleElementReferenceException
import pytesseract
import time
from io import BytesIO
from PIL import Image
from selenium.webdriver.common.action_chains import ActionChains

# Configure Tesseract OCR
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Constants for Chrome profile
USER_DATA_DIR = "C:\\Users\\DELL\\AppData\\Local\\Google\\Chrome\\User Data"
PROFILE_DIRECTORY = "Profile 1"

# Setup Undetected Chrome Driver
def setup_driver():
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument(f"--profile-directory={PROFILE_DIRECTORY}")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--log-level=3")  # Suppress unnecessary logs

    driver = uc.Chrome(options=options, use_subprocess=True)
    return driver

def scroll_to_bottom(driver):
    """Scroll to the bottom of the chat to load new messages."""
    try:
        last_height = driver.execute_script("return document.body.scrollHeight")
        
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Allow messages to load
            
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:  # Stop if no more content is loaded
                break
            last_height = new_height
            
        print("✅ Successfully scrolled to the bottom.")

    except WebDriverException as e:
        print(f"❌ Error while scrolling: {e}")

def safe_click(driver, css_selector):
    """Scroll to bottom first, then click an element safely while handling stale elements."""
    scroll_to_bottom(driver)  # Ensure all messages are loaded **before** clicking

    for attempt in range(3):  # Retry up to 3 times
        try:
            # Refetch the element after scrolling
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
            )
            
            # Scroll the element into view (extra safety)
            driver.execute_script("arguments[0].scrollIntoView({block: 'center', inline: 'nearest'});", element)
            time.sleep(1)  # Allow UI to settle
            
            # Click using ActionChains to prevent interception
            actions = ActionChains(driver)
            actions.move_to_element(element).click().perform()
            time.sleep(1)  # Allow page to process action
            print(f"✅ Clicked successfully: {css_selector}")
            return  # Exit on success

        except StaleElementReferenceException:
            print(f"🔄 Retrying due to stale element: {css_selector} (Attempt {attempt + 1})")
            time.sleep(2)  # Wait before retrying

        except TimeoutException:
            print(f"❌ Timeout: Element {css_selector} not found.")
            return

        except WebDriverException as e:
            print(f"❌ WebDriverException while clicking {css_selector}: {e}")
            return
        
# Retry function for handling transient errors
def retry_function(func, retries=3, delay=5):
    for attempt in range(retries):
        try:
            return func()
        except WebDriverException as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(delay)
    print("All retry attempts failed.")
    raise Exception("Failed after several retries")

# Main Telegram inbox automation function
def telegram_inbox(driver):
    try:
        retry_function(lambda: driver.get("https://web.telegram.org/a/#503474174"))
        wait = WebDriverWait(driver, 60)

        # Scroll to bottom before starting interactions
        scroll_to_bottom(driver)

        # Click on the button to start interaction
        safe_click(driver, "#MiddleColumn > div.messages-layout > div.Transition > div > div.middle-column-footer > div.Composer.shown.mounted > div.composer-wrapper > div > button:nth-child(3) > i")

        # Click the "Start" button inside the menu
        safe_click(driver, "#MiddleColumn > div.messages-layout > div.Transition > div > div.middle-column-footer > div.Composer.shown.mounted > div.composer-wrapper > div > div.Menu.BotKeyboardMenu > div > div > div:nth-child(1) > button:nth-child(3) > div")

        # Click the message list background to close overlays
        safe_click(driver, "#MiddleColumn > div.messages-layout > div.Transition > div > div.MessageList.custom-scroll.no-avatars.with-default-bg.scrolled > div > div.message-date-group.first-message-date-group")

        # Click on captcha image
        safe_click(driver, ".media-inner canvas.thumbnail")

        time.sleep(2)  # Allow UI to update

        # Capture only the CAPTCHA element screenshot
        captcha_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#MediaViewer > div.MediaViewerSlides > div.MediaViewerSlide.MediaViewerSlide--active > div > div > img")))
        screenshot = captcha_element.screenshot_as_png
        image = Image.open(BytesIO(screenshot))

        # Perform OCR
        text = pytesseract.image_to_string(image).strip()
        print(f"OCR Result: {text}")

        # Click the background again to exit captcha view
        safe_click(driver, "#MiddleColumn > div.messages-layout > div.Transition > div > div.MessageList.custom-scroll.no-avatars.with-default-bg.scrolled > div > div.message-date-group.first-message-date-group")

        # Enter text in input field
        message_input = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#editable-message-text")))
        message_input.send_keys(text)

        # Click send button
        safe_click(driver, "#MiddleColumn > div.messages-layout > div.Transition > div > div.middle-column-footer > div.Composer.shown.mounted > button")

        print("Message sent successfully!")

    except Exception as e:
        print(f"Error in telegram_inbox: {e}")

# Main execution
def main():
    driver = setup_driver()
    try:
        telegram_inbox(driver)
    except Exception as e:
        print(f"Main execution error: {e}")
    finally:
        time.sleep(5)
        driver.quit()

if __name__ == "__main__":
    main()
