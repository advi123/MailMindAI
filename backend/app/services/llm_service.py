"""
MailMind AI - LLM Service Placeholder.

Responsibility & Architectural Role:
------------------------------------
- Single Responsibility: Orchestrates natural language processing, prompt formatting, context management,
  and text response generation using Large Language Models (LLMs).
- Decoupling: Operates purely on text input/output, completely unaware of audio, TTS, or network transport layers.

Architectural Decision Rationale:
---------------------------------
1. Async Token Streaming: Conversational voice assistants require low latency. Returning streaming token generators
   allows Text-to-Speech (TTS) to begin synthesizing audio chunks for the first sentence while the LLM is still
   generating subsequent sentences.
2. Abstract Model Provider Interface: Hides vendor specifics (e.g. OpenAI, Anthropic, Gemini, Ollama) behind a clean API.
"""

from collections.abc import AsyncGenerator

from app.core.logging import get_logger
from app.services.base import BaseService

logger = get_logger("services.llm_service")


class LLMService(BaseService):
    """
    Placeholder service for Large Language Model (LLM) interaction and response generation.
    """

    def __init__(self) -> None:
        self._is_initialized = False

    async def initialize(self) -> None:
        """Initialize LLM model client or API connections."""
        logger.info("Initializing LLMService placeholder...")
        self._is_initialized = True

    async def is_ready(self) -> bool:
        """Check LLM service operational status."""
        return self._is_initialized

    async def generate_response(
        self, prompt: str, conversation_history: list[dict[str, str]]
    ) -> str:
        """
        Placeholder interface method for synchronous full-text LLM generation.

        :param prompt: User transcribed message or system prompt.
        :param conversation_history: Prior dialog messages list.
        :return: Generated text response string.
        """
        return f"Placeholder response to: '{prompt}'"

    async def generate_response_stream(
        self, prompt: str, conversation_history: list[dict[str, str]]
    ) -> AsyncGenerator[str, None]:
        """
        Placeholder interface method for streaming LLM text tokens asynchronously.
        """
        response_tokens = [
            "Hello! ",
            "I am ",
            "MailMind AI, ",
            "your ",
            "voice ",
            "assistant.",
        ]
        for token in response_tokens:
            yield token
