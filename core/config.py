from functools import lru_cache
from typing import List, Optional, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    BOT_TOKEN: str
    ADMIN_IDS: Union[List[int], str] = Field(default_factory=list)

    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5433
    POSTGRES_DB: str = "olx_monitor"
    DB_ECHO: bool = False

    PROXY_URL: Optional[str] = None

    IGNORE_BUMPED_OFFERS: bool = False
    IGNORE_PROMOTED_OFFERS: bool = False
    MAX_OFFER_AGE_MINUTES: int = 30
    BATCH_OUTPUT_LIMIT: int = 12
    MAX_PER_CATEGORY_PER_BATCH: int = 2

    MAX_CONCURRENT_CHECKS: int = 5
    POLL_INTERVAL_SECONDS: int = 60
    POLL_JITTER_SECONDS: int = 5
    REQUEST_TIMEOUT: int = 15
    CURL_IMPERSONATE: str = "chrome120"
    LOG_LEVEL: str = "INFO"

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, value: Union[str, List[int]]) -> List[int]:
        if isinstance(value, str):
            if not value.strip():
                return []
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [int(item) for item in value]
        return []

    @field_validator("PROXY_URL", mode="before")
    @classmethod
    def parse_proxy_url(cls, value: Optional[str]) -> Optional[str]:
        if isinstance(value, str):
            cleaned: str = value.strip()
            if not cleaned or cleaned.lower() in {"none", "null", "false", ""}:
                return None
            return cleaned
        return None

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()