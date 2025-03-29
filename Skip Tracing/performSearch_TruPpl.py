import random
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from thefuzz import fuzz
from utilities import human_like_mouse_movement, safe_find_element
import asyncio
from errorHandler import error_handler  # Import the error_handler function
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import ElementNotInteractableException
from selenium.common.exceptions import TimeoutException

# Function to wait for the page to fully load
def wait_for_page_load(driver, timeout=60):
    try:
        # Wait until the document's readyState is 'complete'
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        # Ensure the <body> tag is present in the DOM
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        print("Page fully loaded.")
    except TimeoutException:
        print("Timeout waiting for page to load.")
    except Exception as e:
        print(f"Error waiting for page to load: {e}")
        

def random_delay(min_delay, max_delay, step=500):
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay / 1000)

def safe_find_element(driver, by, value, timeout=10):
    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))
    except Exception as e:
        print(f"Error finding element {value}: {e}")
        return None

def clear_and_enter_text_with_delay(driver, by, value, text, delay=1):
    # Optional: Add a check to ensure 'text' and 'delay' are valid
    if not isinstance(text, str):
        raise ValueError(f"Expected text to be a string, got {type(text)}")
    if not isinstance(delay, (int, float)):
        raise ValueError(f"Expected delay to be a number, got {type(delay)}")
    
    # Clear and enter text logic
    element = driver.find_element(by, value)
    element.clear()
    element.send_keys(text)
    time.sleep(delay)

def human_like_mouse_movement(driver, element):
    actions = ActionChains(driver)
    actions.move_to_element(element).perform()
    
# Main function to extract address query
def extract_address_query(driver, timeout=10):
    address_query_element = safe_find_element(driver, By.XPATH, '//*[@id="site-content"]/div/div[1]/h1/strong', timeout)
    
    # Simulate human-like mouse movement if the element is found
    if address_query_element:
        human_like_mouse_movement(driver, address_query_element)
        address_query = address_query_element.text
        return address_query.strip() if address_query else ''
    else:
        print('Address query element not found.')
        return ''

async def perform_search(driver, street, zipcode, fallback_street_data=None, fallback_zip_data=None, max_retries=3):
    attempt = 0
    fallback_street_data = fallback_street_data or []
    fallback_zip_data = fallback_zip_data or []

    while attempt < max_retries:
        try:
            attempt += 1
            print(f"Attempt {attempt} to perform search...")

            # Step 1: Handle the search faker element
            try:
                search_faker_element = driver.find_element(By.CSS_SELECTOR, '#searchTypeAddress-d > span')
                human_like_mouse_movement(driver, search_faker_element)
                random_delay(1000, 10000, 500)
                search_faker_element.click()
            except NoSuchElementException as e:
                print(f"Element //*[@id=\"search-faker\"]/div not found. Using fallback URL. Error: {e}")
                driver.get('https://truepeoplesearch.com/')
                wait_for_page_load(driver)

            random_delay(1000, 10000, 500)

            # Step 2: Click address link
            address_link = safe_find_element(driver, By.CSS_SELECTOR, '#searchTypeAddress-d > span')
            if address_link:
                address_link.click()

            random_delay(1000, 30000, 300)

            # Step 3: Handle GDPR footer
            try:
                gdpr_footer = driver.find_element(By.ID, 'gdpr-cookie-footer')
                driver.execute_script("arguments[0].style.display = 'none';", gdpr_footer)
            except:
                print('GDPR footer not present.')

            # Step 4: Enter street and zipcode
            search_address_element = safe_find_element(driver, By.CSS_SELECTOR, '#id-d-addr')
            if not search_address_element:
                print('Element #id-d-addr not found. ')
                return ''

            clear_and_enter_text_with_delay(driver, By.CSS_SELECTOR, '#id-d-addr', street)
            random_delay(1500, 10000, 150)
            clear_and_enter_text_with_delay(driver, By.CSS_SELECTOR, '#id-d-loc-addr', zipcode)
            random_delay(1000, 10000, 100)

            zip_field = safe_find_element(driver, By.CSS_SELECTOR, '#id-d-loc-addr')
            if zip_field:
                zip_field.send_keys(Keys.RETURN)

            print(f"Search initiated for: Street='{street}' and Zip='{zipcode}'")
            
            # Break the retry loop if successful
            return

        except NoSuchElementException as e:
            print(f"Error during attempt {attempt} in perform_search: {e}")
            if attempt < max_retries:
                delay = attempt * 2  # Exponential backoff
                print(f"Retrying after {delay} seconds...")
                await asyncio.sleep(delay)
            else:
                print("Max retries reached. Attempting fallback data...")

                # Fallback handling
                for fallback_street, fallback_zip in zip(fallback_street_data, fallback_zip_data):
                    print(f"Retrying with fallback street='{fallback_street}' and zip='{fallback_zip}'...")
                    result = await perform_search(driver, fallback_street, fallback_zip, max_retries=1)
                    if result:
                        return result  # Exit if a fallback attempt succeeds

                print("All fallback attempts failed. Aborting search.")
                return ''

    random_delay(3000, 10000, 500)

