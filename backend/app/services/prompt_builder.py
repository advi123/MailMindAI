"""
MailMind AI - Prompt Builder Service.

Architectural Decision Rationale:
---------------------------------
1. Single Responsibility Principle (SRP): Isolates LLM prompt formatting, template assembly, and history
   truncation logic into a dedicated service. High-level orchestrators and LLM providers depend on PromptBuilder.
2. Extensibility (OCP): Provides explicit context injection parameters (`memory_context`, `rag_context`,
   `tools_context`) enabling future RAG (Milestone 9), Memory (Milestone 8), and Tool Calling (Milestone 10)
   without modifying existing prompt assembly code.
3. Safety Bounds: Truncates historical turns and total character count (`PROMPT_MAX_CHARACTERS`) to prevent
   context window overflow when invoking downstream LLMs.
"""

from app.core.config import settings
from app.core.logging import get_logger
from app.models.conversation_models import ConversationRole, ConversationTurn
from app.services.base import BaseService

logger = get_logger("services.prompt_builder")


class PromptBuilder(BaseService):
    """
    Service responsible for building structured LLM prompts from system instructions,
    historical conversation turns, and context placeholders.
    """

    def __init__(self) -> None:
        self._is_initialized: bool = False

    async def initialize(self) -> None:
        """Initialize PromptBuilder service."""
        logger.info("Initializing PromptBuilder service...")
        self._is_initialized = True
        logger.info("PromptBuilder service initialized successfully.")

    async def is_ready(self) -> bool:
        """Check operational readiness status."""
        return self._is_initialized

    def build_prompt(
        self,
        system_prompt: str | None = None,
        history: list[ConversationTurn] | None = None,
        current_user_message: str = "",
        memory_context: str | None = None,
        rag_context: str | None = None,
        tools_context: str | None = None,
    ) -> str:
        """
        Constructs a formatted, structured prompt string for LLM completion.

        :param system_prompt: Optional system prompt instructions override.
        :param history: List of historical ConversationTurn objects.
        :param current_user_message: Current user message text string.
        :param memory_context: Optional personal memory context (Milestone 8 extension point).
        :param rag_context: Optional email RAG document context (Milestone 9 extension point).
        :param tools_context: Optional tools/functions definitions (Milestone 10 extension point).
        :return: Formatted prompt text string.
        """
        effective_system_prompt = (
            system_prompt.strip()
            if system_prompt and system_prompt.strip()
            else settings.DEFAULT_SYSTEM_PROMPT
        )

        sections: list[str] = [
            "=== SYSTEM MESSAGE ===",
            effective_system_prompt,
        ]

        # Optional Memory Context Injection (Milestone 8 Extension Point)
        if memory_context and memory_context.strip():
            sections.extend([
                "",
                "=== PERSONAL MEMORY CONTEXT ===",
                memory_context.strip(),
            ])

        # Optional RAG Context Injection (Milestone 9 Extension Point)
        if rag_context and rag_context.strip():
            sections.extend([
                "",
                "=== EMAIL KNOWLEDGE CONTEXT ===",
                rag_context.strip(),
            ])

        # Optional Tools Context Injection (Milestone 10 Extension Point)
        if tools_context and tools_context.strip():
            sections.extend([
                "",
                "=== AVAILABLE TOOLS ===",
                tools_context.strip(),
            ])

        # Historical turns context (Truncated to PROMPT_MAX_HISTORY)
        if history:
            recent_turns = history[-settings.PROMPT_MAX_HISTORY:]
            sections.extend(["", "=== CONVERSATION HISTORY ==="])

            for turn in recent_turns:
                role_label = (
                    "User"
                    if turn.role == ConversationRole.USER
                    else "Assistant"
                    if turn.role == ConversationRole.ASSISTANT
                    else "System"
                )
                sections.append(f"{role_label}: {turn.content.strip()}")

        # Current User Turn
        if current_user_message and current_user_message.strip():
            sections.extend([
                "",
                "=== CURRENT USER MESSAGE ===",
                f"User: {current_user_message.strip()}",
            ])

        raw_prompt = "\n".join(sections)

        # Enforce character safety limit
        if len(raw_prompt) > settings.PROMPT_MAX_CHARACTERS:
            raw_prompt = raw_prompt[: settings.PROMPT_MAX_CHARACTERS] + "\n...[Truncated for length]"

        logger.info(
            f"Prompt Built | Character Length: {len(raw_prompt)} | "
            f"History Turns Included: {len(history) if history else 0}"
        )
        return raw_prompt


# Global singleton instance for application lifespan DI
prompt_builder = PromptBuilder()
