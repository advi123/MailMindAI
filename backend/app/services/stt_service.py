"""
MailMind AI - Speech-To-Text (STT) Service Placeholder.

Responsibility & Architectural Role:
------------------------------------
- Single Responsibility: Transcribes audio speech buffers into clean text.
- Decoupling: Converts voice input into textual data without concern for how the audio was captured or how the text will be interpreted by downstream LLMs.

Architectural Decision Rationale:
---------------------------------
1. Provider Agnosticism: Isolates transcription engines (e.g. Whisper, Deepgram, AssemblyAI) behind a standardized
   asynchronous interface (`transcribe_audio`). Switching from local Whisper to cloud STT requires zero changes to API routes.
2. Streaming & Batch Support: Interface designed to handle both complete audio files and real-time audio chunk streams.
"""

from typing import Any

from app.core.logging import get_logger
from app.services.base import BaseService

logger = get_logger("services.stt_service")


class STTService(BaseService):
    """
    Placeholder service for Speech-To-Text (STT) transcription.
    """

    def __init__(self) -> None:
        self._is_initialized = False

    async def initialize(self) -> None:
        """Initialize Speech-To-Text model client or engine."""
        logger.info("Initializing STTService placeholder...")
        self._is_initialized = True

    async def is_ready(self) -> bool:
        """Check STT service readiness status."""
        return self._is_initialized

    async def transcribe_audio(
        self, pcm_audio_bytes: bytes, language: str = "en"
    ) -> dict[str, Any]:
        """
        Placeholder interface method to transcribe audio bytes into text.

        :param pcm_audio_bytes: Audio chunk or stream bytes.
        :param language: Spoken language code (default 'en').
        :return: Transcribed text string and confidence score.
        """
        return {
            "text": "Placeholder transcription: Hello, MailMind AI.",
            "confidence": 0.98,
            "language": language,
        }
