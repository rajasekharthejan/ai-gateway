"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Central configuration for the AI Gateway."""

    # Application
    APP_NAME: str = "AI Gateway"
    APP_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://gateway:gateway_pass@localhost:5432/ai_gateway"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Provider API keys
    OPENAI_API_KEY: str = ""
    AZURE_OPENAI_ENDPOINT: str = ""
    AZURE_OPENAI_KEY: str = ""
    AZURE_OPENAI_API_VERSION: str = "2024-02-01"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"

    # Rate limiting
    DEFAULT_RATE_LIMIT_RPM: int = 60

    # Token budgets
    DEFAULT_TOKEN_BUDGET_MONTHLY: int = 1_000_000

    # Caching
    CACHE_TTL_SECONDS: int = 3600
    CACHE_ENABLED: bool = True

    # Audit
    AUDIT_LOG_REQUEST_BODY: bool = True
    AUDIT_LOG_RESPONSE_BODY: bool = True
    AUDIT_BODY_TRUNCATE_CHARS: int = 500

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # Admin
    ADMIN_API_KEY: str = "admin-secret-change-me"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
