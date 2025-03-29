from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
import pytesseract
import time
from io import BytesIO
from PIL import Image




pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Set up Chrome options
chrome_options = Options()
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-software-rasterizer")
chrome_options.add_argument("--log-level=3")  # Suppress unnecessary logs

# Initialize WebDriver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
driver.get("https://www2.miamidadeclerk.gov/Usermanagementservices")


def login():
    try:
        wait = WebDriverWait(driver, 60)
        username_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#userName.form-control")))
        username_input.send_keys("justinlbrj23")

        password_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#password.form-control")))
        password_input.send_keys("w!axY^3eI8zgxX")

        login_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input.btn.coc-button--primary.col-md-3.m-2")))
        login_button.click()
        print("Login attempt completed.")

    except Exception as e:
        print(f"Login error: {e}")


def search():
    try:
        driver.get("https://onlineservices.miamidadeclerk.gov/officialrecords/StandardSearch.aspx")
        wait = WebDriverWait(driver, 60)

        start_date = wait.until(EC.element_to_be_clickable((By.ID, "prec_date_from")))
        start_date.send_keys("01/01/2025")

        end_date = wait.until(EC.element_to_be_clickable((By.ID, "prec_date_to")))
        end_date.send_keys("02/14/2025")

        doct_type = wait.until(EC.element_to_be_clickable((By.ID, "pdoc_type")))
        doct_type.click()

        option_LP = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#pdoc_type > option:nth-child(45)")))
        option_LP.click()

        submit_button = wait.until(EC.element_to_be_clickable((By.ID, "btnNameSearch")))
        submit_button.click()
        print("Form submitted successfully.")

    except Exception as e:
        print(f"Search error: {e}")
        
def extract_and_click_unique_elements(driver):
    wait = WebDriverWait(driver, 60)
    try:
        td_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'td')))
        td_texts = [td.text.strip() for td in td_elements if td.text.strip()]
        unique_values = {text: td_texts.count(text) for text in set(td_texts)}

        print("Unique Values and Counts:")
        for value, count in unique_values.items():
            print(f"{value}: {count}")

        original_window = driver.current_window_handle

        for value in unique_values.keys():
            clicked = False
            while not clicked:
                try:
                    td_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'td')))
                    target_element = next((td for td in td_elements if td.text.strip() == value), None)

                    if target_element:
                        driver.execute_script("arguments[0].scrollIntoView(true);", target_element)
                        target_element.click()
                        print(f"Clicked element with text: {value}")
                        clicked = True

                        # Wait for new window to open
                        WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > 1)

                        # Switch to the new window
                        new_window = [w for w in driver.window_handles if w != original_window][0]
                        driver.switch_to.window(new_window)

                        print(f"Switched to new window for {value}")

                        # Step 1: Click #btnImage
                        try:
                            btn_image = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#btnImage")))
                            btn_image.click()
                            print(f"Clicked #btnImage for {value}")

                            # Step 2: Switch to iframe and request full-screen mode
                            try:
                                wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "pdfFrame")))
                                print("Switched to iframe #pdfFrame")

                                # Request full-screen mode
                                driver.execute_script("document.documentElement.requestFullscreen();")
                                print("Full-screen mode activated via JavaScript.")

                                time.sleep(2)  # Wait for full-screen mode to take effect
                                
                                # Give time for the document to load and perform OCR
                                time.sleep(5)
                                screenshot = driver.get_screenshot_as_png()
                                image = Image.open(BytesIO(screenshot))

                                # Perform OCR
                                text = pytesseract.image_to_string(image)
                                print(f"OCR Result for {value}:\n{text}")

                            except Exception as iframe_err:
                                print(f"Error switching to iframe #pdfFrame for {value}: {iframe_err}")

                            # Switch back to default content (after iframe)
                            driver.switch_to.default_content()

                        except Exception as e:
                            print(f"Error during #btnImage click or OCR for '{value}': {e}")

                        # Close the new window and switch back to the original window
                        driver.close()
                        driver.switch_to.window(original_window)

                        print(f"Closed new window and returned to original window for {value}")

                except (TimeoutException, StaleElementReferenceException):
                    print(f"Retrying click for element with text: {value}")
                except Exception as e:
                    print(f"Error clicking element with text '{value}': {e}")
                    clicked = True

    except TimeoutException:
        print("No 'td' elements found on the page")
    except Exception as e:
        print(f"Unexpected error: {e}")


def main():
    try:
        login()
        search()
        extract_and_click_unique_elements(driver)
    except Exception as e:
        print(f"Main execution error: {e}")
    finally:
        time.sleep(5)
        # driver.quit()


if __name__ == "__main__":
    main()
