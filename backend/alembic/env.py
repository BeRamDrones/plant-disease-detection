import asyncio
import sys
import os
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Add backend directory to sys.path to enable importing the app module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import Base
from app.core.config import ASYNC_DATABASE_URL
# Import models to register metadata
from app.models.drone import Drone
from app.models.mission import Mission
from app.models.flight_zone import FlightZone
from app.models.detection import ParentModelDiseaseClassification

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Ensure the database URL is read dynamically from environment configuration
config.set_main_option("sqlalchemy.url", ASYNC_DATABASE_URL)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    # Ensure PostGIS extension exists in target database
    connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    
    context.configure(
        connection=connection,
        target_metadata=target_metadata
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    ini_section = config.get_section(config.config_ini_section, {})
    ini_section["sqlalchemy.url"] = ASYNC_DATABASE_URL
    print(f"[Alembic] Connecting to target database: {ASYNC_DATABASE_URL}")
    connectable = async_engine_from_config(
        ini_section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
        await connection.commit()

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
