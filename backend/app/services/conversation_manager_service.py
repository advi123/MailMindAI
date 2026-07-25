"""
MailMind AI - Conversation Manager Service.

Architectural Decision Rationale:
---------------------------------
1. Single Responsibility: Manages transcript validation, string normalization, turn counter tracking,
   and memory delegation. Knows nothing about LLMs or prompt formatting.
2. Robust String Normalization: Strips leading/trailing whitespace, converts multiple spaces or linebreaks
   into single spaces, and rejects invalid or empty speech inputs.
3. Clean Dependency Injection: Receives `ConversationMemoryService` via dependency injection.
"""

import re

from app.core.logging import get_logger
from app.models.conversation_models import ConversationSession, ConversationTurn
from app.services.base import BaseService
from app.services.conversation_memory import (
    ConversationMemoryService,
    conversation_memory_service,
)

logger = get_logger("services.conversation_manager")


class ConversationManager(BaseService):
    """
    Business service responsible for validating, normalizing, and storing STT transcripts into session memory.
    """

    def __init__(self, memory_service: ConversationMemoryService) -> None:
        self.memory_service: ConversationMemoryService = memory_service
        self._is_initialized: bool = False

    async def initialize(self) -> None:
        """Initialize ConversationManager service."""
        logger.info("Initializing ConversationManager service...")
        await self.memory_service.initialize()
        self._is_initialized = True
        logger.info("ConversationManager service initialized successfully.")

    async def is_ready(self) -> bool:
        """Check operational readiness status."""
        return self._is_initialized and await self.memory_service.is_ready()

    def normalize_transcript(self, raw_transcript: str) -> str:
        """
        Validates and normalizes raw transcript string:
        - Collapses duplicate spaces, newlines, and tabs into a single space.
        - Strips leading and trailing whitespace.

        :param raw_transcript: Raw input transcript text string.
        :return: Normalized string.
        """
        if not raw_transcript:
            return ""

        # Replace all whitespace sequences (spaces, tabs, newlines) with a single space
        normalized = re.sub(r"\s+", " ", raw_transcript).strip()
        return normalized

    def process_user_transcript(
        self, session_id: str, transcript_text: str
    ) -> tuple[ConversationSession, ConversationTurn | None]:
        """
        Validates raw transcript, normalizes whitespace, and records a user turn if valid.

        :param session_id: Target session ID.
        :param transcript_text: Raw STT transcript text string.
        :return: Tuple of (ConversationSession, ConversationTurn | None).
        """
        normalized_text = self.normalize_transcript(transcript_text)
        session = self.memory_service.get_or_create_session(session_id)

        if not normalized_text:
            logger.warning(
                f"Transcript Ignored | Session ID: {session_id} | Reason: Empty or whitespace-only string"
            )
            return session, None

        turn = self.memory_service.append_user_message(session_id, normalized_text)
        logger.info(
            f"Transcript Processed | Session ID: {session_id} | Turn #: {turn.turn_number} | "
            f"Normalized Text: '{normalized_text}'"
        )
        return session, turn


# Global singleton instance for application lifespan DI
conversation_manager = ConversationManager(memory_service=conversation_memory_service)
