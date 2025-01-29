# NUHunt

NUHunt is an automated job scraping bot designed for Northeastern University students to track and receive alerts (hunt) for new job postings from NUWorks. It automates job searches, stores results in a Supabase database, and sends email notifications for new job postings.

## Features
- **Automated Job Scraping**: Fetches job postings from NUWorks for specific terms.
- **Job Filtering**: Captures job titles containing "Software", "AI", "Machine Learning", or "Artificial Intelligence".
- **Database Integration**: Stores and updates job listings in Supabase.
- **Email Alerts**: Sends notifications when new jobs are posted.
- **Job Cleanup**: Removes job listings that are no longer available.
- **GitHub Actions Support**: Runs automatically on a schedule.

## Installation
### Prerequisites
- Python 3.11
- Google Chrome & ChromeDriver
- Supabase account
- SMTP email credentials

### Setup
1. Clone this repository:
   ```sh
   git clone https://github.com/yourusername/NUHunt.git
   cd NUHunt
   ```
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the project directory:
   ```sh
   USERNAME="your_nuworks_username"
   PASSWORD="your_nuworks_password"
   SUPABASE_URL="your_supabase_url"
   SUPABASE_KEY="your_supabase_key"
   EMAIL_ADDRESS="your_email@example.com"
   EMAIL_PASSWORD="your_email_password"
   RECIPIENT_EMAIL="recipient_email@example.com"
   ```

## Usage
Run the script manually:
```sh
python script.py
```

## Automating with GitHub Actions
This project includes a GitHub Actions workflow to run NUHunt at scheduled times.
To enable it:
1. Add your environment variables as GitHub Secrets.
2. Commit and push changes to your repository.
3. The workflow runs every hour from 9 AM to 10 PM EST.
