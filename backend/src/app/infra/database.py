import time
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import get_settings

logger = logging.getLogger(__name__)


def _create_engine(max_retries: int = 5, base_delay: float = 2.0):
    """Create SQLAlchemy engine with retry on DNS/connection failures."""
    settings = get_settings()
    database_url = settings.DATABASE_URL

    eng = create_engine(
        database_url,
        # SQLite compatibility
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
        # Connection pool settings for Supabase reliability
        pool_pre_ping=True,  # Check if connection is alive before using
        pool_recycle=300,    # Recycle connections after 5 minutes
        pool_size=5,         # Keep 5 connections in the pool
        max_overflow=10,     # Allow up to 10 extra connections under load
    )

    # Verify connectivity with retries (prevents startup crash on transient DNS failures)
    for attempt in range(1, max_retries + 1):
        try:
            eng.connect().close()
            return eng
        except Exception as e:
            if attempt == max_retries:
                logger.error(f"Database connection failed after {max_retries} attempts: {e}")
                raise
            delay = base_delay * (2 ** (attempt - 1))  # exponential backoff: 2s, 4s, 8s, 16s
            logger.warning(f"Database connection attempt {attempt}/{max_retries} failed: {e}. Retrying in {delay}s...")
            time.sleep(delay)

    return eng


engine = _create_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
