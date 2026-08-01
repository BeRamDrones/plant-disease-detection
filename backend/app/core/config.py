import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database URL parsing and conversion for async engine compatibility
DATABASE_URL = os.getenv("POSTGRES_DATABASE_KEY", "postgresql://postgres:admin123@localhost:5432/Project_Jatayu")

if DATABASE_URL.startswith("postgresql://"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
else:
    ASYNC_DATABASE_URL = DATABASE_URL
