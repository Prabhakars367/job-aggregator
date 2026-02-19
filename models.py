from sqlalchemy import Column, Integer, String, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

# SQLite Database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./jobs.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, index=True)
    job_title = Column(String, index=True)
    job_url = Column(String, unique=True, index=True)
    location = Column(String)
    date_added = Column(DateTime, default=datetime.datetime.utcnow)

# Create the tables
def init_db():
    Base.metadata.create_all(bind=engine)
