"""
Centralized configuration management.

All environment variables are loaded here and accessed via the `settings` object.
This provides a single source of truth for configuration across the application.
"""
import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./inbox.db")

    # Google/AI
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY")

    # OAuth
    OAUTH_REDIRECT_URI: str = os.getenv(
        "OAUTH_REDIRECT_URI", "http://localhost:8000/auth/gmail/callback"
    )

    # Security
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY")

    # Frontend
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    def validate(self) -> list[str]:
        """
        Validate that required settings are present.
        Returns a list of missing required settings.
        """
        missing = []
        required = ["GOOGLE_API_KEY", "ENCRYPTION_KEY"]
        for key in required:
            if not getattr(self, key):
                missing.append(key)
        return missing


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
