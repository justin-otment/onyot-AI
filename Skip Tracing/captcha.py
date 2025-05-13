import os
import re
import time
import json
import logging
import requests
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup

# Constants
API_KEY = os.getenv("TWO_CAPTCHA_API_KEY")  # Loaded from environment
CAPTCHA_SOLVE_TIMEOUT = 180  # seconds
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


async def get_site_key(page):
    """
    Extracts Turnstile sitekey from page HTML, iframes, or data attributes.
    """
    try:
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        # Look in iframe src
        for iframe in soup.find_all("iframe"):
            src = iframe.get("src", "")
            if "challenges.cloudflare.com/turnstile" in src:
                parsed = urlparse(src)
                qs = parse_qs(parsed.query)
                sitekey = qs.get("k", [None])[0]
                if sitekey:
                    logging.info(f"[✓] Found sitekey in iframe: {sitekey}")
                    return sitekey

        # Look for divs with data-sitekey
        div = soup.find("div", {"data-sitekey": True})
        if div:
            logging.info(f"[✓] Found sitekey in div: {div['data-sitekey']}")
            return div["data-sitekey"]

        # Regex fallback
        match = re.search(r'data-sitekey=["\']([\w-]+)["\']', html)
        if match:
            logging.info(f"[✓] Found sitekey via regex: {match.group(1)}")
            return match.group(1)

        logging.warning("[!] No sitekey found in the HTML.")
        return None

    except Exception as e:
        logging.error(f"[!] Error extracting sitekey: {e}")
        return None


def solve_turnstile_captcha(sitekey, page_url):
    """
    Sends CAPTCHA solving request to 2Captcha and polls for result.
    """
    if not API_KEY:
        logging.error("[!] TWO_CAPTCHA_API_KEY not set in environment.")
        return None

    try:
        logging.info(f"[✓] Submitting CAPTCHA solve request for sitekey {sitekey}")
        payload = {
            "key": API_KEY,
            "method": "turnstile",
            "sitekey": sitekey,
            "pageurl": page_url,
            "json": 1
        }
        response = requests.post("http://2captcha.com/in.php", data=payload, headers=HEADERS)
        result = response.json()

        if result.get("status") != 1:
            logging.error(f"[!] 2Captcha submission error: {result.get('request')}")
            return None

        request_id = result["request"]
        logging.info(f"[✓] CAPTCHA request submitted. Request ID: {request_id}")
        poll_url = f"http://2captcha.com/res.php?key={API_KEY}&action=get&id={request_id}&json=1"

        start_time = time.time()
        while True:
            if time.time() - start_time > CAPTCHA_SOLVE_TIMEOUT:
                logging.error("[!] CAPTCHA solve timed out.")
                return None

            time.sleep(5)
            poll_response = requests.get(poll_url, headers=HEADERS).json()
            if poll_response.get("status") == 1:
                logging.info("[✓] CAPTCHA solved successfully.")
                return poll_response["request"]
            elif poll_response.get("request") == "CAPCHA_NOT_READY":
                logging.debug("[…] CAPTCHA not ready yet, polling again...")
                continue
            else:
                logging.error(f"[!] CAPTCHA solve failed: {poll_response.get('request')}")
                return None

    except Exception as e:
        logging.error(f"[!] Exception during CAPTCHA solving: {e}")
        return None


async def inject_token(page, token, page_url):
    """
    Injects CAPTCHA token into a hidden form input and submits the page.
    """
    try:
        logging.info("[!] Injecting CAPTCHA token into page.")
        script = f"""
        () => {{
            const form = document.querySelector('form');
            if (!form) return false;
            const input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'cf-turnstile-response';
            input.value = '{token}';
            form.appendChild(input);
            form.submit();
            return true;
        }}
        """
        result = await page.evaluate(script)
        await page.wait_for_load_state("networkidle", timeout=60000)
        return result
    except Exception as e:
        logging.error(f"[!] Error injecting CAPTCHA token: {e}")
        return False
