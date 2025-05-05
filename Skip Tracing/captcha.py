import requests
import time
import logging
import asyncio
from nordvpn import handle_rate_limit  # Import rate-limit handling function
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file

# === CAPTCHA Configuration ===
CAPTCHA_CONFIG = {
    "max_retries": 3,
    "wait_time_ms": 7000,  # Delay between retries in milliseconds
    "poll_interval_seconds": 5,  # Interval to poll for CAPTCHA solution
    "captcha_timeout_seconds": 75,  # Maximum waiting time for CAPTCHA solving
}

# API Key and URL for 2Captcha
API_KEY = os.getenv("TWO_CAPTCHA_API_KEY")  # Replace with actual 2Captcha API key
CAPTCHA_API_URL = "http://2captcha.com"

# Logging configuration
LOGGING_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)

# === Error Handling ===
async def handle_error(exception, attempt):
    logging.warning(f"[!] Error during sitekey fetch attempt {attempt + 1}: {exception}")
    await asyncio.sleep(2)  # Retry delay

# === CAPTCHA Sitekey Extraction ===
async def get_site_key(page):
    logging.info("[*] Searching for CAPTCHA sitekey...")

    for attempt in range(CAPTCHA_CONFIG["max_retries"]):
        try:
            await page.wait_for_load_state("networkidle")
            logging.info(f"[*] Attempt {attempt + 1}: Searching for CAPTCHA sitekey...")

            await page.wait_for_selector('[data-sitekey], iframe[src*="turnstile"]', timeout=60000)

            sitekey = await page.evaluate("""() => {
                const selectors = [
                    '[data-sitekey]', 'input[name="sitekey"]', '.captcha-sitekey',
                    'div.h-captcha[data-sitekey]', '#captcha-container[data-sitekey]', '.dynamic-captcha[data-sitekey]',
                    'iframe[src*="turnstile"]'
                ];

                for (const selector of selectors) {
                    const element = document.querySelector(selector);
                    if (element) {
                        return element.getAttribute('data-sitekey') || element.value;
                    }
                }
                return null;
            }""")

            if sitekey:
                logging.info(f"[✓] Sitekey found: {sitekey}")
                return sitekey

            logging.warning(f"[!] Sitekey not found on attempt {attempt + 1}. Retrying...")
            await asyncio.sleep(2)

        except Exception as e:
            await handle_error(e, attempt)

            if attempt == CAPTCHA_CONFIG["max_retries"] - 1:
                try:
                    html = await page.content()
                    with open("captcha_debug.html", "w", encoding="utf-8") as f:
                        f.write(html)
                    await page.screenshot(path="captcha_debug.png")
                    logging.info("[*] Saved debug screenshot and HTML for CAPTCHA failure.")
                except Exception as debug_e:
                    logging.warning(f"[!] Failed to save debug files: {debug_e}")

    logging.error("[✗] Sitekey extraction failed after maximum retries.")
    logging.info("[*] Triggering rate-limit handling...")
    await handle_rate_limit(page)
    return None


# === Solve CAPTCHA via 2Captcha API ===
def solve_turnstile_captcha(sitekey, url):
    try:
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

# === Inject CAPTCHA Token ===
async def inject_token(page, captcha_token, url):
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
