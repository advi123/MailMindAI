"""
Services Package - Core Business Logic Layer (Clean Architecture).

Contains interface definitions and implementations for:
- Connection Manager (connection_manager.py)
- Audio Stream Ingestion Service (audio_stream_service.py)
- Voice Activity Detection Engine (vad_service.py)
- Speech-To-Text Provider Engine & Strategy Layer (stt_service.py, providers/)
- Audio Processing (audio_service.py)
- Language Model Orchestration (llm_service.py)
- Text-To-Speech Synthesis (tts_service.py)
- Pipeline & Conversation Orchestration (conversation_service.py)
"""

from app.services.audio_stream_service import AudioStreamService, audio_stream_service
from app.services.base import BaseService, BaseSTTService
from app.services.connection_manager import ConnectionManager, connection_manager
from app.services.providers import (
    BaseSTTProvider,
    GroqSTTProvider,
    STTProviderFactory,
    pcm_to_wav,
)
from app.services.stt_service import STTService, stt_service
from app.services.vad_service import VADService, vad_service

__all__ = [
    "AudioStreamService",
    "BaseSTTProvider",
    "BaseSTTService",
    "BaseService",
    "ConnectionManager",
    "GroqSTTProvider",
    "STTProviderFactory",
    "STTService",
    "VADService",
    "audio_stream_service",
    "connection_manager",
    "pcm_to_wav",
    "stt_service",
    "vad_service",
]
