"""
MailMind AI - Base Abstract Service Definitions.

Architectural Decision Rationale:
---------------------------------
1. Dependency Inversion Principle (DIP): High-level modules (e.g. ConversationService or API endpoints)
   should depend on abstract interfaces rather than concrete third-party vendor SDK implementations.
2. Provider Independence (BaseSTTService): Establishes a formal interface for Speech-To-Text services.
   Swapping between providers (e.g., Groq Whisper, OpenAI Whisper, Deepgram, Azure Speech, Local Faster-Whisper)
   requires zero changes to the application core or WebSocket router layer.
3. Asynchronous Execution (`async`): Voice AI pipelines process streaming audio buffers. Async methods prevent
   blocking the main thread loop during high-latency I/O (network calls to LLMs or STT APIs).
"""

from abc import ABC, abstractmethod
from typing import Any


class BaseService(ABC):
    """
    Abstract Base Class for all core backend services.
    Enforces standard initialization and health lifecycle contracts.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """
        Asynchronously initialize service resources, models, or network connections.
        """

    @abstractmethod
    async def is_ready(self) -> bool:
        """
        Check whether the service is fully operational and ready to process requests.
        """


class BaseSTTService(BaseService, ABC):
    """
    Abstract Base Class for all Speech-To-Text (STT) provider implementations.
    Enforces standard transcription and lifecycle interfaces across all provider adapters.
    """

    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> dict[str, Any]:
        """
        Asynchronously transcribes raw PCM audio bytes into text.

        :param audio_bytes: Raw 16-bit 16000Hz mono PCM binary audio data.
        :param language: ISO language code (default "en").
        :return: Dict containing transcript text, metadata, and processing timing.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verifies API credentials and provider endpoint reachability.
        """

    @abstractmethod
    async def shutdown(self) -> None:
        """
        Gracefully releases network clients and resources.
        """
