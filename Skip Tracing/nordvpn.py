import os
import subprocess
import random
import asyncio
from dotenv import load_dotenv
import logging
import time

# Load credentials from .env file
dotenv_path = "C:/Users/DELL/Documents/Onyot.ai/Lead_List-Generator/python tests/Skip Tracing/.env"
load_dotenv(dotenv_path)
VPN_USERNAME = os.getenv("VPN_USERNAME")
VPN_PASSWORD = os.getenv("VPN_PASSWORD")

if not VPN_USERNAME or not VPN_PASSWORD:
    logging.error("[!] Missing VPN credentials in .env file. Please check.")
    exit(1)

# VPN folder path containing .ovpn files
vpn_folder_path = "C:/Users/DELL/Documents/Onyot.ai/Lead_List-Generator/python tests/externals/VPNs"

def list_vpn_configs(folder_path):
    """
    Lists all available VPN configuration files (.ovpn) in the given folder.
    :param folder_path: Path to the folder containing .ovpn files.
    :return: A shuffled list of VPN config file paths.
    """
    try:
        vpn_files = [
            os.path.join(folder_path, file)
            for file in os.listdir(folder_path)
            if file.endswith(".ovpn")
        ]
        if not vpn_files:
            logging.warning("[!] No .ovpn files found in the VPN folder.")
        random.shuffle(vpn_files)  # Randomize server order for variety
        return vpn_files
    except Exception as e:
        logging.error(f"[!] Error listing VPN configs: {e}")
        return []

def create_auth_file(auth_file_path):
    """
    Create a temporary auth.txt file containing VPN credentials.
    :param auth_file_path: Path to the auth.txt file.
    """
    try:
        with open(auth_file_path, "w") as auth_file:
            auth_file.write(f"{VPN_USERNAME}\n{VPN_PASSWORD}")
        logging.debug(f"[DEBUG] Created auth file at: {auth_file_path}")
    except Exception as e:
        logging.error(f"[!] Error creating auth file: {e}")
        exit(1)

def terminate_existing_vpn():
    """
    Terminate any existing OpenVPN processes to avoid conflicts.
    """
    try:
        subprocess.run(["taskkill", "/F", "/IM", "openvpn.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logging.info("[✓] Terminated existing OpenVPN connections.")
    except Exception as e:
        logging.warning(f"[!] Failed to terminate existing VPN connections: {e}")

async def monitor_vpn_logs_with_timeout(process, timeout=30):
    """
    Monitor VPN logs for connection success, with a timeout.
    :param process: The OpenVPN process to monitor.
    :param timeout: Maximum time (in seconds) to wait for connection confirmation.
    :return: True if connection is confirmed, False otherwise.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        line = process.stdout.readline()
        if line:
            decoded_line = line.decode("utf-8")
            logging.debug(f"[DEBUG] OpenVPN log: {decoded_line}")
            if "Initialization Sequence Completed" in decoded_line:
                logging.info("[✓] VPN connected successfully!")
                return True
        await asyncio.sleep(0.5)  # Avoid blocking
    logging.error("[!] VPN log monitoring timed out.")
    return False

async def switch_vpn(config_file):
    """
    Switch VPN using the specified configuration file.
    :param config_file: Path to the .ovpn configuration file.
    :return: True if VPN switch succeeded, False otherwise.
    """
    openvpn_executable = r"C:\Program Files\OpenVPN\bin\openvpn.exe"
    auth_file_path = "C:\\Users\\DELL\\Documents\\Onyot.ai\\Lead_List-Generator\\python tests\\externals\\VPNs\\auth.txt"

    terminate_existing_vpn()  # Terminate any existing VPN processes
    create_auth_file(auth_file_path)  # Create auth.txt file with credentials
    logging.info(f"[→] Switching to VPN with config: {config_file}")

    try:
        process = subprocess.Popen(
            [openvpn_executable, "--config", config_file, "--auth-user-pass", auth_file_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        # Use monitor_vpn_logs_with_timeout for connection confirmation
        success = await monitor_vpn_logs_with_timeout(process)
        if success:
            return True
        else:
            logging.error("[!] VPN connection failed or logs did not confirm connection.")
            return False

    except FileNotFoundError:
        logging.error(f"[!] OpenVPN executable not found at {openvpn_executable}. Ensure it is installed.")
        return False
    except Exception as e:
        logging.error(f"[!] Error during VPN switch: {e}")
        return False

async def verify_vpn_connection():
    """
    Verify if the VPN connection is established by pinging a reliable external host.
    :return: True if the connection is verified, False otherwise.
    """
    try:
        process = subprocess.run(["ping", "-n", "1", "8.8.8.8"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
            await asyncio.sleep(5)  # Allow time for VPN stabilization
            if not await verify_vpn_connection():
                logging.error("[!] VPN switch succeeded but connectivity could not be verified. Retrying...")
                continue

            logging.info(f"[✓] VPN switched successfully on attempt {attempt}. Reloading page...")
            try:
                await page.reload(wait_until="domcontentloaded", timeout=60000)
                logging.info("[✓] Page reloaded successfully after VPN switch.")
                await asyncio.sleep(3)  # Stabilization delay for CAPTCHA scripts
                return True
            except Exception as e:
                logging.error(f"[!] Error reloading page after VPN switch: {e}")
                continue

        logging.warning(f"[!] VPN switch failed on attempt {attempt}. Retrying...")
        backoff = 2 ** attempt  # Exponential backoff
        logging.warning(f"[!] Backing off for {backoff} seconds...")
        await asyncio.sleep(backoff)

    logging.error("[!] Exhausted all retries. Rate limit handling failed.")
    return False  # Indicate failure
