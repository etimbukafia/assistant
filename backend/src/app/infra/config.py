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
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    DB_POOL_RECYCLE_SECONDS: int = int(os.getenv("DB_POOL_RECYCLE_SECONDS", "300"))
    DB_POOL_TIMEOUT_SECONDS: int = int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "30"))
    
    # Google APIs
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_TRANSCRIPTION_MODEL: str = os.getenv("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")
    VOICE_CAPTURE_MAX_UPLOAD_BYTES: int = int(os.getenv("VOICE_CAPTURE_MAX_UPLOAD_BYTES", "10485760"))

    # Microsoft APIs
    MICROSOFT_CLIENT_ID: str = os.getenv("MICROSOFT_CLIENT_ID", "")
    MICROSOFT_CLIENT_SECRET: str = os.getenv("MICROSOFT_CLIENT_SECRET", "")

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
    
    # Billing provider
    # dodo (default) | polar
    BILLING_PROVIDER: str = os.getenv("BILLING_PROVIDER", "dodo").lower()

    # Dodo Payments
    DODO_PAYMENTS_API_KEY: str = os.getenv("DODO_PAYMENTS_API_KEY", os.getenv("DODO_API_KEY", ""))
    DODO_WEBHOOK_SECRET: str = os.getenv("DODO_WEBHOOK_SECRET", "")
    DODO_PRODUCT_ID: str = os.getenv("DODO_PRODUCT_ID", "")
    DODO_PRODUCT_ID_MONTHLY: str = os.getenv("DODO_PRODUCT_ID_MONTHLY", "")
    DODO_PRODUCT_ID_ANNUAL: str = os.getenv("DODO_PRODUCT_ID_ANNUAL", "")
    DODO_CREDIT_TOPUP_PRODUCT_ID: str = os.getenv("DODO_CREDIT_TOPUP_PRODUCT_ID", "")
    DODO_CREDIT_TOPUP_MIN_USD: int = int(os.getenv("DODO_CREDIT_TOPUP_MIN_USD", "5"))
    DODO_CREDIT_TOPUP_MAX_USD: int = int(os.getenv("DODO_CREDIT_TOPUP_MAX_USD", "500"))
    DODO_CREDIT_TOPUP_UNIT_USD: int = int(os.getenv("DODO_CREDIT_TOPUP_UNIT_USD", "1"))
    DODO_MODE: str = os.getenv("DODO_MODE", "test_mode").lower()  # test_mode | live_mode
    DODO_BASE_URL: str = os.getenv("DODO_BASE_URL", "")
    DODO_WEBHOOK_MAX_AGE_SECONDS: int = int(os.getenv("DODO_WEBHOOK_MAX_AGE_SECONDS", "300"))

    # Polar Billing (legacy/optional fallback)
    POLAR_ACCESS_TOKEN: str = os.getenv("POLAR_ACCESS_TOKEN", os.getenv("POLAR_API_KEY", ""))
    POLAR_WEBHOOK_SECRET: str = os.getenv("POLAR_WEBHOOK_SECRET", "")
    POLAR_PRODUCT_ID: str = os.getenv("POLAR_PRODUCT_ID", os.getenv("POLAR_PRO_PRODUCT_ID", ""))
    
    # Application
    ENV: str = os.getenv("ENV", "development")  # development | staging | production
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000")
    FORCE_HTTPS: bool = os.getenv("FORCE_HTTPS", "false").lower() == "true"

    # LLM provider selection
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini").lower()
    LLM_EMAIL_PROVIDER: str = os.getenv("LLM_EMAIL_PROVIDER", "gemini").lower()
    LLM_CHAT_PROVIDER: str = os.getenv("LLM_CHAT_PROVIDER", "gemini").lower()
    LLM_DRAFT_PROVIDER: str = os.getenv("LLM_DRAFT_PROVIDER", os.getenv("LLM_CHAT_PROVIDER", "gemini")).lower()
    LLM_EMAIL_MODEL: str = os.getenv("LLM_EMAIL_MODEL", "gemma-3-4b-it")
    LLM_CHAT_MODEL: str = os.getenv("LLM_CHAT_MODEL", "gemini-2.5-flash-lite")
    LLM_DRAFT_MODEL: str = os.getenv("LLM_DRAFT_MODEL", os.getenv("LLM_CHAT_MODEL", "gemini-2.5-flash-lite"))

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
    TRIAL_GRACE_DAYS: int = int(os.getenv("TRIAL_GRACE_DAYS", "0"))
    PRO_GRACE_DAYS: int = int(os.getenv("PRO_GRACE_DAYS", "4"))
    # Dunning policy
    DUNNING_WINDOW_DAYS: int = int(os.getenv("DUNNING_WINDOW_DAYS", "7"))
    DUNNING_EXPECTED_RETRIES: int = int(os.getenv("DUNNING_EXPECTED_RETRIES", "3"))
    DUNNING_MIDPOINT_DAY: int = int(os.getenv("DUNNING_MIDPOINT_DAY", "3"))
    # Notification category switches
    ENABLE_REMINDER_NOTIFICATIONS: bool = os.getenv("ENABLE_REMINDER_NOTIFICATIONS", "false").lower() == "true"
    ENABLE_DIGEST_NOTIFICATIONS: bool = os.getenv("ENABLE_DIGEST_NOTIFICATIONS", "false").lower() == "true"
    BILLING_REQUIRE_IDEMPOTENCY_KEY: bool = os.getenv("BILLING_REQUIRE_IDEMPOTENCY_KEY", "true").lower() == "true"
    BILLING_IDEMPOTENCY_TTL_SECONDS: int = int(os.getenv("BILLING_IDEMPOTENCY_TTL_SECONDS", "86400"))
    BILLING_EVENT_RETENTION_DAYS: int = int(os.getenv("BILLING_EVENT_RETENTION_DAYS", "90"))
    WEBHOOK_LOG_RETENTION_DAYS: int = int(os.getenv("WEBHOOK_LOG_RETENTION_DAYS", "30"))
    WEBHOOK_DELIVERY_RETENTION_DAYS: int = int(os.getenv("WEBHOOK_DELIVERY_RETENTION_DAYS", "30"))
    UI_TELEMETRY_RETENTION_DAYS: int = int(os.getenv("UI_TELEMETRY_RETENTION_DAYS", "30"))
    CHAT_METRICS_RETENTION_DAYS: int = int(os.getenv("CHAT_METRICS_RETENTION_DAYS", "30"))

    # Vault proposals (human review queue) - currently unhooked by default
    PROPOSALS_ENABLED: bool = os.getenv("PROPOSALS_ENABLED", "false").lower() == "true"


    def validate(self) -> list[str]:
        """
        Validate that required settings are present.
        Returns a list of missing required settings.
        """
        missing = []
        if not self.ENCRYPTION_KEY:
            missing.append("ENCRYPTION_KEY")

        active_providers = {
            self.LLM_PROVIDER,
            self.LLM_EMAIL_PROVIDER,
            self.LLM_CHAT_PROVIDER,
            self.LLM_DRAFT_PROVIDER,
        }

        if "gemini" in active_providers and not (self.GEMINI_API_KEY or self.GOOGLE_API_KEY):
            missing.append("GOOGLE_API_KEY or GEMINI_API_KEY")

        if "anthropic" in active_providers and not self.ANTHROPIC_API_KEY:
            missing.append("ANTHROPIC_API_KEY")
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
