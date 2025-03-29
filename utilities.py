import random
import asyncio
import time
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

async def get_safe(data, index, default=None):
    """
    Safely retrieves an item from a list or returns a default value if index is out of range.
    """
    try:
        return data[index] if index < len(data) else default
    except IndexError:
        return default


# Generates a random increment within a specified range
async def get_random_increment(min_value, max_value):
    return random.uniform(min_value, max_value)

# Increments a value by a random amount within a specified range
async def increment_value_randomly(value, min_increment, max_increment):
    increment = get_random_increment(min_increment, max_increment)
    return value + increment

# Async function to simulate random delays
async def random_delay(min_delay: int, max_delay: int, jitter: int = 0):
    delay = random.randint(min_delay, max_delay) + random.randint(0, jitter)
    await asyncio.sleep(delay / 1000)  # Convert milliseconds to seconds
    print(f"Waiting for {delay}ms")  # Optional: for debugging

# Types text into an input field with a random delay between each character (Async)
async def slow_mo_typing(driver, input_field, text, min_delay=20, max_delay=500, step=19):
    try:
        for char in text:
            await input_field.send_keys(char)
            delay = increment_value_randomly(min_delay, max_delay)
            await asyncio.sleep(delay / 1000)  # Use async sleep for delay
        print(f"Typed text with slow motion: \"{text}\"")
    except Exception as e:
        print("Error during slow motion typing:", e)

# Presses the return key with a delay (Async)
async def press_return_key_with_delay(driver, input_field):
    try:
        if input_field and hasattr(input_field, 'send_keys'):
            await input_field.send_keys(Keys.RETURN)
        else:
            raise TypeError('input_field.send_keys is not a function')
    except Exception as e:
        print("Error pressing return key:", e)

# Function to generate a random timeout value, with adjustable increments
async def get_random_timeout(min_value, max_value, min_increment=1000, max_increment=5000):
    """
    Generate a random timeout value between min_value and max_value, with an optional increment.
    :param min_value: Minimum value for the timeout (in milliseconds).
    :param max_value: Maximum value for the timeout (in milliseconds).
    :param min_increment: Minimum increment value for random adjustment (in milliseconds).
    :param max_increment: Maximum increment value for random adjustment (in milliseconds).
    :return: Random timeout value.
    """
    random_increment = random.randint(min_increment, max_increment)
    timeout = random.randint(min_value, max_value) + random_increment  # Add increment to the random timeout
    return timeout

# Retry finding an element with specified retries and delay (Async)
async def retry_find_element(driver, locator, retries=3, delay=2):
    attempt = 0
    while attempt < retries:
        try:
            return await driver.find_element(locator)
        except Exception as e:
            if attempt == retries - 1:
                print(f"Failed to locate element: {locator}", e)
                raise e
            await asyncio.sleep(delay)

# Human-like mouse movement on the element
async def human_like_mouse_movement(driver, element):
    actions = ActionChains(driver)
    actions.move_to_element(element).perform()

# Safe find element with a 10-second wait
async def safe_find_element(driver, by, value, timeout=10):
    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))
    except Exception as e:
        print(f"Error finding element {value}: {e}")
        return None

# Clears the input field and enters the provided text with a delay
async def clear_and_enter_text_with_delay(driver, by, value, text, delay=1):
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

# Example usage of randomDelay (async function now)
async def example_usage():
    await random_delay(1000, 10000, 550)
