"""
Unit test suite for STTService orchestrator and strategy dependency injection.
"""

from typing import Any

import pytest

from app.services.base import BaseSTTService
from app.services.providers import BaseSTTProvider
from app.services.stt_service import STTService


class MockTestProvider(BaseSTTProvider):
    """Mock concrete STT provider strategy for unit testing."""

    def __init__(self, should_fail: bool = False) -> None:
        self._should_fail = should_fail
        self._is_initialized = False

    @property
    def provider_name(self) -> str:
        return "mock_test_provider"

    async def initialize(self) -> None:
        self._is_initialized = True

    async def is_ready(self) -> bool:
        return self._is_initialized

    async def health_check(self) -> bool:
        return self._is_initialized

    async def shutdown(self) -> None:
        self._is_initialized = False

    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> dict[str, Any]:
        if self._should_fail:
            raise RuntimeError("Mock provider simulated timeout failure")
        return {
            "text": "Review draft response for quarterly budget.",
            "language": language,
            "duration_seconds": 1.0,
            "processing_ms": 120.0,
            "provider": self.provider_name,
        }


@pytest.mark.asyncio
async def test_stt_service_contract_and_di():
    """
    Verifies STTService conforms to BaseSTTService and accepts injected providers.
    """
    mock_provider = MockTestProvider()
    service = STTService(provider=mock_provider)
    assert isinstance(service, BaseSTTService)
    assert service.provider.provider_name == "mock_test_provider"

    await service.initialize()
    assert await service.is_ready() is True


@pytest.mark.asyncio
async def test_stt_service_transcribe_success_schema():
    """
    Tests that STTService returns a standardized success dictionary payload.
    """
    mock_provider = MockTestProvider()
    service = STTService(provider=mock_provider)
    await service.initialize()

    sample_pcm = b"\x01\x00" * 16000  # 1s audio
    result = await service.transcribe(sample_pcm, language="en")

    assert result["success"] is True
    assert result["text"] == "Review draft response for quarterly budget."
    assert result["provider"] == "mock_test_provider"
    assert result["word_count"] == 6
    assert result["language"] == "en"
    assert "processing_ms" in result
    assert "model" in result


@pytest.mark.asyncio
async def test_stt_service_transcribe_failure_masking():
    """
    Tests that STTService catches provider exceptions and returns a standardized failure payload
    without raising exceptions to the caller.
    """
    failing_provider = MockTestProvider(should_fail=True)
    service = STTService(provider=failing_provider)
    await service.initialize()

    sample_pcm = b"\x01\x00" * 16000
    result = await service.transcribe(sample_pcm)

    assert result["success"] is False
    assert result["provider"] == "mock_test_provider"
    assert "Mock provider simulated timeout failure" in result["error"]
    assert "processing_ms" in result


@pytest.mark.asyncio
async def test_stt_service_empty_audio_rejection_payload():
    """
    Tests that empty audio bytes return a standardized failure payload.
    """
    mock_provider = MockTestProvider()
    service = STTService(provider=mock_provider)
    await service.initialize()

    result = await service.transcribe(b"")

    assert result["success"] is False
    assert "empty audio" in result["error"].lower()
