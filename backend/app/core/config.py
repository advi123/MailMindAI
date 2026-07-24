"""
MailMind AI - Core Configuration Management.

Architectural Decision Rationale:
---------------------------------
1. Single Source of Truth: Configuration parameters are centralized here using Pydantic's BaseSettings.
   This prevents scattered environment variable lookups across the codebase.
2. Type Safety & Validation: Pydantic validates data types (strings, ints, lists) at startup.
   If an environment variable is invalid, the application fails fast before accepting traffic.
3. 12-Factor App Compliance: All configuration can be overridden via environment variables or `.env` files,
   making deployment seamless across dev, staging, and production environments.
"""


import json

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application Settings model reading from environment variables and `.env` file.
    Follows Clean Architecture by isolating environment concerns from domain logic.
    """

    # Application Metadata
    APP_NAME: str = "MailMind AI Backend"
    APP_VERSION: str = "0.1.0"
    ENV: str = "development"
    DEBUG: bool = True

    # HTTP Server Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Structured Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # Options: "json", "text"

    # Security & CORS Configuration
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """
        Parses JSON array strings or comma-separated lists from environment variables
        into a valid Python list of origins.
        """
        if isinstance(v, str) and v.startswith("["):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [i.strip() for i in v.split(",") if i.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


# Singleton settings instance initialized once per process
settings = Settings()
