"""
Providers Package - Speech-To-Text Provider Strategies & Factory.

Contains concrete provider adapters and factory registration:
- BaseSTTProvider interface (base_provider.py)
- GroqSTTProvider strategy (groq_stt.py)
- STTProviderFactory registry (factory.py)
"""

from app.services.providers.base_provider import BaseSTTProvider
from app.services.providers.factory import STTProviderFactory
from app.services.providers.groq_stt import GroqSTTProvider, pcm_to_wav

__all__ = [
    "BaseSTTProvider",
    "GroqSTTProvider",
    "STTProviderFactory",
    "pcm_to_wav",
]
