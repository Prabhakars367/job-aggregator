import requests
import logging
from abc import ABC, abstractmethod
from sqlalchemy.orm import Session
from models import Job
from datetime import datetime
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JobScraper(ABC):
    """Base class for all job scrapers."""
    
    @abstractmethod
    def scrape(self, db: Session) -> int:
        """
        Scrapes jobs and saves them to the database.
        Returns the number of new jobs added.
        """
        pass

    def save_job(self, db: Session, job_data: dict) -> bool:
        """
        Checks for duplicates and saves a job if it's new.
        """
        existing_job = db.query(Job).filter(Job.job_url == job_data['job_url']).first()
        if existing_job:
            logger.info(f"Skipping duplicate job: {job_data['job_title']} at {job_data['company_name']}")
            return False
        
        # Ensure experience_level is present
        if 'experience_level' not in job_data:
            job_data['experience_level'] = self.extract_experience(job_data.get('job_title', '') + " " + job_data.get('description', ''))

        new_job = Job(**job_data)
        db.add(new_job)
        db.commit()
        return True

    def extract_experience(self, text: str) -> str:
        """
        Extracts experience level from text (title or description).
        """
        text = text.lower()
        
        # Priority 1: Direct Level Keywords
        if any(word in text for word in ['lead', 'principal', 'staff', 'architect', 'manager', 'head']):
            return "Lead"
        if any(word in text for word in ['senior', 'sr.', 'sr ']):
            return "Senior"
        if any(word in text for word in ['junior', 'jr.', 'associate', 'fresher', 'intern', 'entry', '0-1 year', '0-2 year']):
            return "Entry"
        
        # Priority 2: Year patterns (e.g., "5+ years", "3-5 yrs", "0 to 2 years")
        import re
        
        # Look for range patterns first (e.g., "0-2 years", "1 to 3 yrs")
        range_match = re.search(r'(\d+)\s*[-to]+\s*(\d+)\s*(years|yrs|year)', text)
        if range_match:
            start_years = int(range_match.group(1))
            end_years = int(range_match.group(2))
            # Categorize based on the upper bound of the range
            return self.infer_level_from_years(end_years if start_years > 0 else start_years)
        
        # Look for single year patterns (e.g., "5+ years", "0 years")
        years_match = re.search(r'(\d+)\s*\+?\s*(years|yrs|year)', text)
        if years_match:
            years = int(years_match.group(1))
            return self.infer_level_from_years(years)
            
        return "Mid" # Default to Mid if info found but no specific level

    def infer_level_from_years(self, years: int) -> str:
        if years <= 2:
            return "Entry"
        if years <= 5:
            return "Mid"
        if years <= 10:
            return "Senior"
        return "Lead"

class GreenhouseScraper(JobScraper):
    """Scraper for Greenhouse job boards."""
    
    def __init__(self, board_token: str, company_name: str):
        self.board_token = board_token
        self.company_name = company_name
        self.api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"

    def scrape(self, db: Session) -> int:
        logger.info(f"Scraping Greenhouse jobs for {self.company_name}...")
        try:
            response = requests.get(self.api_url)
            response.raise_for_status()
            data = response.json()
            jobs = data.get('jobs', [])
            
            new_jobs_count = 0
            for job in jobs:
                job_data = {
                    "company_name": self.company_name,
                    "job_title": job.get('title'),
                    "job_url": job.get('absolute_url'),
                    "location": job.get('location', {}).get('name', 'Remote'),
                    "date_added": datetime.utcnow()
                }
                if self.save_job(db, job_data):
                    new_jobs_count += 1
            
            return new_jobs_count
        except Exception as e:
            logger.error(f"Error scraping Greenhouse for {self.company_name}: {e}")
            return 0

