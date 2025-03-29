import time
import re
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Setup Chrome options
chrome_options = Options()
chrome_options.add_argument("--start-maximized")

# Initialize WebDriver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

# Target URL
url = "https://www.mipublicnotices.com/#/?page=1&per=8&for=Default&area=82&dateRange=tm"

# File path for CSV
csv_file_path = r"C:\Users\DELL\Documents\Onyot.ai\Lead_List-Generator\python tests\externals\City_Notices\online_publication_leads.csv"

# Function to extract key details from text
def analyze_text(text):
    details = {
        "message": text[:200] + "...",  # Sample snippet
        "involved_parties": re.findall(r"\b[A-Z][a-z]+ [A-Z][a-z]+\b", text),
        "location": re.findall(r"\b(?:City|Town|County|State) of [A-Za-z ]+\b", text),
        "date": re.findall(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}\b", text),
        "amount": re.findall(r"\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?", text)
    }
    return details

# Function to write data to CSV
def write_to_csv(data, file_path):
    # Check if the file exists to determine if we need to write headers
    try:
        with open(file_path, 'r', newline='', encoding='utf-8') as f:
            pass
    except FileNotFoundError:
        # Write headers if file doesn't exist
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Message", "Involved Parties", "Location", "Date", "Amount"])

    # Append data to the CSV file
    with open(file_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([data['message'], ', '.join(data['involved_parties']), ', '.join(data['location']),
                         ', '.join(data['date']), ', '.join(data['amount'])])

try:
    driver.get(url)
    wait = WebDriverWait(driver, 10)

    # Wait for elements to load
    elements = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.jss3.jss42.jss50.jss61")))

    for i, elem in enumerate(elements):
        try:
            wait.until(EC.element_to_be_clickable(elem)).click()
            time.sleep(3)  # Wait for content to load

            # Extract text from all <p> elements
            paragraphs = driver.find_elements(By.CSS_SELECTOR, "p")
            extracted_text = "\n".join([p.text for p in paragraphs])

            # Analyze extracted text
            analysis = analyze_text(extracted_text)

            print(f"\n--- Notice {i+1} ---")
            print(f"Message: {analysis['message']}")
            print(f"Involved Parties: {analysis['involved_parties']}")
            print(f"Location: {analysis['location']}")
            print(f"Date: {analysis['date']}")
            print(f"Amount: {analysis['amount']}")

            # Write data to CSV
            write_to_csv(analysis, csv_file_path)

            driver.back()  # Navigate back to the main list
            time.sleep(2)

        except Exception as e:
            print(f"Error processing notice {i+1}: {e}")
            continue

except Exception as e:
    print(f"Script failed: {e}")

finally:
    driver.quit()
