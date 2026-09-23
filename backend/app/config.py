"""Environment-sourced settings, shared by the app, Alembic, and readiness checks.

Single source of truth for connection strings — nothing here is a repository,
service, or provider; it's config, read once at process startup.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://civicpulse:civicpulse@postgres:5432/civicpulse"
    redis_url: str = "redis://redis:6379/0"
    gemini_api_key: str = ""
    rate_limit_max: int = 10
    rate_limit_window_seconds: int = 60


settings = Settings()
