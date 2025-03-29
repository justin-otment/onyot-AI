import cv2
import numpy as np
import pyautogui
import pytesseract
import csv
import time
import os
from datetime import datetime

# Configure Tesseract Path (Optional, if not added to PATH)
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Configurations
SCREEN_RECORD_TIME = 60  # Time to record in seconds (Set to None for infinite)
FPS = 15
RESULT_REGION = (500, 300, 400, 100)  # (x, y, width, height) - Adjust to your game's result area
OUTPUT_VIDEO_PATH = "gameplay_recording.avi"
CSV_FILENAME = "game_results.csv"
INTERVAL_BETWEEN_EXTRACTIONS = 5  # Time between OCR scans in seconds

# Create CSV if not exists
if not os.path.exists(CSV_FILENAME):
    with open(CSV_FILENAME, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Timestamp", "Extracted Result"])

# Screen Recorder Function
def record_screen():
    screen_size = pyautogui.size()
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(OUTPUT_VIDEO_PATH, fourcc, FPS, screen_size)

    start_time = time.time()
    while True:
        img = pyautogui.screenshot()
        frame = np.array(img)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        out.write(frame)

        # Preview (Optional)
        cv2.imshow("Recording", frame)

        # Stop recording after set time
        if SCREEN_RECORD_TIME and (time.time() - start_time) > SCREEN_RECORD_TIME:
            break

        if cv2.waitKey(1) & 0xFF == ord('q'):  # Stop recording manually
            break

    out.release()
    cv2.destroyAllWindows()
    print(f"Recording saved as '{OUTPUT_VIDEO_PATH}'")

# OCR Result Extraction Function
def extract_results_with_ocr():
    while True:
        screenshot = pyautogui.screenshot(region=RESULT_REGION)
        image = np.array(screenshot)
        gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # OCR processing
        extracted_text = pytesseract.image_to_string(gray_image).strip()

        if extracted_text:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            save_result_to_csv(timestamp, extracted_text)
            print(f"[{timestamp}] Extracted: {extracted_text}")
        else:
            print("No readable result found.")

        time.sleep(INTERVAL_BETWEEN_EXTRACTIONS)

# Save extracted result to CSV
def save_result_to_csv(timestamp, result):
    with open(CSV_FILENAME, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([timestamp, result])

# Run both recording and OCR extraction in parallel
from threading import Thread

if __name__ == "__main__":
    record_thread = Thread(target=record_screen)
    ocr_thread = Thread(target=extract_results_with_ocr)

    # Start both threads
    record_thread.start()
    ocr_thread.start()

    # Optional: If you want both to stop after SCREEN_RECORD_TIME
    if SCREEN_RECORD_TIME:
        time.sleep(SCREEN_RECORD_TIME)
        print("Stopping data extraction after recording time limit.")
        # Threads won't "stop" cleanly, so you may need to Ctrl+C manually if using infinite OCR.
