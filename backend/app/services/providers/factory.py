"""
MailMind AI - STT Provider Factory.

Architectural Decision Rationale:
---------------------------------
1. Factory Pattern: Encapsulates provider instantiation logic based on configuration settings (`STT_PROVIDER`).
2. Open/Closed Principle (OCP): New STT providers (e.g. OpenAI, Deepgram, Azure, Faster-Whisper) register
   themselves in `_providers`. Adding a new provider requires ZERO changes to existing routers or endpoints.
3. Decoupled Dynamic Instantiation: High-level services call `STTProviderFactory.create_provider()` without
   hardcoding vendor class names or importing vendor SDKs directly.
"""

from typing import ClassVar

from app.core.config import settings
from app.core.exceptions import AppValidationError
from app.core.logging import get_logger
from app.services.providers.base_provider import BaseSTTProvider
from app.services.providers.groq_stt import GroqSTTProvider

logger = get_logger("services.providers.factory")


class STTProviderFactory:
    """
    Factory responsible for registering and instantiating STT provider strategies.
    """

    # Internal registry mapping string IDs to concrete BaseSTTProvider classes
    _providers: ClassVar[dict[str, type[BaseSTTProvider]]] = {
        "groq": GroqSTTProvider,
    }

    @classmethod
    def register_provider(cls, name: str, provider_cls: type[BaseSTTProvider]) -> None:
        """
        Registers a new STT provider strategy class dynamically.

        :param name: String provider identifier (e.g. 'openai', 'deepgram').
        :param provider_cls: Concrete subclass of BaseSTTProvider.
        """
        key = name.lower().strip()
        cls._providers[key] = provider_cls
        logger.info(f"Registered STT Provider strategy: '{key}' ({provider_cls.__name__}).")

    @classmethod
    def create_provider(cls, provider_name: str | None = None) -> BaseSTTProvider:
        """
        Creates and returns an instance of the configured or specified STT provider.

        :param provider_name: Optional provider string ID. Defaults to settings.STT_PROVIDER if None.
        :return: Instantiated concrete BaseSTTProvider object.
        :raises AppValidationError: If the requested provider_name is not registered.
        """
        target_name = (provider_name or settings.STT_PROVIDER).lower().strip()

        if target_name not in cls._providers:
            registered_keys = list(cls._providers.keys())
            logger.error(
                f"Unknown STT provider requested: '{target_name}'. Available providers: {registered_keys}"
            )
            raise AppValidationError(
                f"Unknown STT provider '{target_name}'. Supported providers: {registered_keys}"
            )

        provider_cls = cls._providers[target_name]
        logger.info(f"STTProviderFactory creating provider instance for: '{target_name}'.")
        return provider_cls()
