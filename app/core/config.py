from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="tsaas", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    api_prefix: str = Field(default="/api/v1", alias="API_PREFIX")

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    jobs_backend: str = Field(default="redis", alias="JOBS_BACKEND")

    models_dir: Path = Field(default=Path("storage/models"), alias="MODELS_DIR")
    metadata_dir: Path = Field(default=Path("storage/metadata"), alias="METADATA_DIR")
    cache_dir: Path = Field(default=Path("storage/cache"), alias="CACHE_DIR")

    allowed_data_hosts: str = Field(default="*", alias="ALLOWED_DATA_HOSTS")
    allowed_model_hosts: str = Field(default="*", alias="ALLOWED_MODEL_HOSTS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings and ensure storage directories exist."""
    settings = Settings()
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    settings.metadata_dir.mkdir(parents=True, exist_ok=True)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    return settings
