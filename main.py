from fastapi import FastAPI, Depends, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import uvicorn

from models import SessionLocal, init_db, Job
from scrapers import run_all_scrapers

# Initialize database
init_db()

app = FastAPI(title="Job Aggregator")

# Setup templates
templates = Jinja2Templates(directory="templates")

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Serves the frontend dashboard."""
    jobs = db.query(Job).order_by(Job.date_added.desc()).all()
    return templates.TemplateResponse("index.html", {"request": request, "jobs": jobs})

@app.get("/api/jobs")
async def get_jobs_json(
    db: Session = Depends(get_db), 
    company: str = None, 
    title: str = None
):
    """Returns job listings in JSON format with optional filters."""
    query = db.query(Job)
    if company:
        query = query.filter(Job.company_name.contains(company))
    if title:
        query = query.filter(Job.job_title.contains(title))
    
    jobs = query.order_by(Job.date_added.desc()).all()
    return [
        {
            "id": j.id,
            "company_name": j.company_name,
            "job_title": j.job_title,
            "job_url": j.job_url,
            "location": j.location,
            "date_added": j.date_added.strftime("%Y-%m-%d")
        } 
        for j in jobs
    ]

@app.post("/api/scrape")
async def trigger_scrape(db: Session = Depends(get_db)):
    """Manually trigger the scraping engine."""
    new_jobs_added = run_all_scrapers(db)
    return {"message": "Scraping completed", "new_jobs_added": new_jobs_added}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
