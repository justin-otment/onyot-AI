import requests
import os
import time
import logging
import json
from nordvpn import switch_vpn  # Import external function

# === Configurations ===
CAPTCHA_CONFIG = {
    "max_retries": 5,
    "wait_time_ms": 7000,
    "poll_interval_seconds": 5,
    "captcha_timeout_seconds": 75,
}

API_KEY = os.getenv('APIKEY_2CAPTCHA', 'a01559936e2950720a2c0126309a824e')
CAPTCHA_API_URL = "http://2captcha.com"
LOGGING_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)

retry_counter = 0  # Keeps track of failed CAPTCHA attempts

# === CAPTCHA Detection ===
async def detect_captcha(content):
    """
    Checks the page content for CAPTCHA presence.
    :param content: The HTML content of the page.
    :return: True if CAPTCHA detected, False otherwise.
    """
    if "captcha" in content.lower() or "are you a human" in content.lower():
        logging.warning("[!] CAPTCHA detected.")
        return True
    return False

# === CAPTCHA Solving ===
async def solve_captcha(page, url):
    """
    Solves CAPTCHA dynamically using external APIs and retries the request.
    :param page: The Playwright page object.
    :param url: Target URL.
    :return: True if CAPTCHA solved successfully, False otherwise.
    """
    global retry_counter
    logging.info("[!] CAPTCHA detected. Attempting to solve.")
    sitekey = await get_site_key(page)
    if not sitekey:
        logging.error("[!] No valid sitekey found.")
        return False

    logging.info(f"[✓] Sitekey found: {sitekey}. Solving CAPTCHA via external API.")
    captcha_token = solve_turnstile_captcha(sitekey, url)
    if not captcha_token:
        logging.error("[!] CAPTCHA solving failed.")
        retry_counter += 1
        if retry_counter >= 2:  # After 2 failed attempts
            logging.warning("[!] Failed CAPTCHA attempts exceeded threshold. Switching VPN...")
            vpn_success = switch_vpn()
            if vpn_success:
                logging.info("[✓] VPN rotated successfully. Retrying CAPTCHA solving...")
            else:
                logging.error("[✗] VPN rotation failed.")
            retry_counter = 0  # Reset counter after VPN rotation
        return False

    success = await inject_token(page, captcha_token, url)
    if success:
        logging.info("[✓] CAPTCHA solved. Reloading page...")
        retry_counter = 0  # Reset counter after successful resolution
        await page.reload(wait_until="networkidle")
        content = await page.content()
        if not await detect_captcha(content):
            logging.info("[✓] CAPTCHA resolved successfully.")
            return True

    logging.warning("[!] CAPTCHA challenge persists after solving.")
    retry_counter += 1
    if retry_counter >= 2:  # After 2 failed attempts
        logging.warning("[!] Failed CAPTCHA attempts exceeded threshold. Switching VPN...")
        vpn_success = switch_vpn()
        if vpn_success:
            logging.info("[✓] VPN rotated successfully. Retrying CAPTCHA solving...")
        else:
            logging.error("[✗] VPN rotation failed.")
        retry_counter = 0  # Reset counter after VPN rotation
    return False

# === Sitekey Extraction ===
async def get_site_key(page):
    """
    Extracts the CAPTCHA site key dynamically from the page with enhanced robustness.
    """
    logging.info("[*] Attempting to locate CAPTCHA sitekey...")
    for attempt in range(CAPTCHA_CONFIG["max_retries"]):
        try:
            await page.wait_for_load_state("networkidle")
            await page.wait_for_selector("[data-sitekey], input[name='sitekey'], .captcha-sitekey", timeout=60000)

            site_key = await page.evaluate("""() => {
                let selectors = [
                    document.querySelector('[data-sitekey]'),
                    document.querySelector('input[name="sitekey"]'),
                    document.querySelector('.captcha-sitekey')
                ];
                for (let selector of selectors) {
                    if (selector) {
                        return selector.getAttribute('data-sitekey') || selector.value;
                    }
                }
                return null;
            }""")

            if site_key:
                logging.info(f"[✓] Sitekey found: {site_key}")
                return site_key
            else:
                logging.warning(f"[!] Attempt {attempt + 1}: Sitekey not found. Retrying...")
                await page.wait_for_timeout(CAPTCHA_CONFIG["wait_time_ms"])

        except Exception as e:
            logging.error(f"[!] Error during attempt {attempt + 1}: {e}")
            await page.wait_for_timeout(CAPTCHA_CONFIG["wait_time_ms"])

    logging.error("[✗] Failed to locate CAPTCHA sitekey after maximum retries.")
    return None

# === CAPTCHA Solving API ===
def solve_turnstile_captcha(sitekey, url):
    """
    Sends CAPTCHA solving request to 2Captcha API.
    """
    try:
        response = requests.post(f"{CAPTCHA_API_URL}/in.php", data={
            "key": API_KEY,
            "method": "turnstile",
            "sitekey": sitekey,
            "pageurl": url,
            "json": 1
        })

        logging.debug(f"[DEBUG] Raw response: {response.text}")
        response.raise_for_status()

        request_data = response.json()
        if request_data.get("status") != 1:
            logging.error(f"[!] API response error: {request_data}")
            return None

        captcha_id = request_data["request"]
        logging.info(f"[✓] CAPTCHA solving request sent. ID: {captcha_id}. Waiting for solution...")

        start_time = time.time()
        while time.time() - start_time < CAPTCHA_CONFIG["captcha_timeout_seconds"]:
            time.sleep(CAPTCHA_CONFIG["poll_interval_seconds"])
            solved_response = requests.get(f"{CAPTCHA_API_URL}/res.php?key={API_KEY}&action=get&id={captcha_id}&json=1")
            logging.debug(f"[DEBUG] Polling raw response: {solved_response.text}")

            solved_response.raise_for_status()
            solved_data = solved_response.json()

            if solved_data.get("status") == 1:
                captcha_token = solved_data["request"]
                logging.info(f"[✓] CAPTCHA solved successfully: {captcha_token}")
                return captcha_token

        logging.error("[!] CAPTCHA solving timed out.")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"[!] Network or HTTP error: {e}")
        return None
    except ValueError as e:
        logging.error(f"[!] JSON decoding error: {e}")
        return None

# === CAPTCHA Token Injection ===
async def inject_token(page, captcha_token, url):
    """
    Injects CAPTCHA token, submits validation, and ensures return to original inquiry.
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
