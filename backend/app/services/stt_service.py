"""
MailMind AI - Speech-To-Text (STT) Orchestrator Service.

Responsibility & Architectural Role:
------------------------------------
- Single Responsibility: High-level STT orchestration service responsible for request validation,
  provider strategy delegation, latency metrics, structured telemetry logging, and standardized response formatting.
- Clean Architecture & Dependency Injection: Implements `BaseSTTService`. Accepts a `BaseSTTProvider` strategy
  via dependency injection during initialization (`STTService(provider=provider)`).
- Strategy & Factory Patterns: Delegates audio transcription to the injected `BaseSTTProvider` concrete strategy.
  Uses `STTProviderFactory` if no provider is explicitly injected.

Architectural Decision Rationale:
---------------------------------
1. Standardized Response Contract: Formats all outcomes into a predictable dictionary schema:
   - Success: `{"success": True, "text": "...", "language": "en", "processing_ms": 342, "provider": "groq", "model": "..."}`
   - Failure: `{"success": False, "provider": "groq", "error": "Timeout or Provider Error Message", "processing_ms": 30001}`
2. Resilient Error Masking: Catches provider exceptions cleanly and returns structured failure payloads,
   ensuring high-level callers and WebSockets never crash or disconnect unexpectedly.
"""

import time
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.services.base import BaseSTTService
from app.services.providers import (
    BaseSTTProvider,
    STTProviderFactory,
)

logger = get_logger("services.stt_service")


class STTService(BaseSTTService):
    """
    STT Service Orchestrator that delegates audio transcriptions to an injected BaseSTTProvider strategy.
    """

    def __init__(self, provider: BaseSTTProvider | None = None) -> None:
        self.provider: BaseSTTProvider = provider or STTProviderFactory.create_provider()
        self._is_initialized: bool = False

    async def initialize(self) -> None:
        """
        Initializes the injected STT provider strategy.
        """
        logger.info(f"Initializing STTService orchestrator with provider: '{self.provider.provider_name}'...")
        await self.provider.initialize()
        self._is_initialized = True
        logger.info("STTService orchestrator initialized successfully.")

    async def is_ready(self) -> bool:
        """Check operational readiness status of provider."""
        return self._is_initialized and await self.provider.is_ready()

    async def health_check(self) -> bool:
        """
        Verifies health of the injected provider.
        """
        return self._is_initialized and await self.provider.health_check()

    async def shutdown(self) -> None:
        """
        Shuts down the injected provider.
        """
        await self.provider.shutdown()
        self._is_initialized = False

    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> dict[str, Any]:
        """
        Orchestrates audio transcription by validating input, delegating to the provider strategy,
        measuring latency, logging telemetry, and formatting a standardized response dictionary.

        :param audio_bytes: Raw 16-bit 16000Hz mono PCM binary audio data.
        :param language: Target language ISO code (default "en").
        :return: Standardized response dict with 'success', 'text', 'processing_ms', 'provider', 'model', etc.
        """
        start_time = time.perf_counter()
        provider_name = self.provider.provider_name

        # 1. Request Validation
        if not audio_bytes or len(audio_bytes) == 0:
            processing_ms = (time.perf_counter() - start_time) * 1000.0
            logger.warning(f"Transcription Request Rejected | Empty audio bytes | Provider: {provider_name}")
            return {
                "success": False,
                "provider": provider_name,
                "error": "Cannot transcribe empty audio buffer.",
                "processing_ms": round(processing_ms, 2),
            }

        duration_seconds = len(audio_bytes) / 32000.0
        logger.info(
            f"Transcription Started | Session Provider: {provider_name} | "
            f"Audio Bytes: {len(audio_bytes)} | Estimated Duration: {duration_seconds:.2f}s | "
            f"Model: {settings.STT_MODEL}"
        )

        # 2. Delegate to Provider Strategy
        try:
            raw_result = await self.provider.transcribe(audio_bytes, language=language)
            processing_ms = (time.perf_counter() - start_time) * 1000.0

            text = raw_result.get("text", "").strip()
            word_count = len(text.split()) if text else 0
            char_count = len(text)

            logger.info(
                f"Transcription Succeeded | Provider: {provider_name} | Model: {settings.STT_MODEL} | "
                f"Latency: {processing_ms:.1f}ms | Word Count: {word_count} | Chars: {char_count} | Text: '{text}'"
            )

            return {
                "success": True,
                "text": text,
                "language": language or settings.STT_LANGUAGE,
                "processing_ms": round(processing_ms, 2),
                "provider": provider_name,
                "model": settings.STT_MODEL,
                "word_count": word_count,
            }

        except Exception as exc:
            processing_ms = (time.perf_counter() - start_time) * 1000.0
            logger.exception(
                f"Transcription Failed | Provider: {provider_name} | Latency: {processing_ms:.1f}ms"
            )
            return {
                "success": False,
                "provider": provider_name,
                "error": str(exc),
                "processing_ms": round(processing_ms, 2),
            }


# Legacy compatibility alias
GroqSTTService = STTService

# Global singleton instances initialized during application lifespan
stt_service = STTService()
groq_stt_service = stt_service
