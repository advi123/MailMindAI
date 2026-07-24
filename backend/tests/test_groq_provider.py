"""
Unit test suite for GroqSTTProvider concrete strategy and in-memory PCM-to-WAV conversion.
"""

import io
import wave
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.exceptions import AppValidationError, ServiceUnavailableError
from app.services.providers import BaseSTTProvider, GroqSTTProvider, pcm_to_wav


def test_pcm_to_wav_conversion():
    """
    Tests in-memory PCM-to-WAV conversion: RIFF header, format, channels, sample rate.
    """
    sample_pcm = b"\x00\x00\x01\x00" * 8000  # 32,000 bytes = 1s 16kHz mono = 16,000 frames
    wav_bytes = pcm_to_wav(sample_pcm, sample_rate=16000, channels=1, sample_width=2)

    assert isinstance(wav_bytes, bytes)
    assert len(wav_bytes) > len(sample_pcm)
    assert wav_bytes.startswith(b"RIFF")
    assert b"WAVE" in wav_bytes
    assert b"fmt " in wav_bytes
    assert b"data" in wav_bytes

    wav_io = io.BytesIO(wav_bytes)
    with wave.open(wav_io, "rb") as wave_read:
        assert wave_read.getnchannels() == 1
        assert wave_read.getsampwidth() == 2
        assert wave_read.getframerate() == 16000
        assert wave_read.readframes(16000) == sample_pcm


def test_pcm_to_wav_empty_audio_rejection():
    """
    Tests that pcm_to_wav rejects empty PCM byte arrays.
    """
    with pytest.raises(AppValidationError):
        pcm_to_wav(b"")


@pytest.mark.asyncio
async def test_groq_stt_provider_contract():
    """
    Verifies GroqSTTProvider inherits from BaseSTTProvider interface.
    """
    provider = GroqSTTProvider()
    assert isinstance(provider, BaseSTTProvider)
    assert provider.provider_name == "groq"
    await provider.initialize()
    assert await provider.is_ready() is True


@pytest.mark.asyncio
async def test_groq_stt_provider_mocked_success():
    """
    Tests successful Groq STT provider transcription with mocked AsyncGroq client.
    """
    provider = GroqSTTProvider()
    await provider.initialize()

    mock_response = MagicMock()
    mock_response.text = "Sync executive calendar for tomorrow."

    mock_client = AsyncMock()
    mock_client.audio.transcriptions.create = AsyncMock(return_value=mock_response)
    provider._client = mock_client

    sample_pcm = b"\x01\x00" * 16000  # 1s audio
    result = await provider.transcribe(sample_pcm, language="en")

    assert result["text"] == "Sync executive calendar for tomorrow."
    assert result["provider"] == "groq"
    assert result["duration_seconds"] == 1.0
    assert "processing_ms" in result
    mock_client.audio.transcriptions.create.assert_called_once()


@pytest.mark.asyncio
async def test_groq_stt_provider_empty_audio_rejection():
    """
    Tests that empty audio bytes are rejected by provider.
    """
    provider = GroqSTTProvider()
    await provider.initialize()

    with pytest.raises(AppValidationError):
        await provider.transcribe(b"")


@pytest.mark.asyncio
async def test_groq_stt_provider_timeout_handling():
    """
    Tests that network/API timeouts raise ServiceUnavailableError.
    """
    provider = GroqSTTProvider()
    await provider.initialize()

    mock_client = AsyncMock()
    mock_client.audio.transcriptions.create = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
    provider._client = mock_client

    sample_pcm = b"\x01\x00" * 16000

    with pytest.raises(ServiceUnavailableError):
        await provider.transcribe(sample_pcm)


@pytest.mark.asyncio
async def test_groq_stt_provider_api_exception_handling():
    """
    Tests that Groq API exceptions raise ServiceUnavailableError cleanly.
    """
    provider = GroqSTTProvider()
    await provider.initialize()

    mock_client = AsyncMock()
    mock_client.audio.transcriptions.create = AsyncMock(side_effect=Exception("Groq Rate Limit"))
    provider._client = mock_client

    sample_pcm = b"\x01\x00" * 16000

    with pytest.raises(ServiceUnavailableError):
        await provider.transcribe(sample_pcm)
