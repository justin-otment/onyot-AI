import re
import time
import json
import requests
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os
import logging
import asyncio

# Configure logging to log to a file with a specific format.
logging.basicConfig(
    level=logging.DEBUG,
    filename="logfile.log",
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.info("Script started")

load_dotenv()

# === Global Configurations ===
CAPTCHA_CONFIG = {
    "max_retries": 5,
    "wait_time_ms": 7000,             # Milliseconds to wait after a CAPTCHA is detected
    "poll_interval_seconds": 5,       # Seconds between each poll for a solution
    "captcha_timeout_seconds": 75,    # Maximum seconds to wait for a solved CAPTCHA
}

API_KEY = os.getenv("TWO_CAPTCHA_API_KEY")
if not API_KEY:
    logging.error("[!] TWO_CAPTCHA_API_KEY not set in environment.")

# Use HTTPS if available (more secure)
CAPTCHA_API_URL = "https://2captcha.com"
CAPTCHA_SOLVE_TIMEOUT = CAPTCHA_CONFIG["captcha_timeout_seconds"]

# Define common headers (update the User-Agent string if needed)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


async def get_site_key(driver):
    """
    Extracts the Turnstile CAPTCHA sitekey from Selenium page HTML or an iframe.
    """
    try:
        # Use asyncio.to_thread to avoid blocking on driver.page_source
        html = await asyncio.to_thread(lambda: driver.page_source)
        soup = BeautifulSoup(html, "html.parser")

        # First, check for an iframe containing the Turnstile challenge.
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src", "")
            if "challenges.cloudflare.com/turnstile" in src:
                parsed = urlparse(src)
                qs = parse_qs(parsed.query)
                sitekey = qs.get("k", [None])[0]
                if sitekey:
                    logging.info(f"[✓] Found sitekey in iframe: {sitekey}")
                    return sitekey

        # Next, try to find a div with a data-sitekey attribute.
        div = soup.find("div", {"data-sitekey": True})
        if div:
            logging.info(f"[✓] Found sitekey in data-sitekey div: {div['data-sitekey']}")
            return div["data-sitekey"]

        # As a fallback, use regex to search for data-sitekey in the HTML.
        match = re.search(r'data-sitekey=["\']([\w-]+)["\']', html)
        if match:
            logging.info(f"[✓] Found sitekey via regex: {match.group(1)}")
            return match.group(1)

        logging.warning("[!] No sitekey found on page.")
        return None

    except Exception as e:
        logging.error(f"[!] get_site_key error: {e}")
        return None


def solve_turnstile_captcha(sitekey, page_url):
    """
    Solves the Turnstile CAPTCHA using the 2Captcha API.
    Submits a CAPTCHA task and then polls for the result until either solved or a timeout occurs.

    :param sitekey: The CAPTCHA sitekey extracted from the page.
    :param page_url: The URL of the page where the CAPTCHA is located.
    :return: The CAPTCHA token if solved successfully, or None if an error occurs.
    """
    if not API_KEY:
        logging.error("[!] TWO_CAPTCHA_API_KEY not set in environment.")
        return None

    try:
        logging.info(f"[!] Submitting CAPTCHA solve request for sitekey: {sitekey}")
        payload = {
            "key": API_KEY,
            "method": "turnstile",
            "sitekey": sitekey,
            "pageurl": page_url,
            "json": 1
        }
        resp = requests.post(f"{CAPTCHA_API_URL}/in.php", data=payload, headers=HEADERS)
        result = resp.json()

        if result.get("status") != 1:
            logging.error(f"[!] 2Captcha submission error: {result.get('request')}")
            return None

        request_id = result["request"]
        logging.info(f"[✓] CAPTCHA task ID: {request_id}")

        poll_url = f"{CAPTCHA_API_URL}/res.php?key={API_KEY}&action=get&id={request_id}&json=1"
        start = time.time()

        while True:
            if time.time() - start > CAPTCHA_SOLVE_TIMEOUT:
                logging.error("[!] CAPTCHA solve timed out.")
                return None

            time.sleep(CAPTCHA_CONFIG["poll_interval_seconds"])
            poll_response = requests.get(poll_url, headers=HEADERS)
            try:
                poll = poll_response.json()
            except json.JSONDecodeError:
                logging.error("[!] Failed to decode JSON from 2Captcha response.")
                continue

            if poll.get("status") == 1:
                logging.info("[✓] CAPTCHA solved.")
                return poll["request"]

            if poll.get("request") == "CAPCHA_NOT_READY":
                logging.debug("[…] Waiting for CAPTCHA solution...")
                continue

            logging.error(f"[!] CAPTCHA solve error: {poll.get('request')}")
            return None

    except Exception as e:
        logging.error(f"[!] solve_turnstile_captcha exception: {e}")
        return None


async def inject_token(driver, token):
    """
    Injects the solved CAPTCHA token into a hidden form field on the page and submits the form.

    :param driver: Selenium WebDriver instance.
    :param token: The solved CAPTCHA token.
    :return: True if the token was successfully injected and submitted, False otherwise.
    """
    try:
        logging.info("[!] Injecting CAPTCHA token into page...")

        def _inject():
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            try:
                form = driver.find_element(By.TAG_NAME, "form")
            except Exception as e:
                logging.error(f"[!] Form not found: {e}")
                return False

            driver.execute_script(
                """
                let form = document.querySelector('form');
                if (!form) { return false; }
                let input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'cf-turnstile-response';
                input.value = arguments[0];
                form.appendChild(input);
                form.submit();
                return true;
                """,
                token
            )

            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            return True

        result = await asyncio.to_thread(_inject)
        return result

    except Exception as e:
        logging.error(f"[!] inject_token error: {e}")
        return False


def solve_captcha(driver, row_index):
    """
    Wrapper function so that your main script can call `solve_captcha(driver, row_index)`
    without needing to know the underlying implementation. This function extracts the CAPTCHA sitekey 
    using get_site_key() and then tries to solve the CAPTCHA using solve_turnstile_captcha().
    
    :param driver: Selenium WebDriver instance.
    :param row_index: The current row index (used for logging only).
    :return: True if the CAPTCHA solving process returns a valid token; False otherwise.
    """
    try:
        # Extract the sitekey asynchronously (this call blocks until complete)
        sitekey = asyncio.run(get_site_key(driver))
        if not sitekey:
            logging.error("[!] Could not find CAPTCHA sitekey, cannot proceed.")
            return False
        
        # Use the current URL of the driver as page_url
        page_url = driver.current_url
        
        token = solve_turnstile_captcha(sitekey, page_url)
        if token:
            logging.info("[✓] CAPTCHA solved; token received.")
            return True
        else:
            logging.error("[!] CAPTCHA could not be solved.")
            return False
    except Exception as e:
        logging.error(f"[!] solve_captcha error: {e}")
        return False
