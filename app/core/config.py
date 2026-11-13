import logging
from typing import Literal

from pydantic import HttpUrl, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.logging import setup_logging


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        secrets_dir="/run/secrets",
        extra="ignore",
    )

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    MAX_OUTPUT_TOKENS: int = 600
    MAX_SAMPLED_IMAGES: int = 20

    UPSTREAM_VLM_BASE_URL: HttpUrl = HttpUrl("https://api.elorian.ai/v1")
    UPSTREAM_VLM_API_KEY: str = ""
    UPSTREAM_VLM_MODEL: str = "glimpse"

    UPSTREAM_THREAT_ENABLED: bool = False
    UPSTREAM_THREAT_BASE_URL: HttpUrl = HttpUrl("https://api.typesafe.ai/v1")
    UPSTREAM_THREAT_API_KEY: str = ""
    UPSTREAM_THREAT_MODEL: str = "jev-latest"

    SYSTEM_PROMPT_PREFIX: str = ""

    @computed_field
    @property
    def log_level_int(self) -> int:
        return getattr(logging, self.LOG_LEVEL.upper(), logging.INFO)

    @computed_field
    @property
    def upstream_vlm_chat_url(self) -> HttpUrl:
        return HttpUrl(f"{str(self.UPSTREAM_VLM_BASE_URL).rstrip('/')}/chat/completions")

    @computed_field
    @property
    def upstream_threat_url(self) -> HttpUrl:
        return HttpUrl(f"{str(self.UPSTREAM_THREAT_BASE_URL).rstrip('/')}/systemone")


settings = Settings()
setup_logging(settings.LOG_LEVEL)
