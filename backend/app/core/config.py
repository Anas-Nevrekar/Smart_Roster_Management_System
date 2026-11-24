from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic import AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Smart Roster Management API"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    environment: Literal["development", "testing", "production"] = "development"
    debug: bool = False
    allowed_frontend_origins: list[str] = ["http://localhost:5173"]
    storage_backend: Literal["mongodb", "memory"] = Field(
        default="mongodb", validation_alias=AliasChoices("STORAGE_BACKEND", "SMART_ROSTER_STORAGE_BACKEND"),
    )
    mongodb_uri: str | None = Field(default=None, validation_alias=AliasChoices("MONGODB_URI", "SMART_ROSTER_MONGODB_URI"))
    mongodb_database: str = Field(default="smart_roster_dev", validation_alias=AliasChoices("MONGODB_DATABASE", "SMART_ROSTER_MONGODB_DATABASE"))
    model_config = SettingsConfigDict(env_file=".env", env_prefix="SMART_ROSTER_", extra="ignore")

    @field_validator("allowed_frontend_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
