import asyncio
from selenium import webdriver
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
async def extract_address_query(driver, timeout=10):
    """
    Extracts the Current Mailing Address from the web page and formats it as a one-liner.

    :param driver: Selenium WebDriver instance.
    :param timeout: Maximum time to wait for the element (in seconds).
    :return: Extracted and formatted address query as a string.
    """
    address_query = ""
    
    try:
        address_query_element = await safe_find_element(driver, By.XPATH, '//*[@id="current_address_section"]/div[1]/h3/a', timeout)
        if address_query_element:
            await human_like_mouse_movement(driver, address_query_element)
            raw_address = address_query_element.text.strip()
            address_query = " ".join(raw_address.splitlines())
        else:
            logging.info("Address query element not found.")
            return ""
    except (NoSuchElementException, TimeoutException) as error:
        logging.error(f"Error extracting address query: {str(error)}")
        await error_handler(driver)
    return address_query 

# Async function to extract and format phone data
async def extract_phone_data(driver, target_name):
    """
    Extracts phone numbers and their corresponding types from the phone section of the web page.
    Formats the data into a readable string.

    :param driver: Selenium WebDriver `instance.
    :param targetName: The target name to be used in the relative_link function if no phone data is found.
    :return: A dictionary with phone numbers, phone types, and a formatted phone data string.
    """
    try:
        # Generate a random timeout
        timeout = await get_random_timeout(15000, 30000, 1000, 5000)

        # Locate the phone number section on the page
        phone_section = driver.find_element(By.ID, 'phone_number_section')

        # Extract phone types and phone numbers as separate lists
        phone_type_elements = phone_section.find_elements(By.CSS_SELECTOR, 'dt+dd')
        phone_number_elements = phone_section.find_elements(By.CSS_SELECTOR, 'a')

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

    except NoSuchElementException as error:
        print(f"Error extracting phone data: {error}")
        # Call error handler in case of failure
        return {
            'phone_numbers': [],
            'phone_types': [],
            'formatted_phone_data': ''
        }

# Async function to extract full name data
async def extract_full_name(driver):
    try:
        full_name_element = driver.find_elements(By.CSS_SELECTOR, 'div#full_name_section span.fullname')
        if full_name_element:
            full_name = full_name_element[0].text.strip()
            name_parts = full_name.split(' ')
            first_name = name_parts[0] if name_parts else ''
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''
            return {
                'first_name': first_name,
                'last_name': last_name
            }
        else:
            logging.info("Full name element not found.")
            return {
                'first_name': '',
                'last_name': ''
            }
    except (NoSuchElementException, TimeoutException) as error:
        logging.error(f"Error extracting full name: {str(error)}")
        await error_handler(driver)
        return {
            'first_name': '',
            'last_name': ''
        }

# Async function to extract email data
async def extractEmailData(driver):
    
    try:
        emailSection = driver.find_element(By.ID, 'email_section')
        emailElements = emailSection.find_elements(By.CSS_SELECTOR, 'h3')
        emailData = [emailElement.text for emailElement in emailElements]
    except NoSuchElementException:
        emailData = []
    
    return emailData

# Async function to extract comprehensive data
async def extract_comprehensive_data(driver, target_name, retries=1):
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
                    EC.presence_of_element_located((By.ID, "phone_number_section"))
                )
                relative_data = await extract_comprehensive_data(driver, target_name, retries - 1)
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
        full_name = await extract_full_name(driver)
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
        timeout = await get_random_timeout(15000, 30000, 1000, 5000)
        linkElements = driver.find_elements(By.CSS_SELECTOR, '#relative-links a')

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