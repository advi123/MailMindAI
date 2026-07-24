"""
Unit test suite for STTProviderFactory registry, dynamic registration, and error handling.
"""

from typing import Any

import pytest

from app.core.exceptions import AppValidationError
from app.services.providers import BaseSTTProvider, GroqSTTProvider, STTProviderFactory


class MockCustomProvider(BaseSTTProvider):
    """Dummy custom provider strategy for testing factory registration."""

    @property
    def provider_name(self) -> str:
        return "custom"

    async def initialize(self) -> None:
        pass

    async def is_ready(self) -> bool:
        return True

    async def health_check(self) -> bool:
        return True

    async def shutdown(self) -> None:
        pass

    async def transcribe(self, audio_bytes: bytes, language: str = "en") -> dict[str, Any]:
        return {"text": "Custom provider transcript"}


def test_factory_creates_default_groq_provider():
    """
    Tests that STTProviderFactory produces GroqSTTProvider by default or when 'groq' is passed.
    """
    provider = STTProviderFactory.create_provider("groq")
    assert isinstance(provider, BaseSTTProvider)
    assert isinstance(provider, GroqSTTProvider)
    assert provider.provider_name == "groq"


def test_factory_creates_provider_from_settings():
    """
    Tests that STTProviderFactory uses settings.STT_PROVIDER if provider_name is None.
    """
    provider = STTProviderFactory.create_provider(None)
    assert isinstance(provider, BaseSTTProvider)
    assert provider.provider_name == "groq"


def test_factory_raises_validation_error_on_unknown_provider():
    """
    Tests that STTProviderFactory raises AppValidationError if an unsupported provider name is given.
    """
    with pytest.raises(AppValidationError) as exc_info:
        STTProviderFactory.create_provider("unsupported_provider_xyz")

    assert "Unknown STT provider" in str(exc_info.value)


def test_factory_dynamic_provider_registration():
    """
    Tests dynamic registration of a custom BaseSTTProvider strategy.
    """
    STTProviderFactory.register_provider("custom", MockCustomProvider)
    custom_instance = STTProviderFactory.create_provider("custom")

    assert isinstance(custom_instance, MockCustomProvider)
    assert custom_instance.provider_name == "custom"
