from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Mapped, mapped_column
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()
DATABASE_URL = os.getenv("POSTGRES_DATABASE_KEY")
engine = create_engine(DATABASE_URL)  # fetches DB throudh URL
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def Get_Status():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()