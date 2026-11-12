import logging
from typing import Literal

from pydantic import Field, HttpUrl, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.logging import setup_logging


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FRIGATE_PROXY_",
        secrets_dir="/run/secrets",
        extra="ignore",
    )

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Token and frame bounds for cost control
    MAX_OUTPUT_TOKENS: int = 600
    MAX_SAMPLED_IMAGES: int = 20

    # Vision-Language Model provider (Elorian Glimpse or compatible)
    ELORIAN_BASE_URL: HttpUrl = HttpUrl("https://api.elorian.ai/v1")
    ELORIAN_API_KEY: str = Field(default="", min_length=0)
    ELORIAN_MODEL: str = "glimpse"

    # Threat Intelligence & Assessment (TypeSafe System 1 / Jev)
    ENABLE_TYPESAFE_THREAT_SCORING: bool = True
    TYPESAFE_BASE_URL: HttpUrl = HttpUrl("https://api.typesafe.ai/v1")
    TYPESAFE_API_KEY: str = Field(default="", min_length=0)
    TYPESAFE_MODEL: str = "jev-latest"

    # Optional prefix or guidance to prepend to inbound prompt
    SYSTEM_PROMPT_PREFIX: str = ""

    @computed_field
    @property
    def log_level_int(self) -> int:
        return getattr(logging, self.LOG_LEVEL.upper(), logging.INFO)

    @computed_field
    @property
    def elorian_chat_url(self) -> HttpUrl:
        return HttpUrl(f"{str(self.ELORIAN_BASE_URL).rstrip('/')}/chat/completions")

    @computed_field
    @property
    def typesafe_systemone_url(self) -> HttpUrl:
        return HttpUrl(f"{str(self.TYPESAFE_BASE_URL).rstrip('/')}/systemone")


settings = Settings()
setup_logging(settings.LOG_LEVEL)