class GenericJSONScraper(JobScraper):
    """A template for custom hidden APIs that return JSON."""
    
    def __init__(self, company_name: str, url: str, headers: dict, mapping: dict):
        """
        mapping: dict that describes how to map JSON keys to Job model fields.
        Example mapping: {
            "root": "data.listings",
            "job_title": "position",
            "job_url": "link",
            "location": "office.city"
        }
        """
        self.company_name = company_name
        self.url = url
        self.headers = headers
        self.mapping = mapping

    def _get_nested_val(self, obj, path):
        """Helper to navigate nested JSON paths."""
        for part in path.split('.'):
            if obj is None: return None
            if isinstance(obj, list) and part.isdigit():
                obj = obj[int(part)]
            else:
                obj = obj.get(part)
        return obj

    def scrape(self, db: Session) -> int:
        logger.info(f"Scraping Generic JSON for {self.company_name}...")
        try:
            response = requests.get(self.url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            # Navigate to the root level where jobs are listed
            jobs = self._get_nested_val(data, self.mapping['root'])
            if not isinstance(jobs, list):
                logger.error(f"Root path {self.mapping['root']} did not return a list for {self.company_name}")
                return 0
                
            new_jobs_count = 0
            for job in jobs:
                job_data = {
                    "company_name": self.company_name,
                    "job_title": self._get_nested_val(job, self.mapping['job_title']),
                    "job_url": self._get_nested_val(job, self.mapping['job_url']),
                    "location": self._get_nested_val(job, self.mapping['location']) or 'Unknown',
                    "date_added": datetime.utcnow()
                }
                if self.save_job(db, job_data):
                    new_jobs_count += 1
            
            return new_jobs_count
        except Exception as e:
            logger.error(f"Error scraping Generic API for {self.company_name}: {e}")
            return 0

class LeverScraper(JobScraper):
    """Scraper for Lever job boards."""
    
    def __init__(self, company_id: str, company_name: str):
        self.company_id = company_id
        self.company_name = company_name
        self.api_url = f"https://api.lever.co/v0/postings/{company_id}?mode=json"

    def scrape(self, db: Session) -> int:
        logger.info(f"Scraping Lever jobs for {self.company_name}...")
        try:
            response = requests.get(self.api_url)
            response.raise_for_status()
            jobs = response.json()
            
            new_jobs_count = 0
            for job in jobs:
                job_data = {
                    "company_name": self.company_name,
                    "job_title": job.get('text'),
                    "job_url": job.get('hostedUrl'),
                    "location": job.get('categories', {}).get('location', 'Remote'),
                    "description": job.get('descriptionPlain', ''), # Lever often has this
                    "date_added": datetime.utcnow()
                }
                if self.save_job(db, job_data):
                    new_jobs_count += 1
            
            return new_jobs_count
        except Exception as e:
            logger.error(f"Error scraping Lever for {self.company_name}: {e}")
            return 0

class AshbyScraper(JobScraper):
    """Scraper for Ashby job boards."""
    
    def __init__(self, company_id: str, company_name: str):
        self.company_id = company_id
        self.company_name = company_name
        self.api_url = f"https://jobs.ashbyhq.com/api/non-auth-api/job-board/{company_id}"

    def scrape(self, db: Session) -> int:
        logger.info(f"Scraping Ashby jobs for {self.company_name}...")
        try:
            response = requests.get(self.api_url)
            response.raise_for_status()
            data = response.json()
            # Ashby structure usually has 'jobBoard' -> 'jobPostings'
            jobs = data.get('jobBoard', {}).get('jobPostings', [])
            
            new_jobs_count = 0
            for job in jobs:
                job_data = {
                    "company_name": self.company_name,
                    "job_title": job.get('title'),
                    "job_url": job.get('jobPostingUrl'),
                    "location": job.get('location', 'Remote'),
                    "date_added": datetime.utcnow()
                }
                if self.save_job(db, job_data):
                    new_jobs_count += 1
            
            return new_jobs_count
        except Exception as e:
            logger.error(f"Error scraping Ashby for {self.company_name}: {e}")
            return 0

class SmartRecruitersScraper(JobScraper):
    """Scraper for SmartRecruiters job boards."""
    
    def __init__(self, company_id: str, company_name: str):
        self.company_id = company_id
        self.company_name = company_name
        self.api_url = f"https://api.smartrecruiters.com/v1/companies/{company_id}/postings"

    def scrape(self, db: Session) -> int:
        logger.info(f"Scraping SmartRecruiters jobs for {self.company_name}...")
        try:
            response = requests.get(self.api_url)
            response.raise_for_status()
            jobs = response.json().get('content', [])
            
            new_jobs_count = 0
            for job in jobs:
                job_data = {
                    "company_name": self.company_name,
                    "job_title": job.get('name'),
                    "job_url": f"https://jobs.smartrecruiters.com/{self.company_id}/{job.get('id')}",
                    "location": f"{job.get('location', {}).get('city', 'Remote')}, {job.get('location', {}).get('country', '')}",
                    "date_added": datetime.utcnow()
                }
                if self.save_job(db, job_data):
                    new_jobs_count += 1
            
            return new_jobs_count
        except Exception as e:
            logger.error(f"Error scraping SmartRecruiters for {self.company_name}: {e}")
            return 0

class LinkedInScraper(JobScraper):
    """Scraper for LinkedIn Jobs using Guest Search API."""
    
    def __init__(self, keywords: str, location: str):
        self.keywords = keywords
        self.location = location
        self.api_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"

    def scrape(self, db: Session) -> int:
        logger.info(f"Scraping LinkedIn for {self.keywords} in {self.location}...")
        try:
            params = {
                "keywords": self.keywords,
                "location": self.location,
                "start": 0
            }
            # LinkedIn requires a User-Agent
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = requests.get(self.api_url, params=params, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            job_cards = soup.find_all('li')
            
            new_jobs_count = 0
            for card in job_cards:
                title_tag = card.find('h3', class_='base-search-card__title')
                company_tag = card.find('h4', class_='base-search-card__subtitle')
                location_tag = card.find('span', class_='job-search-card__location')
                link_tag = card.find('a', class_='base-card__full-link')
                
                if title_tag and company_tag and link_tag:
                    job_data = {
                        "company_name": company_tag.get_text(strip=True),
                        "job_title": title_tag.get_text(strip=True),
                        "job_url": link_tag['href'].split('?')[0],
                        "location": location_tag.get_text(strip=True) if location_tag else "Remote",
                        "date_added": datetime.utcnow()
                    }
                    if self.save_job(db, job_data):
                        new_jobs_count += 1
            
            return new_jobs_count
        except Exception as e:
            logger.error(f"Error scraping LinkedIn: {e}")
            return 0

class NaukriScraper(JobScraper):
    """Scraper for Naukri.com using V3 Search API."""
    
    def __init__(self, keyword: str, location: str):
        self.keyword = keyword
        self.location = location
        self.api_url = "https://www.naukri.com/jobapi/v3/search"

    def scrape(self, db: Session) -> int:
        logger.info(f"Scraping Naukri for {self.keyword} in {self.location}...")
        try:
            params = {
                "noOfResults": 20,
                "keyword": self.keyword,
                "location": self.location,
                "experience": 0
            }
            headers = {
                "appid": "109",
                "systemid": "109",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = requests.get(self.api_url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            jobs = data.get('jobDetails', [])
            
            new_jobs_count = 0
            for job in jobs:
                job_data = {
                    "company_name": job.get('companyName'),
                    "job_title": job.get('title'),
                    "job_url": f"https://www.naukri.com{job.get('jdURL')}",
                    "location": job.get('placeholders', [{}])[0].get('label', 'India'),
                    "description": job.get('jobDescription', ''), # Naukri API often has this
                    "date_added": datetime.utcnow()
                }
                if self.save_job(db, job_data):
                    new_jobs_count += 1
            
            return new_jobs_count
        except Exception as e:
            logger.error(f"Error scraping Naukri: {e}")
            return 0

def run_all_scrapers(db: Session):
    """Helper to run a list of configured scrapers."""
    scrapers = [
        # Indian Tech Companies (Greenhouse)
        GreenhouseScraper("phonepe", "PhonePe"),
        GreenhouseScraper("swiggy", "Swiggy"),
        GreenhouseScraper("razorpay", "Razorpay"),
        GreenhouseScraper("cred", "Cred"),
        GreenhouseScraper("meesho", "Meesho"),
        GreenhouseScraper("groww", "Groww"),
        GreenhouseScraper("dream11", "Dream11"),
        GreenhouseScraper("postman", "Postman"),
        
        # Indian Tech Companies (SmartRecruiters)
        SmartRecruitersScraper("Zomato1", "Zomato"),
        
        # Indian Tech Companies (Lever)
        LeverScraper("pocketfm", "Pocket FM"),
        LeverScraper("grab", "Grab India"),
        
        # Global Tech (Ashby - corrected logic often requires specific board ID)
        # GreenhouseScraper("vercel", "Vercel"), # Vercel also uses Greenhouse sometimes
        GreenhouseScraper("openai", "OpenAI"),
        GreenhouseScraper("figma", "Figma"),
        
        # Large Portals (Generic/Search)
        LinkedInScraper("Software Engineer", "India"),
        NaukriScraper("Frontend Developer", "Bangalore"),
    ]
    
    total_new = 0
    for scraper in scrapers:
        total_new += scraper.scrape(db)
    
    return total_new
