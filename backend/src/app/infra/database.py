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

    is_sqlite = "sqlite" in database_url
    engine_kwargs = {
        "connect_args": {"check_same_thread": False} if is_sqlite else {},
    }
    if not is_sqlite:
        engine_kwargs.update(
            {
                "pool_pre_ping": True,
                "pool_recycle": settings.DB_POOL_RECYCLE_SECONDS,
                "pool_size": settings.DB_POOL_SIZE,
                "max_overflow": settings.DB_MAX_OVERFLOW,
                "pool_timeout": settings.DB_POOL_TIMEOUT_SECONDS,
            }
        )

    eng = create_engine(database_url, **engine_kwargs)

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
