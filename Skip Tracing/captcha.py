import os
import time
import re
import logging
import asyncio
import requests
from playwright.async_api import async_playwright

# === CAPTCHA Configuration ===
CAPTCHA_CONFIG = {
    "max_retries": 5,
    "wait_time_ms": 7000,
    "poll_interval_seconds": 5,
    "captcha_timeout_seconds": 75,
}

API_KEY = os.getenv("CAPTCHA_API_KEY")
CAPTCHA_API_URL = "http://2captcha.com"

# Logging config
LOGGING_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=LOGGING_FORMAT)


# === Utility: Extract CAPTCHA Sitekey ===
async def get_site_key(page):
    logging.info("[*] Searching for CAPTCHA sitekey...")

    sitekey_candidates = []

    async def log_network_response(response):
        try:
            text = await response.text()
            if "sitekey" in text:
                match = re.search(r'sitekey["\']?\s*[:=]\s*["\']([^"\']+)', text)
                if match:
                    sitekey = match.group(1)
                    sitekey_candidates.append(sitekey)
                    logging.info(f"[✓] Sitekey found in network response: {sitekey}")
        except:
            pass

    page.on("response", log_network_response)

    for attempt in range(CAPTCHA_CONFIG["max_retries"]):
        try:
            await page.wait_for_load_state("networkidle")
            logging.info(f"[*] Attempt {attempt + 1}: Searching for CAPTCHA sitekey...")

            # Try common selectors
            sitekey = await page.evaluate("""() => {
                const selectors = [
                    '[data-sitekey]',
                    'input[name="sitekey"]',
                    '.captcha-sitekey',
                    'div.h-captcha[data-sitekey]',
                    '#captcha-container[data-sitekey]',
                    '.dynamic-captcha[data-sitekey]'
                ];
                for (let sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el) return el.getAttribute('data-sitekey') || el.value;
                }
                return null;
            }""")

            # Try iframe scanning if no success
            if not sitekey:
                logging.info("[*] Trying iframe scanning for sitekey...")
                frames = page.frames
                for f in frames:
                    try:
                        frame_sitekey = await f.evaluate("""() => {
                            const el = document.querySelector('[data-sitekey]');
                            return el ? el.getAttribute('data-sitekey') : null;
                        }""")
                        if frame_sitekey:
                            sitekey = frame_sitekey
                            break
                    except:
                        continue

            if not sitekey and sitekey_candidates:
                sitekey = sitekey_candidates[0]

            if sitekey:
                logging.info(f"[✓] Sitekey found: {sitekey}")
                return sitekey
            else:
                logging.warning(f"[!] Sitekey not found on attempt {attempt + 1}. Retrying...")
                await asyncio.sleep(3)

        except Exception as e:
            logging.warning(f"[!] Error during sitekey fetch: {e}")
            await asyncio.sleep(3)

    logging.error("[✗] Sitekey extraction failed after max retries.")
    return None


# === Utility: Solve CAPTCHA with 2Captcha ===
def solve_turnstile_captcha(sitekey, url):
    if not API_KEY:
        logging.error("[✗] CAPTCHA_API_KEY is not set in environment.")
        return None

    try:
        # Submit CAPTCHA
        logging.info("[*] Submitting CAPTCHA to 2Captcha...")
        submit_resp = requests.post(f"{CAPTCHA_API_URL}/in.php", data={
            "key": API_KEY,
            "method": "turnstile",
            "sitekey": sitekey,
            "pageurl": url,
            "json": 1
        }, timeout=30)
        result = submit_resp.json()

        if result.get("status") != 1:
            logging.error(f"[!] 2Captcha error: {result}")
            return None

        captcha_id = result["request"]
        logging.info(f"[✓] CAPTCHA sent for solving. ID: {captcha_id}")

        # Poll for result
        start = time.time()
        while time.time() - start < CAPTCHA_CONFIG["captcha_timeout_seconds"]:
            time.sleep(CAPTCHA_CONFIG["poll_interval_seconds"])
            poll_resp = requests.get(f"{CAPTCHA_API_URL}/res.php", params={
                "key": API_KEY,
                "action": "get",
                "id": captcha_id,
                "json": 1
            }, timeout=15)
            poll_result = poll_resp.json()

            if poll_result.get("status") == 1:
                token = poll_result["request"]
                logging.info(f"[✓] CAPTCHA solved: {token}")
                return token

        logging.error("[✗] CAPTCHA solving timed out.")
        return None

    except requests.RequestException as e:
        logging.error(f"[✗] HTTP error during CAPTCHA solving: {e}")
        return None


# === Utility: Inject CAPTCHA Token ===
async def inject_token(page, captcha_token, url):
    try:
        logging.info("[*] Injecting CAPTCHA token into page.")
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
                  }
                  return false;
              }).catch(() => false);
        }""", captcha_token)

        if not response:
            logging.warning("[!] CAPTCHA submission failed. Reloading page...")
            await page.reload(wait_until="networkidle")
            return False

        logging.info(f"[✓] CAPTCHA bypass successful. Navigating to: {url}")
        await page.goto(url, wait_until="networkidle", timeout=60000)
        return True

    except Exception as e:
        logging.error(f"[✗] Error during CAPTCHA token injection: {e}")
        return False
