from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import ASYNC_DATABASE_URL

# Create the async engine
engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,  # Set to True for SQL logging during debugging
    future=True
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# Base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass

import logging
logger = logging.getLogger("app.core.database")

# Async DB session dependency with fallback error protection
async def get_db():
    try:
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()
    except Exception as exc:
        logger.warning(f"[Database] Async session error: {exc}")
        yield None
