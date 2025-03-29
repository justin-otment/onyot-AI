import time
import csv
import os
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.remote.remote_connection import LOGGER
from undetected_chromedriver import Chrome, ChromeOptions


# Set logger level for Selenium
LOGGER.setLevel(logging.DEBUG)

# Constants
TIMEOUT = 10  # seconds
DELAY = 5  # seconds
OUTPUT_CSV = 'olj.csv'

# Helper function to delay execution
def delay(seconds):
    time.sleep(seconds)

# Constants
USER_DATA_DIR = "C:\\Users\\DELL\\AppData\\Local\\Google\\Chrome\\User Data"
PROFILE_DIRECTORY = "Profile 1"
SHEET_ID = "1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A"


def setup_chrome_driver():
    """Set up Chrome driver with custom options."""
    options = ChromeOptions()
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument("--remote-debugging-port=50567")
    options.add_argument(f"--profile-directory={PROFILE_DIRECTORY}")
    options.add_argument(f"--start-maximized")
    return Chrome(options=options)

# Initialize WebDriver
driver = setup_chrome_driver()
wait = WebDriverWait(driver, TIMEOUT)

def login_to_onlinejobs():
    try:
        driver.get("https://www.onlinejobs.ph")
        print("Navigated to OnlineJobs.ph")

        login_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@id='navbarSupportedContent']/ul/li[6]/a")))
        login_link.click()
        print("Clicked login link")

        username_input = wait.until(EC.presence_of_element_located((By.XPATH, "//*[@id='login_username']")))
        password_input = driver.find_element(By.XPATH, "//*[@id='login_password']")
        login_button = driver.find_element(By.XPATH, "/html/body/div[2]/section/div/div/div/div[1]/div/form/div[4]/button")

        username_input.send_keys("francis.garcia.realty@gmail.com")
        password_input.send_keys("anngong09")
        login_button.click()
        print("Logged in successfully")
    except Exception as e:
        print(f"Error during login: {e}")

def navigate_to_job_listings():
    try:
        job_listing_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@id='navbarSupportedContent']/ul/li[3]/a")))
        job_listing_link.click()
        print("Navigated to job listings")

        browse_jobs_link = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div/section[1]/div/div/div/div/div/div/a/u")))
        browse_jobs_link.click()
        print("Clicked on 'Browse all job posts'")
    except Exception as e:
        print(f"Error navigating to job listings: {e}")

def uncheck_full_time_option():
    try:
        full_time_checkbox = wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@id='advanceSearch']/div[3]/div[3]/label")))
        print("Unchecked 'Full-Time' option")
    except Exception as e:
        print(f"Error unchecking 'Full-Time' option: {e}")

def search_jobs(keyword):
    try:
        search_input = wait.until(EC.presence_of_element_located((By.XPATH, "//*[@id='jobkeyword']")))
        search_button = driver.find_element(By.XPATH, "//*[@id='myform']/div/div/dl/dt/button/span")

        search_input.send_keys(keyword)
        search_button.click()
        print(f"Searched for '{keyword}' jobs")
    except Exception as e:
        print(f"Error searching for jobs: {e}")

def scrape_job_data(max_pages=7):
    jobs_data = []

    for page in range(1, max_pages + 1):
        try:
            print(f"Scraping page {page}...")
            pagination_selector = f"body > div > section > div > div:nth-child(2) > div.col-md-9 > div.oj-pagination.text-center.pl-0.pt-2 > div > div > nav > ul > li:nth-child({page})"
            page_element = driver.find_element(By.CSS_SELECTOR, pagination_selector)

            actions = ActionChains(driver)
            actions.move_to_element(page_element).click().perform()
            delay(2)

            job_elements = driver.find_elements(By.CSS_SELECTOR, "h4.fs-16.fw-700")
            for job in job_elements:
                try:
                    job_title = job.text
                    # Check if the job title contains "real estate"
                    if "manager" not in job_title.lower():
                        continue  # Skip jobs without "real estate" in the title

                    parent_element = job.find_element(By.XPATH, './ancestor::a')
                    job_link = parent_element.get_attribute('href')

                    if job_link and job_title:
                        jobs_data.append({"Job Title": job_title, "Job Link": job_link})
                        print(f"Job Title: {job_title}, Link: {job_link}")
                except Exception as e:
                    print(f"Error extracting job data: {e}")
        except Exception as e:
            print(f"Error navigating to page {page}: {e}")
            break

    return jobs_data


