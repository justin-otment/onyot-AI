import requests
import time
import logging
import asyncio
from playwright.async_api import async_playwright

# === CAPTCHA Configuration ===
CAPTCHA_CONFIG = {
    "max_retries": 5,  # Maximum retries for CAPTCHA solving
    "wait_time_ms": 7000,  # Delay between retries in milliseconds
    "poll_interval_seconds": 5,  # Interval to poll for CAPTCHA solution
    "captcha_timeout_seconds": 75,  # Maximum waiting time for CAPTCHA solving
}

# API Key and URL for 2Captcha
API_KEY = "a01559936e2950720a2c0126309a824e"  # Replace with your actual 2Captcha API key
CAPTCHA_API_URL = "http://2captcha.com"

# Logging configuration
LOGGING_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)


# === Utility: Extract CAPTCHA Sitekey (HTML + Network Request Handling) ===
async def get_site_key(page):
    """
    Extract CAPTCHA sitekey using Playwright with enhanced debugging.
    :param page: Playwright page object.
    :return: The extracted sitekey or None if not found.
    """
    logging.info("[*] Searching for CAPTCHA sitekey...")

    for attempt in range(CAPTCHA_CONFIG["max_retries"]):
        try:
            await page.wait_for_load_state("networkidle")
            logging.info(f"[*] Attempt {attempt + 1}: Searching for CAPTCHA sitekey...")

            # Capture network requests looking for site-key dynamically
            sitekey_candidates = []
            
            async def log_network_request(response):
                text = await response.text()
                if "sitekey" in text:
                    logging.info(f"[✓] Potential sitekey found in network response: {response.url}")
                    sitekey_candidates.append(text)

            page.on("response", log_network_request)

            # Extract sitekey from known HTML elements
            sitekey = await page.evaluate("""() => {
                let selectors = [
                    document.querySelector('[data-sitekey]'),
                    document.querySelector('input[name="sitekey"]'),
                    document.querySelector('.captcha-sitekey'),
                    document.querySelector('div.h-captcha[data-sitekey]'),
                    document.querySelector('#captcha-container[data-sitekey]'),
                    document.querySelector('.dynamic-captcha[data-sitekey]')
                ];
                for (let selector of selectors) {
                    if (selector) {
                        return selector.getAttribute('data-sitekey') || selector.value;
                    }
                }
                return null;
            }""")

            # If no sitekey found in HTML, check network logs
            if not sitekey and sitekey_candidates:
                sitekey = sitekey_candidates[0]  # Using the first extracted instance

            if sitekey:
                logging.info(f"[✓] Sitekey found: {sitekey}")
                return sitekey
            else:
                logging.warning(f"[!] Sitekey not found on attempt {attempt + 1}. Retrying...")
                await asyncio.sleep(3)  # Shorter retry delay for dynamic loading

        except Exception as e:
            logging.warning(f"[!] Error during sitekey fetch attempt {attempt + 1}: {e}")
            await asyncio.sleep(3)  # Retry delay

    logging.error("[✗] Sitekey extraction failed after maximum retries.")
    return None


# === Utility: Solve CAPTCHA via 2Captcha API ===
def solve_turnstile_captcha(sitekey, url):
    """
    Sends CAPTCHA solving request to 2Captcha API.
    :param sitekey: The CAPTCHA sitekey extracted from the page.
    :param url: The page URL where the CAPTCHA is located.
    :return: The solved CAPTCHA token or None if solving fails.
    """
    try:
        # Send CAPTCHA solving request to 2Captcha
        response = requests.post(f"{CAPTCHA_API_URL}/in.php", data={
            "key": API_KEY,
            "method": "turnstile",
            "sitekey": sitekey,
            "pageurl": url,
            "json": 1
        })
        response.raise_for_status()

        request_data = response.json()
        if request_data.get("status") != 1:
            logging.error(f"[!] API response error: {request_data}")
            return None

        captcha_id = request_data["request"]
        logging.info(f"[✓] CAPTCHA solving request sent. ID: {captcha_id}. Waiting for solution...")

        # Poll for CAPTCHA solution
        start_time = time.time()
        while time.time() - start_time < CAPTCHA_CONFIG["captcha_timeout_seconds"]:
            time.sleep(CAPTCHA_CONFIG["poll_interval_seconds"])
            solved_response = requests.get(f"{CAPTCHA_API_URL}/res.php?key={API_KEY}&action=get&id={captcha_id}&json=1")
            solved_response.raise_for_status()

            solved_data = solved_response.json()
            if solved_data.get("status") == 1:
                captcha_token = solved_data["request"]
                logging.info(f"[✓] CAPTCHA solved successfully: {captcha_token}")
                return captcha_token

        logging.error("[!] CAPTCHA solving timed out.")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"[!] Network or HTTP error during CAPTCHA solving: {e}")
        return None
    except ValueError as e:
        logging.error(f"[!] JSON decoding error during CAPTCHA solving: {e}")
        return None


# === Utility: Inject CAPTCHA Token ===
async def inject_token(page, captcha_token, url):
    """
    Injects the CAPTCHA token into the page and submits the form for validation.
    :param page: Playwright page object.
    :param captcha_token: The solved CAPTCHA token.
    :param url: The page URL for navigation after injection.
    :return: True if the injection and navigation succeed, False otherwise.
    """
    try:
        logging.info("[✓] Attempting CAPTCHA token injection.")
        response = await page.evaluate("""(token) => {
            return fetch("/internalcaptcha/captchasubmit", {
                method: "POST",
                body: new URLSearchParams({ 'captchaToken': token }),
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-Requested-With': 'XMLHttpRequest'
                }
            }).then(res => res.json())
              .then(data => {
                  if (data.RedirectUrl) {
                      document.location.href = data.RedirectUrl;
                      return true;
                  } else {
                      return false;
                  }
              }).catch(error => {
                  console.error(error);
                  return false;
              });
        }""", captcha_token)

        if not response:
            logging.warning("[!] CAPTCHA submission failed. Reloading page...")
            await page.reload(wait_until="networkidle")
            return False

        logging.info(f"[✓] CAPTCHA solved! Navigating back to URL: {url}")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        return True

    except Exception as e:
        logging.error(f"[!] Error injecting CAPTCHA token: {e}")
        return False
