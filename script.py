import json

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
from supabase import create_client, Client
from webdriver_manager.chrome import ChromeDriverManager
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import time

start_time = time.time()
# Load environment variables from .env
load_dotenv()
username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
email_address = os.getenv("EMAIL_ADDRESS")
email_password = os.getenv("EMAIL_PASSWORD")
recipient_email = os.getenv("RECIPIENT_EMAIL")

# Initialize Supabase client
supabase: Client = create_client(supabase_url, supabase_key)

# Set up ChromeDriver dynamically
chrome_service = Service(ChromeDriverManager().install())
chrome_options = Options()
chrome_options.add_argument("--headless")  # Headless mode to avoid opening browser
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")

# Initialize WebDriver
driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

def save_cookies():
    """Saves cookies to Supabase."""
    try:
        cookies = driver.get_cookies()
        cookies_json = json.dumps(cookies)

        # Store in Supabase
        response = supabase.table("cookies").upsert(
            {"id": 1, "cookies": cookies_json}
        ).execute()

        print("Cookies saved to Supabase.")
    except Exception as e:
        print(f"Error saving cookies: {e}")


def load_cookies():
    """Loads cookies from Supabase and applies them to WebDriver."""
    try:
        # Fetch cookies from Supabase
        response = supabase.table("cookies").select("cookies").eq("id", 1).single().execute()

        if not response.data:
            print("No saved cookies in Supabase.")
            return False

        cookies = json.loads(response.data["cookies"])
        driver.get("https://northeastern-csm.symplicity.com/students/app/home")

        for cookie in cookies:
            driver.add_cookie(cookie)

        driver.refresh()
        print("Cookies loaded from Supabase.")
        return True

    except Exception as e:
        print(f"Error loading cookies from Supabase: {e}")
        return False


def login():
    """Logs into the Northeastern job portal and saves cookies."""
    try:
        print("Logging into the Northeastern job portal...")
        driver.get("https://northeastern-csm.symplicity.com/students/app/home")

        print("Starting the WebDriver in headless mode...")
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
        driver.switch_to.frame(duo_iframe)

        # Locate and select "Remember me for 30 days" checkbox
        try:
            remember_me_checkbox = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.NAME, "dampen_choice"))
            )
            if not remember_me_checkbox.is_selected():
                remember_me_checkbox.click()
        except Exception as e:
            print(f"Could not select 'Remember me': {e}")

        # Click "Send Me a Push"
        push_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Send Me a Push')]"))
        )
        push_button.click()
        print("Clicked 'Send Me a Push' button.")
        time.sleep(10)  # Wait for the push notification to be approved

        # Switch back to the main content
        driver.switch_to.default_content()
        print("Login successful.")

        # Save cookies to Supabase
        save_cookies()

    except Exception as e:
        print(f"An error occurred during login: {e}")
        driver.quit()
        raise e


def update_supabase(jobs, table_name):
    """Updates the Supabase table by inserting new jobs and removing outdated ones."""
    try:
        print(f"Updating table '{table_name}'...")
        # Fetch existing jobs from Supabase
        existing_jobs = supabase.table(table_name).select("id", "title", "company").execute().data
        existing_jobs_set = {(job["title"], job["company"]): job["id"] for job in existing_jobs}

        # Identify new jobs to add
        new_jobs = [job for job in jobs if (job["title"], job["company"]) not in existing_jobs_set]

        # Identify outdated jobs to delete
        current_jobs_set = {(job["title"], job["company"]) for job in jobs}
        outdated_jobs = [job_id for (title, company), job_id in existing_jobs_set.items()
                         if (title, company) not in current_jobs_set]

        # Insert new jobs
        if new_jobs:
            response = supabase.table(table_name).insert(new_jobs).execute()
            print(f"Inserted {len(new_jobs)} new jobs into '{table_name}'.")

        # Delete outdated jobs
        if outdated_jobs:
            for job_id in outdated_jobs:
                supabase.table(table_name).delete().eq("id", job_id).execute()
            print(f"Deleted {len(outdated_jobs)} outdated jobs from '{table_name}'.")

        # Send notifications for new jobs
        if new_jobs:
            send_email_notification(new_jobs, table_name)

        return len(new_jobs)

    except Exception as e:
        print(f"Failed to update table '{table_name}': {e}")
        driver.quit()
        raise e


def scrape_jobs(url, table_name):
    """Scrapes jobs from a specific URL and updates the specified Supabase table."""
    try:
        print(f"Navigating to {url}...")
        driver.get(url)

        # Wait for job list to load
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.ID, "list"))
        )

        # Scrape job titles and companies
        print(f"Scraping jobs for table '{table_name}'...")
        jobs = []
        job_elements = driver.find_elements(By.CLASS_NAME, "list-item-body")
        for job_element in job_elements:
            try:
                title = job_element.find_element(By.CLASS_NAME, "list-item-title").text
                company = job_element.find_element(By.CLASS_NAME, "list-item-subtitle").text

                # Filter titles containing 'Software', 'AI', etc.
                if "Software" in title or "AI" in title or "Machine Learning" in title or "Artificial Intelligence" in title:
                    jobs.append({"title": title, "company": company})
            except Exception as e:
                print(f"Error extracting job details: {e}")

        print(f"Scraped {len(jobs)} jobs matching the criteria.")
        if jobs:
            return update_supabase(jobs, table_name)
        else:
            print(f"No jobs found for '{table_name}'.")
            return 0

    except Exception as e:
        print(f"An error occurred during scraping: {e}")
        return 0


def send_email_notification(new_jobs, table_name):
    """Sends an email notification with the new job postings."""
    try:
        print("Sending email notification...")
        subject = f"New Jobs Alert - {table_name}"
        body = f"New jobs have been posted in the '{table_name}' table:\n\n"
        for job in new_jobs:
            body += f"Title: {job['title']}\nCompany: {job['company']}\n\n"

        msg = MIMEMultipart()
        msg["From"] = email_address
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(email_address, email_password)
            server.send_message(msg)

        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")


# Main script
try:
    if not load_cookies():  # Try using cookies first
        login()  # If cookies fail, log in manually

    job_links = {
        "fall_jobs": "https://northeastern-csm.symplicity.com/students/app/jobs/search?perPage=5000&page=1&sort=!postdate&ocr=f&el_work_term=62e86769398ef06e8102c40d39502733&exclude_applied_jobs=1",
        "summer_jobs": "https://northeastern-csm.symplicity.com/students/app/jobs/search?perPage=5000&page=1&sort=!postdate&ocr=f&el_work_term=37226e910d4151f066cd60e5177508b6&exclude_applied_jobs=1"
    }

    for table_name, url in job_links.items():
        new_jobs_count = scrape_jobs(url, table_name)
        print(f"Number of new jobs added to '{table_name}': {new_jobs_count}")
finally:
    driver.quit()

end_time = time.time()

print(f"Finished in {round(end_time - start_time, 2)} seconds.")