from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException, TimeoutException
from undetected_chromedriver import Chrome, ChromeOptions

def extract_text_from_elements(driver, url):
    """
    Extract text from a specific element inside an iframe on the webpage after waiting for it to be present.

    Args:
        driver: The Selenium WebDriver instance.
        url: The URL to navigate to.

    Returns:
        None
    """
    try:
        # Navigate to the URL
        driver.get(url)

        # Wait for the iframe to be present and switch to it
        wait = WebDriverWait(driver, 60)
        iframe = wait.until(EC.presence_of_element_located((By.TAG_NAME, 'iframe')))
        driver.switch_to.frame(iframe)

        # Wait for the element to be present inside the iframe
        element = wait.until(EC.presence_of_element_located((By.CLASS_NAME, 'col-12')))

        # Extract text from the specified element
        text_content = element.text
        print("Extracted Text:", text_content)

    except TimeoutException:
        print("Element not found within the given time.")
    except NoSuchElementException:
        print("Element not found.")
    except ElementNotInteractableException:
        print("Element not interactable.")
    finally:
        driver.quit()

if __name__ == "__main__":
    # Initialize the Chrome driver with options
    options = ChromeOptions()
    driver = Chrome(options=options)

    # URL to navigate to
    url = "https://county-taxes.net/fl-lee/property-tax/bGVlOnJlYWxfZXN0YXRlOnBhcmVudHM6ZTE4MjZlODAtOTU0Mi0xMWVjLTgxYmEtZDIxZTQ0Njc0YjU4"

    # Perform text extraction
    extract_text_from_elements(driver, url)
