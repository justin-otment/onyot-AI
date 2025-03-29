import asyncio
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fuzzywuzzy import fuzz as string_similarity
from utilities import get_random_timeout, human_like_mouse_movement, safe_find_element, random_delay
import re
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from errorHandler import error_handler
from datetime import datetime
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Utility function to remove HTML tags from a string
def remove_html_tags(text):
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

# Async function to extract the Current Mailing Address
async def extract_address_query(driver, timeout=60):
    """
    Extracts the Current Mailing Address from the web page and formats it as a one-liner.

    :param driver: Selenium WebDriver instance.
    :param timeout: Maximum time to wait for the element (in seconds).
    :return: Extracted and formatted address query as a string.
    """
    address_query = ""

    try:
        # Locate the address query element
        current_address = WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '#personDetails > div:nth-child(5) > div.col-12.col-sm-11.pl-sm-1 > div.row.pl-sm-2 > div'))
        )
        driver.execute_script("arguments[0].scrollIntoView();", current_address)
        
        address_query_element = await safe_find_element(driver, By.CSS_SELECTOR, '.dt-hd', timeout)
        
        # Simulate human-like mouse movement if the element is found
        if address_query_element:
            await human_like_mouse_movement(driver, address_query_element)
            raw_address = address_query_element.text.strip()
            # Format the address into a single line
            address_query = " ".join(raw_address.splitlines())
        else:
            print("Address query element not found.")
    except Exception as error:
        print(f"Error extracting address query: {str(error)}")
    
    return address_query


# Async function to extract and format phone data
async def extract_phone_data(driver, target_name):
    """
    Extracts phone numbers and their corresponding types from the phone section of the web page.
    Formats the data into a readable string.

    :param driver: Selenium WebDriver instance.
    :param targetName: The target name to be used in the relative_link function if no phone data is found.
    :return: A dictionary with phone numbers, phone types, and a formatted phone data string.
    """
    try:
        # Generate a random timeout
        timeout = await get_random_timeout(15000, 30000, 1000, 5000)

        # Locate the phone number section on the page
        phone_section = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.col-12 col-sm-11.pl-sm-1'))
        )
        driver.execute_script("arguments[0].scrollIntoView();", phone_section)



        # Extract phone types and phone numbers as separate lists
        phone_type_elements = phone_section.find_elements(By.CSS_SELECTOR, 'span.smaller')
        phone_number_elements = phone_section.find_elements(By.CSS_SELECTOR, 'span')

        # Initialize separate lists for phone types and numbers
        phone_types = [element.text.strip() or '' for element in phone_type_elements]
        phone_numbers = [element.text.strip() or '' for element in phone_number_elements]

        # Ensure both lists are the same length by padding with empty strings
        max_length = max(len(phone_types), len(phone_numbers))
        phone_types += [''] * (max_length - len(phone_types))
        phone_numbers += [''] * (max_length - len(phone_numbers))

        # Format the phone data into a readable string
        phone_data = ", ".join(
            [f"{num} ({ptype})" for num, ptype in zip(phone_numbers, phone_types) if num]
        )

        # Check if no phone data was extracted
        if not phone_numbers:
            # Try searching for a relative link if no phone data is found
            if not await relativeLink(driver, target_name):
                # If no relative link is found, call error handler
                await error_handler(driver)

        return {
            'phone_numbers': phone_numbers,
            'phone_types': phone_types,
            'formatted_phone_data': phone_data
        }

    except Exception as error:
        print(f"Error extracting phone data: {error}")
        # Call error handler in case of failure
        await error_handler(driver)
        return {
            'phone_numbers': [],
            'phone_types': [],
            'formatted_phone_data': ''
        }

# Function to handle errors
async def error_handler(driver):
    """
    Handles errors during phone data extraction by logging and performing necessary recovery actions.
    :param driver: Selenium WebDriver instance.
    """
    print("Handling error in phone data extraction.")
    # Implement error handling logic (e.g., retry, logging, screenshot, etc.)
    # Optionally, you can add a screenshot here as well
    await take_screenshot(driver)

