import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Database URL resolution strategy:
# 1. NEON_DATABASE_URL or DATABASE_URL (Neon Serverless PostgreSQL / TimescaleDB)
# 2. POSTGRES_DATABASE_KEY (if non-localhost / valid remote host)
# 3. Fallback to SQLite (sqlite+aiosqlite:///./project_jatayu.db) for instant local execution
raw_url = os.getenv("NEON_DATABASE_URL") or os.getenv("DATABASE_URL")
postgres_key = os.getenv("POSTGRES_DATABASE_KEY", "")

if raw_url and raw_url.strip():
    DATABASE_URL = raw_url.strip()
elif postgres_key and not "localhost:5433" in postgres_key:
    DATABASE_URL = postgres_key.strip()
else:
    # Portable local SQLite database — zero external daemon required
    DATABASE_URL = "sqlite+aiosqlite:///./project_jatayu.db"

# Driver parsing for SQLAlchemy async engine
if DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
else:
    ASYNC_DATABASE_URL = DATABASE_URL

# Fix sslmode parameter for asyncpg compatibility if connecting to Neon DB
if "sslmode=" in ASYNC_DATABASE_URL:
    ASYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace("sslmode=require", "ssl=require").replace("sslmode=verify-full", "ssl=require")
