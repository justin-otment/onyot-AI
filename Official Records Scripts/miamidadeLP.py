from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, WebDriverException
import pytesseract
from io import BytesIO
from PIL import Image
import re
import csv
import os
import logging
import time

# Set up Tesseract path for OCR
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Chrome driver
def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--log-level=3")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    return driver

# Login function
def login(driver):
    try:
        driver.get("https://www2.miamidadeclerk.gov/Usermanagementservices")
        wait = WebDriverWait(driver, 60)
        username_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#userName.form-control")))
        username_input.send_keys("justinlbrj23")

        password_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#password.form-control")))
        password_input.send_keys("w!axY^3eI8zgxX")

        login_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input.btn.coc-button--primary.col-md-3.m-2")))
        login_button.click()
        logging.info("Login attempt completed.")
    except Exception as e:
        logging.error(f"Login error: {e}")

# Search function
def search(driver):
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
        logging.info("Form submitted successfully.")
    except Exception as e:
        logging.error(f"Search error: {e}")

# Function to extract case details from OCR text
def extract_case_details(ocr_text):
    case_details = {
        'Case Number': None,
        'Plaintiffs': None,
        'Defendants': None,
        'Filing Date': None
    }

    logging.info(f"Extracting case details from OCR text: {ocr_text[:100]}...")  # Log first 100 chars

    # Extract the case number (e.g., Case # or Case No.)
    case_number_match = re.search(r'Case\s?No\.\s?([A-Za-z0-9-]+)', ocr_text)
    if case_number_match:
        case_details['Case Number'] = case_number_match.group(1)

    # Extract plaintiffs (e.g., after "Plaintiff." or similar text)
    plaintiffs_match = re.search(r'Plaintiff[s]*\s*[:\.\s]*([^\n]+)', ocr_text)
    if plaintiffs_match:
        case_details['Plaintiffs'] = plaintiffs_match.group(1).strip()

    # Extract defendants (e.g., after "Defendant." or similar text)
    defendants_match = re.search(r'Defendant[s]*\s*[:\.\s]*([^\n]+)', ocr_text)
    if defendants_match:
        case_details['Defendants'] = defendants_match.group(1).strip()

    # Extract filing date (e.g., after "DATE:" or similar text)
    filing_date_match = re.search(r'DATE[:\s]+([\d/]+)', ocr_text)
    if filing_date_match:
        case_details['Filing Date'] = filing_date_match.group(1).strip()

    return case_details

# Function to save extracted case details to CSV
def save_to_csv(data_list, filename=r'C:\Users\DELL\Documents\Onyot.ai\Lead_List-Generator\python tests\Official Records Scripts\case_details.csv'):
    # Filter out any empty data entries
    valid_data = [data for data in data_list if any(data.values())]

    if not valid_data:
        logging.warning("No valid data extracted. Skipping CSV writing.")
        return

    # Check if the file exists, and decide whether to write header
    write_header = not os.path.exists(filename)

    try:
        with open(filename, mode='a', newline='', encoding='utf-8') as file:
            fieldnames = ['Case Number', 'Plaintiffs', 'Defendants', 'Filing Date']  # Ensure all relevant fields are listed
            writer = csv.DictWriter(file, fieldnames=fieldnames)

            # Write the header if the file is new
            if write_header:
                writer.writeheader()

            # Write the extracted case details
            writer.writerows(valid_data)
            logging.info(f"Data successfully written to {filename}.")
    except IOError as e:
        logging.error(f"Error writing to file {filename}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error while saving to CSV: {e}")

# Scroll and capture OCR from iframe content
def scroll_and_capture(driver, iframe_element, max_scroll_attempts=10):
    extracted_data = []
    driver.switch_to.frame(iframe_element)

    scroll_attempts = 0
    previous_scroll_position = -1

    pdf_viewer_container = driver.find_element(By.TAG_NAME, 'html')

    while scroll_attempts < max_scroll_attempts:
        screenshot = driver.get_screenshot_as_png()
        image = Image.open(BytesIO(screenshot))

        ocr_text = pytesseract.image_to_string(image)
        logging.info(f"OCR Text (Scroll {scroll_attempts + 1}):\n{ocr_text}\n")

        case_details = extract_case_details(ocr_text)
        extracted_data.append(case_details)

        driver.execute_script("arguments[0].scrollBy(0, 500);", pdf_viewer_container)
        time.sleep(3)

        current_scroll_position = driver.execute_script("return arguments[0].scrollTop;", pdf_viewer_container)
        max_scroll_height = driver.execute_script("return arguments[0].scrollHeight;", pdf_viewer_container)

        if current_scroll_position == previous_scroll_position or current_scroll_position + 500 >= max_scroll_height:
            logging.info("Reached the bottom of the document or no further scrolling possible.")
            break

        previous_scroll_position = current_scroll_position
        scroll_attempts += 1

    driver.switch_to.default_content()
    save_to_csv(extracted_data)
    return extracted_data

# Extract and click elements
def extract_and_click_unique_elements(driver):
    wait = WebDriverWait(driver, 60)
    case_details_list = []

    try:
        td_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'td')))
        td_texts = [td.text.strip() for td in td_elements if td.text.strip()]
        unique_values = {text: td_texts.count(text) for text in set(td_texts)}

        logging.info("Unique Values and Counts:")
        for value, count in unique_values.items():
            logging.info(f"{value}: {count}")

        original_window = driver.current_window_handle

        for value in unique_values.keys():
            clicked = False
            while not clicked:
                try:
                    td_elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'td')))
                    target_element = next((td for td in td_elements if td.text.strip() == value), None)

                    if target_element:
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_element)
                        target_element.click()
                        logging.info(f"Clicked element with text: {value}")

                        WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) > 1)
                        new_window = [w for w in driver.window_handles if w != original_window][0]
                        driver.switch_to.window(new_window)
                        logging.info(f"Switched to new window for {value}")

                        btn_image = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#btnImage")))
                        btn_image.click()
                        logging.info(f"Clicked #btnImage for {value}")

                        try:
                            wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "pdfFrame")))
                            driver.execute_script("document.documentElement.requestFullscreen();")
                            logging.info("Full-screen mode activated via JavaScript.")
                            time.sleep(2)

                            time.sleep(5)
                            screenshot = driver.get_screenshot_as_png()
                            image = Image.open(BytesIO(screenshot))

                            ocr_text = pytesseract.image_to_string(image)
                            logging.info(f"OCR Result for {value}:\n{ocr_text}")

                            case_details = extract_case_details(ocr_text)
                            case_details_list.append(case_details)

                        except Exception as iframe_err:
                            logging.error(f"Error switching to iframe #pdfFrame for {value}: {iframe_err}")

                        driver.switch_to.default_content()

                        driver.close()
                        driver.switch_to.window(original_window)
                        logging.info(f"Closed new window and returned to original window for {value}")
                except (TimeoutException, StaleElementReferenceException):
                    logging.warning(f"Retrying click for element with text: {value}")
                except Exception as e:
                    logging.error(f"Error clicking element with text '{value}': {e}")
                    clicked = True

    except TimeoutException:
        logging.error("No 'td' elements found on the page")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

    return case_details_list

def main():
    driver = setup_driver()
    try:
        login(driver)
        search(driver)
        
        # Extract details and check if data was collected
        case_details_list = extract_and_click_unique_elements(driver)
        if case_details_list:
            logging.info(f"Extracted {len(case_details_list)} case details.")
            save_to_csv(case_details_list)
        else:
            logging.warning("No case details to save.")
    except Exception as e:
        logging.error(f"Main execution error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
