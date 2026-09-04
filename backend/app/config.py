from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path

# Resolve .env from project root regardless of working directory
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    database_url: str          # asyncpg — used by FastAPI at runtime
    database_sync_url: str     # psycopg2 — used by Alembic CLI
    groq_api_key: str
    embedding_model: str = "all-MiniLM-L6-v2"
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    frontend_origin: str = "http://localhost:5173"
    # Organizer login — env-driven so no credential lives in source
    organizer_username: str = "organizer"
    organizer_password: str = ""
    # Autonomous-loop scheduler (Phase 1.5 hardening)
    scheduler_enabled: bool = True
    sweep_interval_minutes: int = 5
    reminder_interval_minutes: int = 5
    mentor_timeout_interval_minutes: int = 2
    resource_overdue_interval_minutes: int = 10

    class Config:
        env_file = str(_ENV_FILE)
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
