import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database URL parsing and conversion for async engine compatibility
DATABASE_URL = (
    os.getenv("NEON_DATABASE_URL")
    or os.getenv("DATABASE_URL")
    or os.getenv("POSTGRES_DATABASE_KEY", "postgresql://postgres:admin123@localhost:5433/Project_Jatayu")
)

if DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
else:
    ASYNC_DATABASE_URL = DATABASE_URL

# Fix sslmode parameter for asyncpg compatibility if connecting to Neon DB
if "sslmode=" in ASYNC_DATABASE_URL:
    ASYNC_DATABASE_URL = ASYNC_DATABASE_URL.replace("sslmode=require", "ssl=require").replace("sslmode=verify-full", "ssl=require")
