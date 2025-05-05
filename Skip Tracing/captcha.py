import requests
import time
import logging
import asyncio
from nordvpn import handle_rate_limit  # Import rate-limit handling function
import os
from dotenv import load_dotenv
import json

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

            # Check network requests for sitekey exposure
            async def find_sitekey_from_network(response):
                if "captcha" in response.url.lower():
                    text = await response.text()
                    if "sitekey" in text:
                        match = re.search(r"sitekey[\"\']: ?[\"']([a-zA-Z0-9_-]+)", text)
                        if match:
                            return match.group(1)
                return None

            page.on("response", find_sitekey_from_network)

            # Extract sitekey from iframe or DOM elements
            sitekey = await page.evaluate("""() => {
                const selectors = [
                    '[data-sitekey]', 'input[name="sitekey"]', '.captcha-sitekey',
                    'div.h-captcha[data-sitekey]', '#captcha-container[data-sitekey]',
                    '.dynamic-captcha[data-sitekey]', 'iframe[src*="turnstile"]'
                ];
                for (const selector of selectors) {
                    const element = document.querySelector(selector);
                    if (element) {
                        return element.getAttribute('data-sitekey') || element.value;
                    }
                }
                return null;
            }""")

            # Try searching inside iframes
            if not sitekey:
                frames = page.frames
                for frame in frames:
                    sitekey = await frame.evaluate("""() => {
                        const element = document.querySelector('[data-sitekey]');
                        return element ? element.getAttribute('data-sitekey') : null;
                    }""")
                    if sitekey:
                        break

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
