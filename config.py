import os
from dotenv import load_dotenv

# Load variables from .env if it exists
load_dotenv()

class Config:
    # Use absolute path for SQLite to avoid issues on Render/Linux
    _default_db = "sqlite:///jobs.db"
    if os.name != 'nt': # If not Windows (likely Render/Linux)
        _default_db = "sqlite:////opt/render/project/src/jobs.db"
    
    DATABASE_URL = os.getenv("DATABASE_URL", _default_db)
    PORT = int(os.getenv("PORT", 8000))
    HOST = os.getenv("HOST", "127.0.0.1")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")

settings = Config()