def write_to_csv(data, append=False):
    file_exists = os.path.exists(OUTPUT_CSV)
    mode = 'a' if append else 'w'
    with open(OUTPUT_CSV, mode, newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["Job Title", "Job Link"])
        if not file_exists or not append:
            writer.writeheader()
        writer.writerows(data)

def apply_to_jobs(jobs_data):
    for job in jobs_data:
        job_link = job.get("Job Link")
        if not job_link:
            continue

        driver.get(job_link)
        print(f"Processing job URL: {job_link}")

        try:
            contact_name = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div/section[2]/div/div[4]/div/div/div[2]/p[1]/strong"))).text
        except:
            contact_name = "Not Found"

        try:
            job_title = wait.until(EC.presence_of_element_located((By.XPATH, "/html/body/div/section[1]/div/div/div/h1"))).text
        except:
            job_title = "Not Found"

        try:
            apply_button = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div/section[1]/div/div/div/div[2]/form/button")))
            apply_button.click()

            subject_input = wait.until(EC.presence_of_element_located((By.XPATH, "//*[@id='subject']")))
            message_body = driver.find_element(By.XPATH, "//*[@id='message']")
            points_input = driver.find_element(By.XPATH, "//*[@id='appy-form']/div[4]/div/input")
            send_button = driver.find_element(By.XPATH, "//*[@id='appy-form']/div[5]/div[1]/button")

            subject_input.send_keys(f"Job Application For: {job_title}")
            message_body.send_keys(
                f"Hi {contact_name},\n\n"
                "I hope my message finds you doing well.\n"
                "I saw your job advert via Onlinejobs PH, and thought I'd be a great candidate for it. "
                "I have a proven and strong background in real estate in several different industry niches, "
                "which makes me a great fit for the role itself.\n\n"
                "With my eight (8) years of experience in the Virtual Real Estate Market, "
                "I know I would nail it and get the job seamlessly done.\n\n"
                "Here's a quick URL/Link to my updated resume for your review:\n"
                "https://drive.google.com/file/d/1JQWQJxsNu6lAOwrN26FlKnkmBkBnlsZu/view?usp=drive_link\n\n"
                "And a link to my voice recording:\n"
                "https://drive.google.com/file/d/12Ou8JjUr-RRPnDziV16CmUDEi2q70aP2/view?usp=drive_link\n\n"
                "Sample Seller Call:\n"
                "https://drive.google.com/file/d/1sfe0yJ_ghQLQmWjU8c6Wg87EKpik7RRN/view?usp=drive_link\n\n"
                "Sample Buyer Call:\n"
                "https://drive.google.com/file/d/1fTsw-uPv2lAniVSI7XNkfm3XFapqjF0b/view?usp=drive_link\n\n"
                "I hope I'm not yet too late, and that the job is still open for me. "
                "Regardless, I am always looking forward to any real estate opportunity "
                "that I may indulge my skills and expertise with.\n\n"
                "Best Regards,\n"
                "J."
            )
            points_input.send_keys("2")
            send_button.click()
            print("Application submitted")
        except Exception as e:
            print(f"Error applying for job: {e}")

# Execute the script
try:
    login_to_onlinejobs()
    navigate_to_job_listings()
    uncheck_full_time_option()
    search_jobs("real estate")
    jobs = scrape_job_data(10)
    if jobs:
        write_to_csv(jobs)
        apply_to_jobs(jobs)
finally:
    driver.quit()
    print("Script completed")
