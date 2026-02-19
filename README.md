# India Job Aggregator Web App

A lightweight, dark-mode job aggregator built with FastAPI and modular "Hidden API" scrapers. Monitored companies include PhonePe, Swiggy, Zomato, LinkedIn, and more.

## 🚀 Deployment Instructions

To host this app online for free using GitHub and Render:

### 1. Push to GitHub
> [!NOTE]
> **I have already initialized git and committed your files locally.** You only need to run the following:

1. Create a new repository on GitHub named `job-aggregator-india`.
2. Run these commands in your terminal:
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/job-aggregator-india.git
   git push -u origin main
   ```

### 2. Host on Render
1. Create a free account at [Render.com](https://render.com).
2. Click **"New +"** -> **"Web Service"**.
3. Connect your GitHub repository.
4. Set the following:
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker`
5. Click **"Create Web Service"**.

## 🛠️ Local Setup
1. Clone the repo.
2. Install dependencies: `pip install -r requirements.txt`
3. Run: `python main.py`
4. Visit: `http://127.0.0.1:8000`

## ✨ Features
- **No Selenium**: Fast scraping via JSON/HTML fragments.
- **India Specific**: Quick-filter chips for Bangalore, Gurgaon, Pune.
- **Portals**: Support for LinkedIn, Naukri, Greenhouse, Lever, and Ashby.
