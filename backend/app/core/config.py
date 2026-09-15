from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PLACEHOLDER_SECRET_MARKERS = ("change-me", "changeme", "secret-key-test", "ci-secret-key")


class Settings(BaseSettings):
    # Le .env de la racine du dépôt est la référence ; un backend/.env local peut le surcharger.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_env: Literal["dev", "test", "staging", "prod"] = "dev"
    secret_key: str = Field(min_length=32)
    database_url: str = "postgresql+psycopg://tender:tender@127.0.0.1:5433/tender"
    redis_url: str = "redis://127.0.0.1:6379/0"

    storage_backend: Literal["s3", "local"] = "s3"
    storage_endpoint: str = "http://127.0.0.1:9000"
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
    # IP(s) autorisées à transmettre X-Forwarded-For (le relais Next.js). "*" = toutes (réseau Docker fermé).
    trusted_proxy_ips: str = "*"
    max_upload_mb: int = 50
    relevance_threshold: int = 70

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def is_deployed(self) -> bool:
        return self.app_env in ("staging", "prod")

    @model_validator(mode="after")
    def _deployed_guards(self) -> "Settings":
        """En staging/prod, refuser une configuration de développement (clé d'exemple, cookie non sûr)."""
        if not self.is_deployed:
            return self
        problems: list[str] = []
        if any(marker in self.secret_key.lower() for marker in PLACEHOLDER_SECRET_MARKERS):
            problems.append("SECRET_KEY est une valeur d'exemple (générer : openssl rand -hex 32)")
        if not self.cookie_secure:
            problems.append("COOKIE_SECURE doit valoir true (HTTPS obligatoire)")
        if self.storage_backend == "s3" and not self.storage_endpoint.startswith("https://"):
            problems.append("STORAGE_ENDPOINT doit être en https")
        if problems:
            raise ValueError(f"Configuration {self.app_env} invalide : " + " ; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
