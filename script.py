import json
import time
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dateutil import parser
from dotenv import load_dotenv
from supabase import create_client, Client

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

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
chrome_options.add_argument("--headless")  # Run in headless mode
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")

# Initialize WebDriver
driver = webdriver.Chrome(service=chrome_service, options=chrome_options)
driver.set_page_load_timeout(10000)

def save_cookies():
    """Saves cookies to Supabase; 'updated_at' is auto-managed by Supabase/Postgres."""
    try:
        cookies = driver.get_cookies()
        cookies_json = json.dumps(cookies)

        # Upsert into Supabase. 'updated_at' is automatically updated if your DB is configured that way.
        supabase.table("cookies").upsert(
            {
                "id": 1,
                "cookies": cookies_json
            }
        ).execute()

        print("Cookies saved to Supabase.")
    except Exception as e:
        print(f"Error saving cookies: {e}")


def load_cookies():
    """Loads cookies from Supabase if they exist AND are not older than 5 hours."""
    try:
        response = supabase.table("cookies").select("*").eq("id", 1).single().execute()
        data = response.data

        if not data:
            print("No saved cookies in Supabase.")
            return False

        updated_at_str = data["updated_at"]
        print(f"Raw updated_at timestamp from Supabase: {updated_at_str}")

        # Use dateutil.parser to parse the timestamp more flexibly
        try:
            updated_at_dt = parser.isoparse(updated_at_str)  # Handles various timestamp formats
        except ValueError as ve:
            print(f"Error parsing timestamp '{updated_at_str}': {ve}")
            return False

        time_diff_seconds = (datetime.now() - updated_at_dt).total_seconds()
        if time_diff_seconds > 18000:
            print("Saved cookies are older than 5 hours. Clearing cookies table entry.")
            supabase.table("cookies").delete().eq("id", 1).execute()
            return False

        cookies = json.loads(data["cookies"])
        driver.get("https://northeastern-csm.symplicity.com/students/app/home")

        for cookie in cookies:
            print(f"Attempting to set cookie: {cookie}")
            if "domain" in cookie:
                if "northeastern-csm.symplicity.com" not in cookie["domain"]:
                    print(f"Warning: Cookie domain mismatch! Expected 'northeastern-csm.symplicity.com', but got {cookie['domain']}. Skipping this cookie.")
                    continue
            driver.add_cookie(cookie)

        driver.refresh()
        print("Cookies loaded from Supabase successfully.")
        return True

    except Exception as e:
        print(f"Error loading cookies from Supabase: {e}")
        import traceback
        print(traceback.format_exc())  # This prints the full stack trace for debugging.
        return False



def login():
    """Logs into the Northeastern job portal and saves cookies."""
    try:
        print("Logging into the Northeastern job portal...")
        driver.get("https://northeastern-csm.symplicity.com/students/app/home")

        print("Starting the WebDriver...")
        button = driver.find_element(By.XPATH, "//input[@value='Current Students and Alumni']")
        button.click()

        # Fill in username and password fields
        username_field = driver.find_element(By.ID, "username")
        password_field = driver.find_element(By.ID, "password")
        username_field.send_keys(username)
        password_field.send_keys(password)

        # Click the "Log In" button
        login_button = driver.find_element(By.XPATH, "//button[@name='_eventId_proceed']")
        login_button.click()
        time.sleep(20)

        # Handle Duo Authentication
        duo_iframe = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "duo_iframe"))
        )
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
        time.sleep(10)  # Wait for Duo authentication

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
        existing_jobs = supabase.table(table_name).select("id", "title", "company").execute().data
        existing_jobs_set = {(job["title"], job["company"]): job["id"] for job in existing_jobs}

        new_jobs = [job for job in jobs if (job["title"], job["company"]) not in existing_jobs_set]
        current_jobs_set = {(job["title"], job["company"]) for job in jobs}
        outdated_jobs = [
            job_id for (title, company), job_id in existing_jobs_set.items()
            if (title, company) not in current_jobs_set
        ]

        if new_jobs:
            supabase.table(table_name).insert(new_jobs).execute()
            print(f"Inserted {len(new_jobs)} new jobs into '{table_name}'.")

        if outdated_jobs:
            for job_id in outdated_jobs:
                supabase.table(table_name).delete().eq("id", job_id).execute()
            print(f"Deleted {len(outdated_jobs)} outdated jobs from '{table_name}'.")

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

        WebDriverWait(driver, timeout=100000).until(
            EC.presence_of_element_located((By.ID, "list"))
        )
        print("Found")
        jobs = []
        job_elements = driver.find_elements(By.CLASS_NAME, "list-item-body")
        if not job_elements:
            raise ValueError("No job elements found on the page. The structure may have changed.")

        for job_element in job_elements:
            try:
                title = job_element.find_element(By.CLASS_NAME, "list-item-title").text
                company = job_element.find_element(By.CLASS_NAME, "list-item-subtitle").text
                if any(keyword in title for keyword in ("Software", "AI", "Machine Learning", "Artificial Intelligence", "ML")):
                    jobs.append({"title": title, "company": company})
            except Exception as e:
                print(f"Error extracting job details: {e}")
                import traceback
                print(traceback.format_exc())

        print(f"Scraped {len(jobs)} jobs matching the criteria.")
        return update_supabase(jobs, table_name) if jobs else 0

    except ValueError as ve:
        print(f"Scraping error: {ve}")
    except Exception as e:
        print(f"An error occurred during scraping: {e}")
        import traceback
        print(traceback.format_exc())
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
    # Attempt to load existing cookies.
    # If none found OR they're older than 5 hours, do a fresh login.
    if not load_cookies():
        login()

    job_links = {
        "fall_jobs": (
            "https://northeastern-csm.symplicity.com/students/app/jobs/search"
            "?perPage=5000&page=1&sort=!postdate&ocr=f"
            "&el_work_term=62e86769398ef06e8102c40d39502733"
            "&exclude_applied_jobs=1"
        ),
        "summer_jobs": (
            "https://northeastern-csm.symplicity.com/students/app/jobs/search"
            "?perPage=5000&page=1&sort=!postdate&ocr=f"
            "&el_work_term=37226e910d4151f066cd60e5177508b6"
            "&exclude_applied_jobs=1"
        )
    }

    for table_name, url in job_links.items():
        new_jobs_count = scrape_jobs(url, table_name)
        print(f"Number of new jobs added to '{table_name}': {new_jobs_count}")
finally:
    driver.quit()

end_time = time.time()
print(f"Finished in {round(end_time - start_time, 2)} seconds.")
