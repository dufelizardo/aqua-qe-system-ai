"""
utils/config.py
Single source of truth for all configuration.
Reads from .env file and environment variables.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # AI Provider
    AI_PROVIDER:   str = "anthropic"
    AI_MODEL:      str = "claude-sonnet-4-20250514"
    AI_API_KEY:    str = ""
    AI_BASE_URL:   str | None = None   # corporate proxy endpoint
    BASE_URL:      str | None = None   # alias — used when AI_BASE_URL not set

    # FastAPI
    APP_ENV:    str = "development"
    APP_HOST:   str = "0.0.0.0"
    APP_PORT:   int = 8000
    APP_RELOAD: bool = True

    # Orchestrator
    ENGINE_MAX_TOKENS:   int   = 8000
    ENGINE_TIMEOUT:      float = 120.0
    ENGINE_CONCURRENCY:  int   = 5
    ENGINE_LANGUAGE:     str   = "portuguese"

    # Database
    DB_PATH: str = "qa_system.db"

    @property
    def effective_base_url(self) -> str | None:
        """Returns AI_BASE_URL if set, otherwise BASE_URL."""
        return self.AI_BASE_URL or self.BASE_URL

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# Convenience singleton
settings = get_settings()
