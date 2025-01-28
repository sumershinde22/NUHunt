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


def scrape_jobs():
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

        # Wait for job list to load
        WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.ID, "list"))
        )

        # Scrape job titles and companies
        print("Scraping job titles and companies...")
        jobs = []
        job_elements = driver.find_elements(By.CLASS_NAME, "list-item-body")
        for job_element in job_elements:
            try:
                title = job_element.find_element(By.CLASS_NAME, "list-item-title").text
                company = job_element.find_element(By.CLASS_NAME, "list-item-subtitle").text

                # Filter titles containing 'Software' or 'AI'
                if (("Software" in title or "AI" in title) or "Machine Learning" in title) or "Artificial Intelligence" in title:
                    jobs.append({"title": title, "company": company})
            except Exception as e:
                print(f"Error extracting job details: {e}")

        print(f"Scraped {len(jobs)} jobs matching the criteria.")

        # Insert jobs into Supabase and return new jobs count
        if jobs:
            return insert_into_supabase(jobs)
        else:
            return 0

    except Exception as e:
        print(f"An error occurred during scraping: {e}")
        return 0

    finally:
        print("Closing the WebDriver...")
        driver.quit()


def insert_into_supabase(jobs):
    try:
        print("Inserting data into Supabase...")
        existing_jobs = supabase.table("jobs").select("title", "company").execute().data
        existing_jobs_set = {(job["title"], job["company"]) for job in existing_jobs}

        new_jobs = [job for job in jobs if (job["title"], job["company"]) not in existing_jobs_set]

        if new_jobs:
            response = supabase.table("jobs").insert(new_jobs).execute()
            print(f"Inserted {len(new_jobs)} new jobs into Supabase.")
            print("Response:", response)
            send_email_notification(new_jobs)
            return len(new_jobs)
        else:
            print("No new jobs found.")
            return 0

    except Exception as e:
        print(f"Failed to insert data into Supabase: {e}")
        return 0


def send_email_notification(new_jobs):
    try:
        print("Sending email notification...")
        subject = "New Jobs Alert"
        body = "The following new jobs have been posted:\n\n"
        for job in new_jobs:
            body += f"Title: {job['title']}\nCompany: {job['company']}\n\n"

        msg = MIMEMultipart()
        msg["From"] = email_address
        msg["To"] = recipient_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        # Set up the SMTP server
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(email_address, email_password)
            server.send_message(msg)

        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")


# Run the scraping job and return the number of new jobs added
new_jobs_count = scrape_jobs()
print(f"Number of new jobs found: {new_jobs_count}")