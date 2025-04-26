import os
import subprocess
import random
import asyncio
from dotenv import load_dotenv
import logging

# Load credentials from environment variables
load_dotenv()  # Automatically loads `.env` if present in the root or parent directories
VPN_USERNAME = os.getenv("VPN_USERNAME")
VPN_PASSWORD = os.getenv("VPN_PASSWORD")

if not VPN_USERNAME or not VPN_PASSWORD:
    logging.error("[!] Missing VPN credentials. Please check environment variables or .env file.")
    exit(1)

# Use relative paths for compatibility
vpn_folder_path = "./VPNs"
auth_file_path = os.path.join(vpn_folder_path, "auth.txt")

def list_vpn_configs(folder_path):
    """Lists all available VPN configuration files (.ovpn) in the given folder."""
    try:
        vpn_files = [os.path.join(folder_path, file) for file in os.listdir(folder_path) if file.endswith(".ovpn")]
        if not vpn_files:
            logging.warning("[!] No .ovpn files found in the VPN folder.")
        random.shuffle(vpn_files)
        return vpn_files
    except Exception as e:
        logging.error(f"[!] Error listing VPN configs: {e}")
        return []

def create_auth_file(auth_file_path):
    """Create a temporary auth.txt file containing VPN credentials."""
    try:
        with open(auth_file_path, "w") as auth_file:
            auth_file.write(f"{VPN_USERNAME}\n{VPN_PASSWORD}")
        logging.debug(f"[DEBUG] Created auth file at: {auth_file_path}")
    except Exception as e:
        logging.error(f"[!] Error creating auth file: {e}")
        exit(1)

async def switch_vpn(config_file):
    """Switch VPN using the specified configuration file."""
    openvpn_executable = "/usr/sbin/openvpn"  # Path valid for Linux CI environments
    create_auth_file(auth_file_path)  # Create auth file with credentials
    logging.info(f"[→] Switching to VPN with config: {config_file}")

    try:
        result = subprocess.run(
            [openvpn_executable, "--config", config_file, "--auth-user-pass", auth_file_path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if result.returncode == 0:
            logging.info("[✓] VPN switched successfully!")
            return True
        else:
            logging.error(f"[!] VPN switch failed. Output:\n{result.stderr}")
            return False
    except FileNotFoundError:
        logging.error(f"[!] OpenVPN executable not found at {openvpn_executable}. Ensure it is installed.")
        return False
    except Exception as e:
        logging.error(f"[!] Error during VPN switch: {e}")
        return False

async def handle_rate_limit(page):
    """Handle rate-limit errors by switching VPN servers and retrying."""
    vpn_files = list_vpn_configs(vpn_folder_path)
    if not vpn_files:
        logging.error("[!] No VPN configuration files found. Exiting...")
        return False

    retries = 5  # Maximum retry attempts
    for attempt in range(1, retries + 1):
        config_file = random.choice(vpn_files)
        logging.warning(f"[!] Attempting VPN switch ({attempt}/{retries}) with config: {config_file}")
        success = await switch_vpn(config_file)

        if success:
            logging.info(f"[✓] VPN switched successfully on attempt {attempt}. Reloading page...")
            try:
                await page.reload(wait_until="domcontentloaded")
                return True
            except Exception as e:
                logging.error(f"[!] Error reloading page after VPN switch: {e}")
                return False

        logging.warning(f"[!] VPN switch failed on attempt {attempt}. Retrying...")
        backoff = 2 ** attempt  # Exponential backoff
        logging.warning(f"[!] Backing off for {backoff} seconds...")
        await asyncio.sleep(backoff)

    logging.error("[!] Exhausted all retries. Rate limit handling failed.")
    return False
