from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import get_settings


def _create_engine():
    """Create SQLAlchemy engine with settings from environment."""
    settings = get_settings()
    database_url = settings.DATABASE_URL

    return create_engine(
        database_url,
        # SQLite compatibility
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
        # Connection pool settings for Supabase reliability
        pool_pre_ping=True,  # Check if connection is alive before using
        pool_recycle=300,    # Recycle connections after 5 minutes
        pool_size=5,         # Keep 5 connections in the pool
        max_overflow=10,     # Allow up to 10 extra connections under load
    )


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
