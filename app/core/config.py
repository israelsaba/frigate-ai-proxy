import logging
from typing import Literal

from pydantic import AliasChoices, Field, HttpUrl, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.logging import setup_logging


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        secrets_dir="/run/secrets",
        extra="ignore",
    )

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        validation_alias=AliasChoices("FRIGATE_PROXY_LOG_LEVEL", "HELPERS_LOG_LEVEL", "LOG_LEVEL"),
    )

    MAX_OUTPUT_TOKENS: int = Field(
        default=600,
        validation_alias=AliasChoices(
            "FRIGATE_PROXY_MAX_OUTPUT_TOKENS", "HELPERS_STD_MAX_OUTPUT_TOKENS"
        ),
    )
    MAX_SAMPLED_IMAGES: int = Field(
        default=20,
        validation_alias=AliasChoices("FRIGATE_PROXY_MAX_SAMPLED_IMAGES", "MAX_SAMPLED_IMAGES"),
    )

    ELORIAN_BASE_URL: HttpUrl = Field(
        default=HttpUrl("https://api.elorian.ai/v1"),
        validation_alias=AliasChoices(
            "FRIGATE_PROXY_VLM_BASE_URL",
            "FRIGATE_PROXY_UPSTREAM_BASE_URL",
            "FRIGATE_PROXY_ELORIAN_BASE_URL",
            "UPSTREAM_VLM_BASE_URL",
            "VLM_BASE_URL",
            "OPENAI_BASE_URL",
            "HELPERS_ELORIAN_BASE_URL",
        ),
    )
    ELORIAN_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices(
            "FRIGATE_PROXY_VLM_API_KEY",
            "FRIGATE_PROXY_UPSTREAM_API_KEY",
            "FRIGATE_PROXY_ELORIAN_API_KEY",
            "UPSTREAM_VLM_API_KEY",
            "VLM_API_KEY",
            "OPENAI_API_KEY",
            "HELPERS_ELORIAN_API_KEY",
            "ELORIAN_API_KEY",
        ),
    )
    ELORIAN_MODEL: str = Field(
        default="glimpse",
        validation_alias=AliasChoices(
            "FRIGATE_PROXY_VLM_MODEL",
            "FRIGATE_PROXY_UPSTREAM_MODEL",
            "FRIGATE_PROXY_ELORIAN_MODEL",
            "UPSTREAM_VLM_MODEL",
            "VLM_MODEL",
            "OPENAI_MODEL",
            "HELPERS_ELORIAN_MODEL",
        ),
    )

    ENABLE_TYPESAFE_THREAT_SCORING: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "FRIGATE_PROXY_ENABLE_THREAT_SCORING",
            "FRIGATE_PROXY_ENABLE_TYPESAFE_THREAT_SCORING",
            "ENABLE_THREAT_SCORING",
            "ENABLE_TYPESAFE_THREAT_SCORING",
        ),
    )
    TYPESAFE_BASE_URL: HttpUrl = Field(
        default=HttpUrl("https://api.typesafe.ai/v1"),
        validation_alias=AliasChoices(
            "FRIGATE_PROXY_THREAT_SCORING_BASE_URL",
            "FRIGATE_PROXY_TYPESAFE_BASE_URL",
            "THREAT_SCORING_BASE_URL",
            "HELPERS_TYPESAFE_BASE_URL",
        ),
    )
    TYPESAFE_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices(
            "FRIGATE_PROXY_THREAT_SCORING_API_KEY",
            "FRIGATE_PROXY_TYPESAFE_API_KEY",
            "THREAT_SCORING_API_KEY",
            "HELPERS_TYPESAFE_API_KEY",
            "TYPESAFE_API_KEY",
        ),
    )
    TYPESAFE_MODEL: str = Field(
        default="jev-latest",
        validation_alias=AliasChoices(
            "FRIGATE_PROXY_THREAT_SCORING_MODEL",
            "FRIGATE_PROXY_TYPESAFE_MODEL",
            "THREAT_SCORING_MODEL",
            "HELPERS_TYPESAFE_MODEL",
        ),
    )

    SYSTEM_PROMPT_PREFIX: str = Field(
        default="",
        validation_alias=AliasChoices("FRIGATE_PROXY_SYSTEM_PROMPT_PREFIX", "SYSTEM_PROMPT_PREFIX"),
    )

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
