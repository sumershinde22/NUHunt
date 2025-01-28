from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
import os
import time

# Load environment variables from .env file
load_dotenv()
username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")

# Set up ChromeDriver in headless mode
chrome_service = Service("/Users/sumershinde/chromedriver-mac-arm64/chromedriver")
chrome_options = Options()
chrome_options.add_argument("--headless")  # Run in headless mode
chrome_options.add_argument("--disable-gpu")  # Disable GPU acceleration
chrome_options.add_argument("--window-size=1920x1080")  # Set a fixed window size
chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Prevent detection as a bot

# Initialize WebDriver
driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

try:
    print("Starting the WebDriver in headless mode...")

    # Visit the login page
    login_url = "https://northeastern-csm.symplicity.com/students/app/jobs/search?perPage=500&page=1&sort=!postdate&ocr=f&targeted_academic_majors=0160&el_work_term=62e86769398ef06e8102c40d39502733&exclude_applied_jobs=1"
    print(f"Navigating to login URL: {login_url}")
    driver.get(login_url)

    # Locate and click the "Current Students and Alumni" button
    print("Locating and clicking 'Current Students and Alumni' button...")
    button = driver.find_element(By.XPATH, "//input[@value='Current Students and Alumni']")
    button.click()

    # Fill in username and password fields
    print("Filling in username and password...")
    username_field = driver.find_element(By.ID, "username")
    password_field = driver.find_element(By.ID, "password")
    username_field.send_keys(username)
    password_field.send_keys(password)

    # Click the "Log In" button
    print("Clicking the 'Log In' button...")
    login_button = driver.find_element(By.XPATH, "//button[@name='_eventId_proceed']")
    login_button.click()
    time.sleep(20)

    # Handle Duo Authentication
    print("Waiting for the Duo iframe to load...")
    duo_iframe = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.ID, "duo_iframe"))
    )
    print("Switching to the Duo iframe...")
    # Switch to the iframe
    driver.switch_to.frame(duo_iframe)

    # Locate the "Send Me a Push" button inside the iframe
    print("Locating 'Send Me a Push' button...")
    push_button = WebDriverWait(driver, 20).until(
        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Send Me a Push')]"))
    )
    push_button.click()
    print("Clicked 'Send Me a Push' button.")
    time.sleep(10)  # Wait for the push notification to be approved

    # Switch back to the main content
    driver.switch_to.default_content()

    # Extract job titles and companies
    print("Extracting job titles and companies...")
    jobs = []
    job_elements = WebDriverWait(driver, 60).until(
        EC.presence_of_all_elements_located((By.CLASS_NAME, "list-item-body"))
    )
    for job_element in job_elements:
        try:
            # Extract job title
            title_element = job_element.find_element(By.CLASS_NAME, "list-item-title")
            job_title = title_element.text.strip()

            # Extract company information
            company_element = job_element.find_element(By.CLASS_NAME, "list-item-subtitle")
            company_info = company_element.text.strip()

            # Filter jobs based on "Software" or "AI"
            if "Software" in job_title or "AI" in job_title:
                jobs.append({"title": job_title, "company": company_info})
        except Exception as e:
            print(f"An error occurred while processing a job element: {e}")

    # Print the extracted job information
    print("Filtered job list:")
    for job in jobs:
        print(f"Job Title: {job['title']}, Company: {job['company']}")

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    print("Closing the WebDriver...")
    driver.quit()
