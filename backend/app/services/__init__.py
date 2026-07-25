"""
Services Package - Core Business Logic Layer (Clean Architecture).

Contains interface definitions and implementations for:
- Connection Manager (connection_manager.py)
- Audio Stream Ingestion Service (audio_stream_service.py)
- Voice Activity Detection Engine (vad_service.py)
- Speech-To-Text Provider Engine & Strategy Layer (stt_service.py, providers/)
- Conversation Memory Service (conversation_memory.py)
- Prompt Builder Service (prompt_builder.py)
- Conversation Manager Service (conversation_manager_service.py)
- Conversation Intelligence Service (conversation_service.py)
"""

from app.services.audio_stream_service import AudioStreamService, audio_stream_service
from app.services.base import BaseService, BaseSTTService
from app.services.connection_manager import ConnectionManager, connection_manager
from app.services.conversation_manager_service import (
    ConversationManager,
    conversation_manager,
)
from app.services.conversation_memory import (
    ConversationMemoryService,
    conversation_memory_service,
)
from app.services.conversation_service import ConversationService, conversation_service
from app.services.prompt_builder import PromptBuilder, prompt_builder
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
    "ConversationManager",
    "ConversationMemoryService",
    "ConversationService",
    "GroqSTTProvider",
    "PromptBuilder",
    "STTProviderFactory",
    "STTService",
    "VADService",
    "audio_stream_service",
    "connection_manager",
    "conversation_manager",
    "conversation_memory_service",
    "conversation_service",
    "pcm_to_wav",
    "prompt_builder",
    "stt_service",
    "vad_service",
]
