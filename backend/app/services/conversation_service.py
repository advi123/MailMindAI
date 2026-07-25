"""
MailMind AI - Conversation Service (Intelligence Engine Orchestrator).

Architectural Decision Rationale:
---------------------------------
1. Facade & Orchestration Layer: Coordinates `ConversationManager`, `ConversationMemoryService`, and
   `PromptBuilder` without embedding business rules directly. High-level routers depend on ConversationService.
2. Preparation for Milestone 7 (LLM Engine): Constructs and packages the structured prompt and turn state,
   making it ready for seamless injection into downstream LLM providers in Milestone 7.
3. Zero LLM Calls (Milestone 6 Contract): Performs no text generation or network calls to LLMs.
"""

from datetime import datetime, timezone
from typing import Any

from app.core.logging import get_logger
from app.services.base import BaseService
from app.services.conversation_manager_service import ConversationManager
from app.services.conversation_memory import ConversationMemoryService
from app.services.prompt_builder import PromptBuilder

logger = get_logger("services.conversation_service")


class ConversationService(BaseService):
    """
    High-level orchestrator service coordinating transcript processing, session memory,
    and structured prompt construction.
    """

    def __init__(
        self,
        conversation_manager: ConversationManager,
        memory_service: ConversationMemoryService,
        prompt_builder: PromptBuilder,
    ) -> None:
        self.conversation_manager: ConversationManager = conversation_manager
        self.memory_service: ConversationMemoryService = memory_service
        self.prompt_builder: PromptBuilder = prompt_builder
        self._is_initialized: bool = False

    async def initialize(self) -> None:
        """Initialize ConversationService dependencies."""
        logger.info("Initializing ConversationService engine...")
        await self.memory_service.initialize()
        await self.prompt_builder.initialize()
        await self.conversation_manager.initialize()
        self._is_initialized = True
        logger.info("ConversationService engine initialized successfully.")

    async def is_ready(self) -> bool:
        """Check operational readiness status."""
        return (
            self._is_initialized
            and await self.memory_service.is_ready()
            and await self.prompt_builder.is_ready()
            and await self.conversation_manager.is_ready()
        )

    async def process_transcript(
        self, session_id: str, transcript_text: str, language: str = "en"
    ) -> dict[str, Any]:
        """
        Processes an incoming STT transcript by recording the turn in memory, fetching conversation history,
        building an LLM prompt context, and returning a structured conversation payload.

        :param session_id: Target session ID.
        :param transcript_text: Raw STT transcript text string.
        :param language: ISO language code.
        :return: Dict payload containing session_id, turn_number, history_length, prompt, and latest_user_message.
        """
        now = datetime.now(timezone.utc)

        # 1. Normalize and record user turn via ConversationManager
        session, turn = self.conversation_manager.process_user_transcript(
            session_id=session_id, transcript_text=transcript_text
        )

        # 2. Retrieve history for prompt building
        history = self.memory_service.get_history(session_id)
        latest_msg = turn.content if turn else ""
        turn_num = turn.turn_number if turn else session.turn_counter

        # 3. Construct formatted LLM prompt
        built_prompt = self.prompt_builder.build_prompt(
            history=history[:-1] if turn else history,  # Exclude current turn from history block to avoid duplication
            current_user_message=latest_msg,
        )

        # 4. Calculate session duration metrics
        session_duration = (now - session.created_at).total_seconds()

        logger.info(
            f"Conversation Prepared | Session ID: {session_id} | Turn #: {turn_num} | "
            f"History Size: {len(history)} turns | Prompt Length: {len(built_prompt)} chars | "
            f"Session Duration: {session_duration:.1f}s"
        )

        return {
            "success": True,
            "session_id": session_id,
            "turn_number": turn_num,
            "history_length": len(history),
            "prompt": built_prompt,
            "latest_user_message": latest_msg,
            "timestamp": now.isoformat(),
        }


# Global singleton instances for application lifespan DI
conversation_manager = ConversationManager(memory_service=ConversationMemoryService())
conversation_service = ConversationService(
    conversation_manager=conversation_manager,
    memory_service=conversation_manager.memory_service,
    prompt_builder=PromptBuilder(),
)
