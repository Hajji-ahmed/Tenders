from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["dev", "test", "staging", "prod"] = "dev"
    secret_key: str = Field(min_length=32)
    database_url: str = "postgresql+psycopg://tender:tender@localhost:5432/tender"
    redis_url: str = "redis://localhost:6379/0"

    storage_backend: Literal["s3", "local"] = "s3"
    storage_endpoint: str = "http://localhost:9000"
    storage_bucket: str = "tender-ai"
    storage_access_key: str = ""
    storage_secret_key: str = ""
    storage_local_dir: str = "./data/storage"

    openai_api_key: str = ""
    openai_model_fast: str = "gpt-4.1-mini"
    openai_model_strong: str = "gpt-4.1"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    tavily_api_key: str = ""
    resend_api_key: str = ""
    notification_email: str = ""
    sentry_dsn: str = ""

    access_token_minutes: int = 60 * 12
    cookie_secure: bool = False
    max_upload_mb: int = 50
    relevance_threshold: int = 70
    celery_task_always_eager: bool = False

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
