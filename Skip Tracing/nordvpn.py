import os
import subprocess
import random
import asyncio
import platform
import shutil
import logging
import time
from dotenv import load_dotenv

# Load credentials from .env file
load_dotenv()
VPN_USERNAME = os.getenv("VPN_USERNAME")
VPN_PASSWORD = os.getenv("VPN_PASSWORD")

if not VPN_USERNAME or not VPN_PASSWORD:
    logging.error("[!] Missing VPN credentials in .env file. Please check.")
    exit(1)

vpn_folder_path = "externals/VPNs"  # Updated for Docker compatibility
OPENVPN_EXECUTABLE = "/usr/sbin/openvpn"
AUTH_FILE_PATH = "/app/externals/VPNs/auth.txt"

def list_vpn_configs(folder_path):
    try:
        vpn_files = [
            os.path.join(folder_path, file)
            for file in os.listdir(folder_path)
            if file.endswith(".ovpn")
        ]
        if not vpn_files:
            logging.warning("[!] No .ovpn files found in the VPN folder.")
        random.shuffle(vpn_files)
        return vpn_files
    except Exception as e:
        logging.error(f"[!] Error listing VPN configs: {e}")
        return []

def create_auth_file(auth_file_path):
    try:
        with open(auth_file_path, "w") as auth_file:
            auth_file.write(f"{VPN_USERNAME}\n{VPN_PASSWORD}")
        logging.debug(f"[DEBUG] Created auth file at: {auth_file_path}")
    except Exception as e:
        logging.error(f"[!] Error creating auth file: {e}")
        exit(1)

def terminate_existing_vpn():
    try:
        if platform.system() == "Windows":
            subprocess.run(["taskkill", "/F", "/IM", "openvpn.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.run(["pkill", "-f", "openvpn"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info("[✓] Terminated existing OpenVPN connections.")
    except Exception as e:
        logging.warning(f"[!] Failed to terminate existing VPN connections: {e}")

async def monitor_vpn_logs_with_timeout(process, timeout=30):
    start_time = time.time()
    while time.time() - start_time < timeout:
        line = process.stdout.readline()
        if line:
            decoded_line = line.decode("utf-8", errors="ignore")
            logging.debug(f"[DEBUG] OpenVPN log: {decoded_line}")
            if "Initialization Sequence Completed" in decoded_line:
                logging.info("[✓] VPN connected successfully!")
                return True
        await asyncio.sleep(0.5)
    logging.error("[!] VPN log monitoring timed out.")
    return False

async def switch_vpn(config_file):
    if not shutil.which("openvpn"):
        logging.error(f"[!] OpenVPN executable not found. Install it before proceeding.")
        return False

    terminate_existing_vpn()
    create_auth_file(AUTH_FILE_PATH)

    logging.info(f"[→] Switching to VPN with config: {config_file}")

    try:
        process = subprocess.Popen(
            [OPENVPN_EXECUTABLE, "--config", config_file, "--auth-user-pass", AUTH_FILE_PATH],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        success = await monitor_vpn_logs_with_timeout(process)
        return success
    except FileNotFoundError:
        logging.error(f"[!] OpenVPN executable not found at {OPENVPN_EXECUTABLE}. Ensure it is installed.")
        return False
    except Exception as e:
        logging.error(f"[!] Error during VPN switch: {e}")
        return False

async def verify_vpn_connection():
    try:
        flag = "-n" if platform.system() == "Windows" else "-c"
        process = subprocess.run(["ping", flag, "1", "8.8.8.8"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode == 0:
            logging.info("[✓] VPN connectivity verified successfully.")
            return True
        else:
            logging.warning("[!] VPN connectivity could not be verified.")
            return False
    except Exception as e:
        logging.error(f"[!] Error verifying VPN connectivity: {e}")
        return False

async def handle_rate_limit(page):
    vpn_files = list_vpn_configs(vpn_folder_path)
    if not vpn_files:
        logging.error("[!] No VPN configuration files found. Exiting...")
        return False

    retries = 5
    for attempt in range(1, retries + 1):
        config_file = random.choice(vpn_files)
        logging.warning(f"[!] Attempting VPN switch ({attempt}/{retries}) with config: {config_file}")

        success = await switch_vpn(config_file)
        if success:
            await asyncio.sleep(5)
            if not await verify_vpn_connection():
                logging.error("[!] VPN switch succeeded but connectivity could not be verified. Retrying...")
                continue

            logging.info(f"[✓] VPN switched successfully on attempt {attempt}. Reloading page...")
            try:
                await page.reload(wait_until="domcontentloaded", timeout=60000)
                logging.info("[✓] Page reloaded successfully after VPN switch.")
                await asyncio.sleep(3)
                return True
            except Exception as e:
                logging.error(f"[!] Error reloading page after VPN switch: {e}")
                continue

        logging.warning(f"[!] VPN switch failed on attempt {attempt}. Retrying...")
        backoff = 5 ** attempt
        logging.warning(f"[!] Backing off for {backoff} seconds...")
        await asyncio.sleep(backoff)

    logging.error("[!] Exhausted all retries. Rate limit handling failed.")
    return False
