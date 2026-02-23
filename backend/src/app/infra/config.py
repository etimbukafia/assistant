"""
Application configuration

Load settings from environment variables with sensible defaults.
"""
import os
from dataclasses import dataclass
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    """Application settings loaded from environment variables"""
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://localhost/donna")
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "3"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "2"))
    DB_POOL_RECYCLE_SECONDS: int = int(os.getenv("DB_POOL_RECYCLE_SECONDS", "300"))
    DB_POOL_TIMEOUT_SECONDS: int = int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "15"))
    
    # Google APIs
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")

    # Security
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
    
    # OAuth / Auth
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")
    GMAIL_OAUTH_REDIRECT_URI: str = os.getenv(
        "GMAIL_OAUTH_REDIRECT_URI",
        os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/auth/gmail/callback")
    )
    
    # Polar Billing
    POLAR_ACCESS_TOKEN: str = os.getenv("POLAR_ACCESS_TOKEN", "")
    POLAR_WEBHOOK_SECRET: str = os.getenv("POLAR_WEBHOOK_SECRET", "")
    POLAR_PRODUCT_ID: str = os.getenv("POLAR_PRODUCT_ID", "")
    
    # Application
    ENV: str = os.getenv("ENV", "development")  # development | staging | production
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")

    # Frontend
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # Backend public URL (used for push notification webhook addresses)
    API_URL: str = os.getenv("API_URL", "http://localhost:8000")
    ADMIN_EMAILS: str = os.getenv("ADMIN_EMAILS", "")
    
    # Gmail Pub/Sub
    GOOGLE_CLOUD_PROJECT_ID: str = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "")
    GMAIL_PUBSUB_TOPIC: str = os.getenv("GMAIL_PUBSUB_TOPIC", "gmail-notifications")
    GMAIL_PUBSUB_SUBSCRIPTION: str = os.getenv("GMAIL_PUBSUB_SUBSCRIPTION", "")
    GMAIL_PUBSUB_PUSH_SERVICE_ACCOUNT: str = os.getenv("GMAIL_PUBSUB_PUSH_SERVICE_ACCOUNT", "")
    GMAIL_WEBHOOK_TOKEN: str = os.getenv("GMAIL_WEBHOOK_TOKEN", "")
    GMAIL_WEBHOOK_AUDIENCE: str = os.getenv("GMAIL_WEBHOOK_AUDIENCE", "")
    GMAIL_WEBHOOK_REQUIRE_AUTH: bool = os.getenv("GMAIL_WEBHOOK_REQUIRE_AUTH", "true").lower() == "true"

    # Email
    MAX_EMAILS_PER_SYNC: int = int(os.getenv("MAX_EMAILS_PER_SYNC", "3"))
    
    # Trial
    TRIAL_DURATION_DAYS: int = int(os.getenv("TRIAL_DURATION_DAYS", "7"))

    # Vault proposals (human review queue) - currently unhooked by default
    PROPOSALS_ENABLED: bool = os.getenv("PROPOSALS_ENABLED", "false").lower() == "true"


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
    """
    Cached settings factory for dependency injection.
    
    Usage in FastAPI routes:
        settings: Settings = Depends(get_settings)
    
    Usage in services/classes:
        settings = get_settings()
    """
    return Settings()
