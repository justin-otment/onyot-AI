import os
import subprocess

def restart_nordvpn():
    """
    Executes the updated AHK script created for NordVPN using subprocess.
    """
    ahk_script_path = r"C:\\Users\\DELL\\Documents\\Onyot.ai\\Lead_List-Generator\\python tests\\nordvpn.ahk"

    # Check if the AHK script exists
    if not os.path.exists(ahk_script_path):
        print(f"AHK script not found at: {ahk_script_path}")
        return

    try:
        # Use subprocess to run the AHK script
        subprocess.run(["AutoHotkey.exe", ahk_script_path], check=True)
        print("AHK script executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error occurred while executing the AHK script: {e}")

# Example usage
if __name__ == "__main__":
    restart_nordvpn()
