"""
Database module — SQLAlchemy engine, session management, and initialization.
Auto-creates the database and tables on first run.
"""

import logging
from urllib.parse import urlparse, urlunparse

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

from config import settings

from sqlalchemy import MetaData
logger = logging.getLogger(__name__)

# Force all tables and enums into the 'avatar' schema to bypass RDS public schema permission errors
metadata_obj = MetaData(schema="avatar")
Base = declarative_base(metadata=metadata_obj)


def _ensure_database_exists():
    """
    Connect to the default 'postgres' database and create the target
    database if it doesn't already exist. Runs once on startup.
    """
    parsed = urlparse(settings.database_url)
    db_name = parsed.path.lstrip("/")  # e.g. "k8s_incidents"

    if not db_name:
        logger.warning("No database name found in DATABASE_URL, skipping auto-create.")
        return

    # Build a URL pointing to the default 'postgres' database
    default_url = urlunparse(parsed._replace(path="/postgres"))

    try:
        temp_engine = create_engine(default_url, isolation_level="AUTOCOMMIT")
        with temp_engine.connect() as conn:
            result = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": db_name},
            )
            if not result.fetchone():
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                logger.info(f"✅ Created database '{db_name}'.")
            else:
                logger.info(f"✅ Database '{db_name}' already exists.")
        temp_engine.dispose()
    except Exception as e:
        logger.warning(f"Could not auto-create database: {e}. Continuing anyway...")


def _create_tables():
    """Import all models and create their tables if they don't exist."""
    import models  # noqa: F401  — registers models with Base
    from sqlalchemy import text
    
    # Ensure the 'avatar' schema is created before creating any tables
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS avatar;"))
        conn.commit()
    
    Base.metadata.create_all(bind=engine)
    logger.info("✅ Database tables ready.")


# ─── Auto-setup on first import ───
_ensure_database_exists()

engine = create_engine(settings.database_url, echo=False, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

_create_tables()


def init_db():
    """Manual trigger (kept for CLI compatibility). Already runs on import."""
    _create_tables()
    print("✅ Database tables created successfully.")


def get_db():
    """Dependency for FastAPI — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