# Screenshot function (optional)
async def take_screenshot(driver):
    """
    Takes a screenshot in case of an error.
    :param driver: Selenium WebDriver instance.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    screenshot_path = f"screenshots/screenshot_{timestamp}.png"
    driver.save_screenshot(screenshot_path)
    print(f"Screenshot taken: {screenshot_path}")


# Async function to extract full name data
async def extractFullName(driver):
    firstName = ''
    lastName = ''
    
    try:
        fullNameElement = WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.oh1'))
        )
        driver.execute_script("arguments[0].scrollIntoView();", fullNameElement[0])
        
        if not fullNameElement:
            await error_handler(driver)  # Await the error_handler coroutine if no elements are found
            await random_delay(3000, 10000, 500)
            return None, 0
            
        else:
            fullName = fullNameElement[0].text.strip()
            nameParts = fullName.split(' ')
            firstName = nameParts[0] if nameParts else ''
            lastName = ' '.join(nameParts[1:]) if len(nameParts) > 1 else ''
    except Exception as error:
        print(f"Error extracting full name: {str(error)}")

    return {'firstName': firstName, 'lastName': lastName}

# Async function to extract email data
async def extractEmailData(driver):
    
    try:
        emailSection = WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.col-12.col-sm-11.pl-sm-1'))
        )
        driver.execute_script("arguments[0].scrollIntoView();", emailSection)

        emailElements = emailSection.find_elements(By.CSS_SELECTOR, 'div')
        emailData = [emailElement.text for emailElement in emailElements]
    except NoSuchElementException:
        emailData = []
    
    return emailData

async def extract_full_data(driver, target_name, retries=3):
    """Extract comprehensive data from the current page."""
    try:
        timeout = await get_random_timeout(15000, 30000, 1000, 5000)

        # Extract phone data
        phone_data = await extract_phone_data(driver, target_name)
        print(f"Phone data extracted: {phone_data}")

        if not phone_data and retries > 0:
            print("No phone data found on the initial page. Attempting relative link fallback...")
            
            relative_link_success = await relativeLink(driver, target_name)

            if relative_link_success:
                WebDriverWait(driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'div.col-12 col-sm-11.pl-sm-1'))
                )
                relative_data = await extract_full_data(driver, target_name, retries - 1)
                relative_data["relativeName"] = target_name
                return relative_data
            else:
                print("No matching link found for fallback, skipping extraction for this entry.")
                return {
                    "current_mailing_address": "",
                    "address": "",
                    "city": "",
                    "state": "",
                    "zipcode": "",
                    "first_name": "",
                    "last_name": "",
                    "phone_numbers": [],
                    "phone_types": [],
                    "formatted_phone_data": [],
                    "email_data": [],
                    "relative_name": ""
                }
        address_query = await extract_address_query(driver)
        phone_data = await extract_phone_data(driver, target_name)
        full_name = await extractFullName(driver)
        email_data = await extractEmailData(driver)
        return {
            'current_mailing_address': address_query,
            'address': '',
            'city': '',
            'state': '',
            'zipcode': '',
            'first_name': '','first_name': full_name['first_name'],
            'last_name': full_name['last_name'],
            'phone_numbers': phone_data.get("phone_numbers", []),
            'phone_types': phone_data.get("phone_types", []),
            'formatted_phone_data': phone_data['formatted_phone_data'],
            "email_data": email_data,
            'relative_name': ''
        }
    except Exception as error:
        logging.error(f"Error extracting comprehensive data: {str(error)}")
        return {
            'current_mailing_address': '',
            'address': '',
            'city': '',
            'state': '',
            'zipcode': '',
            'first_name': '',
            'last_name': '',
            'phone_numbers': [],
            'phone_types': [],
            'formatted_phone_data': '',
            'email_data': [],
            'relative_name': ''
        }

# Function to search for relative links based on the target name
async def relativeLink(driver, target_name):
    try:
        relative_section = WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '#personDetails > div:nth-child(18) > div.col-12.col-sm-11.pl-sm-1'))
            )
        print ("Relative link section found", relative_section)
        timeout = await get_random_timeout(15000, 30000, 1000, 5000)
        linkElements = relative_section.find_elements(By.CSS_SELECTOR, 'a > span')

        bestMatch = None
        highestSimilarity = 0

        targetLastName = target_name.split(' ')[-1]

        for element in linkElements:
            text = element.text
            if not isinstance(text, str) or not isinstance(target_name, str):
                print('Invalid text or targetName, skipping similarity check.')
                continue

            elementLastName = text.split(' ')[-1]
            similarityRate = string_similarity.ratio(elementLastName, targetLastName)

            print(f"Comparing '{elementLastName}' with '{targetLastName}': Similarity = {similarityRate}")
            if similarityRate > highestSimilarity:
                highestSimilarity = similarityRate
                bestMatch = element

        print(f"Best match: {bestMatch.text if bestMatch else 'None'} with similarity: {highestSimilarity}")
        if bestMatch and highestSimilarity >= 0.03:
            print(f"Clicking on best match: {bestMatch.text} with similarity rate: {highestSimilarity}")
            await human_like_mouse_movement(driver, bestMatch)
            bestMatch.click()
            return True
        else:
            print(f"No matching link found for '{target_name}' with sufficient similarity.")
            return False
    except Exception as error:
        print(f"Error in relativeLink: {str(error)}")
        return False
