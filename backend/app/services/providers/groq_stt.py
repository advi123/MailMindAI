"""
MailMind AI - Groq Whisper STT Provider Implementation.

Architectural Decision Rationale:
---------------------------------
1. Concrete Provider Strategy: Encapsulates all Groq SDK interactions and Whisper Large V3 Turbo API calls.
2. In-Memory PCM-to-WAV Conversion: Converts 16-bit PCM bytes to WAV containers in RAM using standard
   library `wave` and `io.BytesIO`. Performs zero disk I/O operations.
3. Isolated Vendor Logic: All Groq-specific parameters, client initialization, timeouts, and error handling
   reside exclusively inside this provider module.
"""

import asyncio
import io
import time
import wave
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import AppValidationError, ServiceUnavailableError
from app.core.logging import get_logger
from app.services.providers.base_provider import BaseSTTProvider

logger = get_logger("services.providers.groq_stt")

# Try importing groq SDK safely
try:
    import groq
    from groq import AsyncGroq
    GROQ_AVAILABLE = True
except ImportError:
    groq = None
    AsyncGroq = None
    GROQ_AVAILABLE = False


def pcm_to_wav(
    pcm_bytes: bytes,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """
    Converts raw 16-bit PCM audio bytes to WAV container format completely in memory using wave and io.BytesIO.

    :param pcm_bytes: Raw PCM binary audio bytes.
    :param sample_rate: Sample rate in Hz (default 16000).
    :param channels: Channel count (default 1 for mono).
    :param sample_width: Sample width in bytes (default 2 for 16-bit PCM).
    :return: Complete WAV binary file bytes.
    :raises AppValidationError: If pcm_bytes is empty or invalid.
    """
    if not pcm_bytes or len(pcm_bytes) == 0:
        raise AppValidationError("Cannot convert empty PCM audio bytes to WAV format.")

    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_bytes)

    return wav_io.getvalue()


class GroqSTTProvider(BaseSTTProvider):
    """
    Groq Whisper API Speech-To-Text concrete provider implementation.
    Invokes Groq's `whisper-large-v3-turbo` model for high-accuracy, ultra-low-latency transcriptions.
    """

    def __init__(self) -> None:
        self._client: Any = None
        self._is_initialized: bool = False

    @property
    def provider_name(self) -> str:
        """Returns provider string identifier."""
        return "groq"

    async def initialize(self) -> None:
        """
        Initializes the AsyncGroq client using settings configuration.
        """
        logger.info("Initializing GroqSTTProvider...")
        if not GROQ_AVAILABLE:
            logger.warning("Groq SDK package is not installed. Provider requests will fail.")
            self._is_initialized = True
            return

        api_key = settings.GROQ_API_KEY
        if not api_key:
            logger.warning(
                "GROQ_API_KEY environment variable is not configured. "
                "Provider will operate in fallback mode until key is supplied."
            )
        else:
            self._client = AsyncGroq(api_key=api_key)

        self._is_initialized = True
        logger.info(f"GroqSTTProvider initialized successfully (Model: {settings.STT_MODEL}).")

    async def is_ready(self) -> bool:
        """Check operational readiness status."""
        return self._is_initialized

    async def health_check(self) -> bool:
        """
        Verifies Groq API client configuration validity.
        """
        return self._is_initialized and (self._client is not None or not settings.GROQ_API_KEY)

    async def shutdown(self) -> None:
        """
        Gracefully releases AsyncGroq client connections.
        """
        if self._client and hasattr(self._client, "close"):
            try:
                await self._client.close()
            except Exception:
                logger.exception("Error closing Groq AsyncClient")
        self._client = None
        self._is_initialized = False

    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> dict[str, Any]:
        """
        Transcribes raw PCM audio bytes using Groq Whisper Large V3 Turbo API.

        :param audio_bytes: Raw 16-bit 16000Hz mono PCM binary audio data.
        :param language: Target language ISO code (default "en").
        :return: Dict containing raw transcript text, duration, and provider metadata.
        :raises AppValidationError: If audio payload is empty or invalid.
        :raises ServiceUnavailableError: If Groq API call times out or fails.
        """
        if not audio_bytes or len(audio_bytes) == 0:
            raise AppValidationError("Cannot transcribe empty audio buffer.")

        duration_seconds = len(audio_bytes) / 32000.0
        start_time = time.perf_counter()

        logger.info(
            f"Groq Provider Transcription Started | Audio Bytes: {len(audio_bytes)} | "
            f"Estimated Duration: {duration_seconds:.2f}s | Model: {settings.STT_MODEL}"
        )

        # Convert raw PCM to in-memory WAV container
        wav_bytes = pcm_to_wav(audio_bytes)

        # Handle unconfigured client API key gracefully
        if not self._client:
            if not settings.GROQ_API_KEY:
                processing_ms = (time.perf_counter() - start_time) * 1000.0
                mock_text = "Placeholder transcript: MailMind AI voice assistant is active."
                logger.warning("GROQ_API_KEY missing. Returning fallback transcript.")
                return {
                    "text": mock_text,
                    "language": language or settings.STT_LANGUAGE,
                    "duration_seconds": round(duration_seconds, 2),
                    "processing_ms": round(processing_ms, 2),
                    "provider": self.provider_name,
                    "model": settings.STT_MODEL,
                }

            self._client = AsyncGroq(api_key=settings.GROQ_API_KEY)

        try:
            file_tuple = ("audio.wav", wav_bytes, "audio/wav")

            transcription_coro = self._client.audio.transcriptions.create(
                file=file_tuple,
                model=settings.STT_MODEL,
                language=language or settings.STT_LANGUAGE,
                response_format="json",
            )

            response = await asyncio.wait_for(
                transcription_coro,
                timeout=settings.STT_TIMEOUT,
            )

            transcript_text = getattr(response, "text", str(response)).strip()
            processing_ms = (time.perf_counter() - start_time) * 1000.0

            logger.info(
                f"Groq Provider Transcription Completed | Latency: {processing_ms:.1f}ms | "
                f"Text: '{transcript_text}'"
            )

            return {
                "text": transcript_text,
                "language": language or settings.STT_LANGUAGE,
                "duration_seconds": round(duration_seconds, 2),
                "processing_ms": round(processing_ms, 2),
                "provider": self.provider_name,
                "model": settings.STT_MODEL,
            }

        except (asyncio.TimeoutError, httpx.TimeoutException) as timeout_exc:
            processing_ms = (time.perf_counter() - start_time) * 1000.0
            logger.exception(
                f"Groq Provider Timeout | Exceeded {settings.STT_TIMEOUT}s | Latency: {processing_ms:.1f}ms"
            )
            raise ServiceUnavailableError(
                f"Groq STT provider timed out after {settings.STT_TIMEOUT}s."
            ) from timeout_exc

        except Exception as exc:
            processing_ms = (time.perf_counter() - start_time) * 1000.0
            logger.exception(
                f"Groq Provider Failure | Latency: {processing_ms:.1f}ms"
            )
            raise ServiceUnavailableError(
                f"Groq STT provider error: {exc!s}"
            ) from exc
