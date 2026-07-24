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
4. Voice Activity Detection (VAD) Tuning: Centralizes VAD parameters (energy threshold, silence timeout,
   min/max speech durations) to enable fine-tuning of voice turn-taking responsiveness without code edits.
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

    # Voice Activity Detection (VAD) Configuration
    VAD_ENABLED: bool = True
    VAD_ENERGY_THRESHOLD: float = 0.015  # Normalized RMS energy threshold (0.0 to 1.0)
    VAD_SILENCE_THRESHOLD_MS: int = 800  # Silence duration (ms) to trigger UTTERANCE_COMPLETE
    VAD_MIN_SPEECH_DURATION_MS: int = 250  # Minimum speech duration (ms) to trigger VOICE_STARTED
    VAD_MAX_UTTERANCE_DURATION_MS: int = 15000  # Maximum utterance duration (ms) limit
    VAD_SAMPLE_RATE: int = 16000  # PCM sample rate in Hz
    VAD_BYTES_PER_SAMPLE: int = 2  # 16-bit PCM = 2 bytes/sample
    VAD_CHANNELS: int = 1  # Mono audio

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """
        Parses JSON array strings or comma-separated lists from environment variables
        into a valid Python list of origins.
        """
        if isinstance(v, str):
            if v.startswith("["):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    return [i.strip() for i in v.split(",") if i.strip()]

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
