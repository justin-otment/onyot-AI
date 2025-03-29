from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from nordvpn import restart_nordvpn  # Import the restart_nordvpn function
import time
from utilities import random_delay
from captcha import captcha
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys


async def error_handler(driver):
    """ 
    Checks if the page displays a rate limit error, restarts NordVPN if necessary,
    and refreshes the page afterward.
    """
    try:
        # Wait for the h1 element to appear and get its text
        h1_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
        )
        h1_text = h1_element.text.strip()
        print(f"Found h1 text: {h1_text}")

        if h1_text == "Rate Limit Exceeded":
            time.sleep(60)
            print("Page refreshed successfully.")

            return True  # Indicate that rate limit handling was performed
    except Exception as e:
        print(f"Error while checking rate limit, restarting NordVPN, or refreshing: {e}")
    
    return False

async def error_handler(driver):
    """ 
    Checks if the page displays a rate limit error, restarts NordVPN if necessary,
    and refreshes the page afterward.
    """
    try:
        # Wait for the h1 element to appear and get its text
        h1_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "h1"))
        )
        h1_text = h1_element.text.strip()
        print(f"Found h1 text: {h1_text}")

        if h1_text == "Loading Search Results":
            time.sleep(60)
            driver.refresh()
            print("Page refreshed successfully.")
            time.sleep(3)

            return True  # Indicate that rate limit handling was performed
    except Exception as e:
        print(f"Error while checking rate limit, restarting NordVPN, or refreshing: {e}")
    
    return False


async def error_handler(driver):
    try:
        # Step 1: Fetch the current URL
        current_url = driver.current_url
        print(f"Fetched URL: {current_url}")
        
        # Step 2: Open a new tab using Ctrl+T
        try:
            # Perform the Ctrl+T key combination
            ActionChains(driver).key_down(Keys.CONTROL).send_keys('t').key_up(Keys.CONTROL).perform()
            driver.switch_to.window(driver.window_handles[-1])  # Switch to the new tab
            driver.get(current_url)  # Navigate to the fetched URL
            print("New tab opened and URL loaded.")
        except Exception as e:
            print(f"Failed to open a new tab: {e}")
            return

        # Locate the iframe
        iframe_xpath = "//*[@id='content']"
        try:
            iframe = WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.XPATH, iframe_xpath))
            )
            print("Iframe located.")
        except TimeoutException:
            print("Iframe not found. Exiting handler.")
            return

        # Scroll to iframe and switch context
        ActionChains(driver).move_to_element(iframe).perform()
        driver.switch_to.frame(iframe)

        # Locate the target element within the iframe
        element_xpath = "//*[@id='cyhGN8']/div/label/input"
        try:
            element = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, element_xpath))
            )
            element.click()
            print("Element clicked.")
        except TimeoutException:
            print("Clickable element not found inside iframe.")

        # Close the tab and switch back to the original tab
        if len(driver.window_handles) > 1:
            driver.close()  # Close the current tab
            driver.switch_to.window(driver.window_handles[0])  # Switch back to the first tab
        driver.refresh()  # Refresh the original tab
        print("Original tab refreshed.")

    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage
if __name__ == "__main__":
    from selenium import webdriver
    driver = webdriver.Chrome()  # Replace with your WebDriver instance
    try:
        # Pass the driver instance to the error handler
        error_handler(driver)
    finally:
        driver.quit()