async def increment_value_randomly(min_value, max_value, step):
    value = random.randint(min_value, max_value)
    incremented_value = value + step
    await asyncio.sleep(1)  # Simulate async operation
    return incremented_value

def update_google_sheet(sheet, row, extracted_id):
    """Update the Google Sheet with the extracted ID."""
    sheet.update(f"X{row}", extracted_id)
    print(f"✅ Row {row} updated successfully with ID: {extracted_id}")

async def find_best_match(
    driver, 
    target_names, 
    fallback_target_name, 
    street_address="", 
    zipcode="", 
    fallback_target_names=None, 
    max_retries=3
):
    fallback_target_names = fallback_target_names or []
    timeout = random.randint(1000, 30000) / 1000

    def generate_name_permutations(name):
        """Generate possible name permutations."""
        parts = name.lower().split()
        if len(parts) == 2:
            return [" ".join(parts), " ".join(reversed(parts))]
        return [" ".join(parts)]

    async def attempt_match(names):
        """Attempt to find the best match among the given names."""
        best_match_element = None
        highest_score = 0
        
        try:
            elements = WebDriverWait(driver, 30).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, '#site-content a'))
            )
            print(f"Elements found: {len(elements)}")
        except TimeoutException:
                print("Timed out waiting for elements to be located")

        # If elements are not found, check the header text
        if not elements:
            header_text = driver.find_element(By.CSS_SELECTOR, 'h1').text.strip()
            print(f"Header text: {header_text}")
            if "loading search results" in header_text.lower():
                await error_handler(driver)
                return None, 0

        for element in elements:
            element_text = element.text.strip().lower()
            if not element_text:
                continue

            for target_name in names:
                if not target_name:
                    continue

                normalized_target_name = target_name.lower()
                permutations = generate_name_permutations(normalized_target_name)
                similarities = [fuzz.ratio(element_text, perm) / 100 for perm in permutations]

                highest_local_score = max(similarities)

                if highest_local_score > highest_score:
                    highest_score = highest_local_score
                    best_match_element = element

        return best_match_element, highest_score

    for attempt in range(max_retries):
        try:
            # Attempt match with primary target names
            best_match_element, highest_score = await attempt_match(target_names)

            if not best_match_element or highest_score < 0.35:
                print("Trying fallback target name.")
                # Attempt match with the fallback target name
                best_match_element, highest_score = await attempt_match([fallback_target_name])

            if not best_match_element or highest_score < 0.35:
                print("Trying fallback target names list.")
                # Attempt match with fallback target names list
                best_match_element, highest_score = await attempt_match(fallback_target_names)

            # If a sufficiently good match is found
            if best_match_element and highest_score > 0.5:
                print(f"Best match found with a score of {highest_score}. Clicking the element.")
                await increment_value_randomly(1000, 10000, 500)  # Await the coroutine

                # Scroll the element into view
                driver.execute_script("arguments[0].scrollIntoView(true);", best_match_element)
                time.sleep(1)  # Give time for scrolling

                # Retry clicking the element
                for _ in range(3):
                    try:
                        human_like_mouse_movement(driver, best_match_element)
                        best_match_element.click()
                        wait_for_page_load(driver)
                        await increment_value_randomly(1000, 10000, 500)  # Await the coroutine
                        WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, '//*[@id="full_name_section"]/h2/span')))
                        return True
                    except NoSuchElementException as e:
                        print(f"Retry clicking the element: {e}")
                        time.sleep(2)  # Wait before retrying

            # If street address and zipcode are provided, attempt a match in the address elements
            if street_address and zipcode:
                print("Checking for matches with street address and zipcode.")
                street_elements = driver.find_elements(By.CSS_SELECTOR, 'div.col-12.col-sm-11.pl-sm-1 > div.row.pl-sm-2 > div > div > a > span:nth-child(1)')
                for element in street_elements:
                    address_text = element.text
                    if street_address in address_text and zipcode in address_text:
                        print(f"Match found with address: {address_text}. Getting href attribute.")
                        human_like_mouse_movement(driver, element)
                        parent_anchor = element.find_element(By.XPATH, '..')
                        href = parent_anchor.get_attribute('href')
                        print(f"Href attribute: {href}")
                        extracted_id = extract_id_from_href(href)
                        print(f"Extracted ID: {extracted_id}")
                        await increment_value_randomly(900, 60000, 1300)  # Await the coroutine
                        return extracted_id

            def extract_id_from_href(href):
                """Extracts the ID portion from the given href."""
                return href.split('/')[-1]


            print("No matsch found after all fallback attempts.")
            return False
        
        except NoSuchElementException as e:
            print(f"Error finding best match on attempt {attempt + 1}: {e}")

        except ElementNotInteractableException as e:
            print(f"Error finding best match on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                print("Retrying...")
                await asyncio.sleep(2)  # Wait before retrying
            else:
                print("Max retries reached. Aborting.")
                return False
