"""
MailMind AI - Base Abstract Service Definition.

Architectural Decision Rationale:
---------------------------------
1. Dependency Inversion Principle (DIP): High-level modules (e.g. ConversationService or API endpoints)
   should depend on abstract interfaces rather than concrete third-party vendor SDK implementations.
2. Swappable Implementations: Abstract base classes enforce a strict contract. In future phases, swapping
   between local models (e.g., Whisper, Silero VAD, Ollama) and cloud providers (e.g. Deepgram, ElevenLabs, OpenAI)
   will require zero changes to the orchestration or web API layer.
3. Asynchronous Execution (`async`): Voice AI pipelines process streaming audio buffers. Async methods prevent
   blocking the main thread loop during high-latency I/O (network calls to LLMs or TTS APIs).
"""

from abc import ABC, abstractmethod


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
