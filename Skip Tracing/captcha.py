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

logging.basicConfig(level=logging.DEBUG, filename="logfile.log", filemode="a",
                    format="%(asctime)s - %(levelname)s - %(message)s")
logging.info("Script started")

load_dotenv()

# === Global Configurations ===
CAPTCHA_CONFIG = {
    "max_retries": 5,
    "wait_time_ms": 7000,
    "poll_interval_seconds": 5,
    "captcha_timeout_seconds": 75,
}
API_KEY = os.getenv("TWO_CAPTCHA_API_KEY")
CAPTCHA_API_URL = "http://2captcha.com"
CAPTCHA_SOLVE_TIMEOUT = 75  # Seconds

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

async def get_site_key(driver):
    """
    Extracts Turnstile CAPTCHA sitekey from Selenium page HTML or iframe.
    """
    try:
        html = await asyncio.to_thread(driver.page_source)
        soup = BeautifulSoup(html, "html.parser")

        # Check iframe URLs
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src", "")
            if "challenges.cloudflare.com/turnstile" in src:
                parsed = urlparse(src)
                qs = parse_qs(parsed.query)
                sitekey = qs.get("k", [None])[0]
                if sitekey:
                    logging.info(f"[✓] Found sitekey in iframe: {sitekey}")
                    return sitekey

        # Check for div with data-sitekey
        div = soup.find("div", {"data-sitekey": True})
        if div:
            logging.info(f"[✓] Found sitekey in data-sitekey div: {div['data-sitekey']}")
            return div["data-sitekey"]

        # Regex fallback
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
    Solves Turnstile CAPTCHA using 2Captcha.
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

            time.sleep(5)
            poll = requests.get(poll_url, headers=HEADERS).json()
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
    Injects the CAPTCHA token into a hidden form field and submits it.
    """
    try:
        logging.info("[!] Injecting CAPTCHA token into page...")

        def _inject():
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            form = driver.find_element(By.TAG_NAME, "form")
            if not form:
                return False

            driver.execute_script("""
                let form = document.querySelector('form');
                let input = document.createElement('input');
                input.type = 'hidden';
                input.name = 'cf-turnstile-response';
                input.value = arguments[0];
                form.appendChild(input);
                form.submit();
            """, token)

            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            return True

        result = await asyncio.to_thread(_inject)
        return result

    except Exception as e:
        logging.error(f"[!] inject_token error: {e}")
        return False
