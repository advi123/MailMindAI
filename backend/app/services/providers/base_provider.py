"""
MailMind AI - Base STT Provider Abstract Interface.

Architectural Decision Rationale:
---------------------------------
1. Strategy Pattern: Defines an abstract strategy interface for Speech-To-Text provider adapters.
   Every concrete provider (Groq, OpenAI, Deepgram, Azure, Faster-Whisper) must implement this contract.
2. Open/Closed Principle (OCP): High-level application logic depends on BaseSTTProvider rather than
   vendor-specific SDKs. New providers can be added without altering application routers or services.
"""

from abc import ABC, abstractmethod
from typing import Any

from app.services.base import BaseService


class BaseSTTProvider(BaseService, ABC):
    """
    Abstract Base Class for Speech-To-Text (STT) concrete providers.
    Enforces standardized initialization, transcription, health check, and shutdown contracts.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Returns the unique string identifier for this provider (e.g., 'groq', 'openai', 'deepgram').
        """

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> dict[str, Any]:
        """
        Asynchronously transcribes raw 16-bit PCM audio bytes into text.

        :param audio_bytes: Raw 16-bit 16000Hz mono PCM binary audio data.
        :param language: Target language ISO code (default "en").
        :return: Dict containing raw transcript text, provider metadata, and metrics.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verifies provider credentials and API endpoint reachability.
        """

    @abstractmethod
    async def shutdown(self) -> None:
        """
        Gracefully releases provider clients and resources.
        """
