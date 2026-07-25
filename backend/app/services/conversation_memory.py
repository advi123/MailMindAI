"""
MailMind AI - Conversation Memory Service.

Architectural Decision Rationale:
---------------------------------
1. Session Isolation: Manages an in-memory registry mapping unique `session_id` to `ConversationSession`.
   Guarantees zero cross-session leakage between concurrent WebSocket clients.
2. Abstract Storage Abstraction: Encapsulates all state mutations (creating, appending turns, resetting,
   deleting sessions). In future milestones, this service will swap internal storage to Redis without
   altering dependent business services.
3. Structured Logging & Observability: Logs lifecycle events (session creation, message appends, resets, deletions)
   with session ID, turn count, history length, and timestamps.
"""

from datetime import datetime, timezone

from app.core.config import settings
from app.core.logging import get_logger
from app.models.conversation_models import (
    ConversationMetadata,
    ConversationRole,
    ConversationSession,
    ConversationTurn,
)
from app.services.base import BaseService

logger = get_logger("services.conversation_memory")


class ConversationMemoryService(BaseService):
    """
    In-memory isolated conversation session memory storage service.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, ConversationSession] = {}
        self._is_initialized: bool = False

    async def initialize(self) -> None:
        """Initialize in-memory session registry."""
        logger.info("Initializing ConversationMemoryService...")
        self._sessions.clear()
        self._is_initialized = True
        logger.info("ConversationMemoryService initialized successfully.")

    async def is_ready(self) -> bool:
        """Check operational readiness status."""
        return self._is_initialized

    def create_session(self, session_id: str, language: str = "en") -> ConversationSession:
        """
        Creates a new isolated ConversationSession for the specified session_id.

        :param session_id: Unique WebSocket session identifier.
        :param language: ISO language code (default "en").
        :return: Created ConversationSession instance.
        """
        now = datetime.now(timezone.utc)
        session = ConversationSession(
            session_id=session_id,
            created_at=now,
            updated_at=now,
            conversation_history=[],
            turn_counter=0,
            metadata=ConversationMetadata(
                total_user_messages=0,
                total_ai_messages=0,
                last_activity=now,
                language=language or settings.DEFAULT_LANGUAGE,
            ),
        )
        self._sessions[session_id] = session
        logger.info(
            f"Conversation Session Created | Session ID: {session_id} | Language: {session.metadata.language}"
        )
        return session

    def get_session(self, session_id: str) -> ConversationSession | None:
        """
        Retrieves active ConversationSession by session_id.
        """
        return self._sessions.get(session_id)

    def get_or_create_session(self, session_id: str, language: str = "en") -> ConversationSession:
        """
        Retrieves existing session or creates a new one if absent.
        """
        session = self.get_session(session_id)
        if session is None:
            session = self.create_session(session_id, language=language)
        return session

    def delete_session(self, session_id: str) -> bool:
        """
        Deletes a session from memory registry.

        :return: True if deleted, False if session did not exist.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Conversation Session Deleted | Session ID: {session_id}")
            return True
        return False

    def reset_session(self, session_id: str) -> ConversationSession:
        """
        Resets conversation history and turn counts for an existing session while preserving session_id.
        """
        session = self.get_or_create_session(session_id)
        now = datetime.now(timezone.utc)
        session.conversation_history.clear()
        session.turn_counter = 0
        session.updated_at = now
        session.metadata.total_user_messages = 0
        session.metadata.total_ai_messages = 0
        session.metadata.last_activity = now

        logger.info(f"Conversation Session Reset | Session ID: {session_id}")
        return session

    def append_user_message(self, session_id: str, content: str) -> ConversationTurn:
        """
        Appends a user role turn to the session history.

        :param session_id: Target session ID.
        :param content: User text content string.
        :return: Created ConversationTurn instance.
        """
        session = self.get_or_create_session(session_id)
        now = datetime.now(timezone.utc)

        session.turn_counter += 1
        turn = ConversationTurn(
            role=ConversationRole.USER,
            content=content,
            timestamp=now,
            turn_number=session.turn_counter,
        )

        session.conversation_history.append(turn)
        session.metadata.total_user_messages += 1
        session.metadata.last_activity = now
        session.updated_at = now

        # Maintain max history boundary
        if len(session.conversation_history) > settings.MAX_CONVERSATION_HISTORY:
            session.conversation_history = session.conversation_history[-settings.MAX_CONVERSATION_HISTORY:]

        logger.info(
            f"User Turn Added | Session ID: {session_id} | Turn #: {turn.turn_number} | "
            f"History Length: {len(session.conversation_history)} | Text: '{content[:50]}...'"
        )
        return turn

    def append_assistant_message(self, session_id: str, content: str) -> ConversationTurn:
        """
        Appends an assistant role turn to the session history.

        :param session_id: Target session ID.
        :param content: Assistant text content string.
        :return: Created ConversationTurn instance.
        """
        session = self.get_or_create_session(session_id)
        now = datetime.now(timezone.utc)

        session.turn_counter += 1
        turn = ConversationTurn(
            role=ConversationRole.ASSISTANT,
            content=content,
            timestamp=now,
            turn_number=session.turn_counter,
        )

        session.conversation_history.append(turn)
        session.metadata.total_ai_messages += 1
        session.metadata.last_activity = now
        session.updated_at = now

        if len(session.conversation_history) > settings.MAX_CONVERSATION_HISTORY:
            session.conversation_history = session.conversation_history[-settings.MAX_CONVERSATION_HISTORY:]

        logger.info(
            f"Assistant Turn Added | Session ID: {session_id} | Turn #: {turn.turn_number} | "
            f"History Length: {len(session.conversation_history)} | Text: '{content[:50]}...'"
        )
        return turn

    def get_history(self, session_id: str, max_turns: int | None = None) -> list[ConversationTurn]:
        """
        Retrieves ordered conversation turns for the session.

        :param session_id: Target session ID.
        :param max_turns: Optional limit for recent turns.
        :return: List of ConversationTurn models.
        """
        session = self.get_session(session_id)
        if not session:
            return []

        history = session.conversation_history
        if max_turns is not None and max_turns > 0:
            return history[-max_turns:]
        return list(history)

    def get_latest_message(self, session_id: str) -> ConversationTurn | None:
        """
        Returns the most recent ConversationTurn in the session history or None.
        """
        history = self.get_history(session_id)
        return history[-1] if history else None

    def get_recent_turns(self, session_id: str, n_turns: int) -> list[ConversationTurn]:
        """
        Returns the most recent n turns.
        """
        return self.get_history(session_id, max_turns=n_turns)


# Global singleton instance for application lifespan DI
conversation_memory_service = ConversationMemoryService()
