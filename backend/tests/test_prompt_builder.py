"""
Unit test suite for PromptBuilder service prompt formatting, system prompt overrides, and safety truncation.
"""

import pytest

from app.models.conversation_models import ConversationRole, ConversationTurn
from app.services.prompt_builder import PromptBuilder


@pytest.mark.asyncio
async def test_prompt_builder_basic_formatting():
    """
    Tests basic prompt formatting with default system prompt and user message.
    """
    builder = PromptBuilder()
    await builder.initialize()

    prompt = builder.build_prompt(current_user_message="Schedule a sync with Sarah.")

    assert "=== SYSTEM MESSAGE ===" in prompt
    assert "MailMind AI" in prompt
    assert "=== CURRENT USER MESSAGE ===" in prompt
    assert "User: Schedule a sync with Sarah." in prompt


@pytest.mark.asyncio
async def test_prompt_builder_history_ordering():
    """
    Tests history formatting and turn ordering.
    """
    builder = PromptBuilder()
    await builder.initialize()

    history = [
        ConversationTurn(role=ConversationRole.USER, content="Show unread emails", turn_number=1),
        ConversationTurn(role=ConversationRole.ASSISTANT, content="You have 2 unread emails.", turn_number=2),
    ]

    prompt = builder.build_prompt(
        history=history,
        current_user_message="Summarize the first one.",
    )

    assert "=== CONVERSATION HISTORY ===" in prompt
    assert "User: Show unread emails" in prompt
    assert "Assistant: You have 2 unread emails." in prompt
    assert "User: Summarize the first one." in prompt


@pytest.mark.asyncio
async def test_prompt_builder_extensibility_contexts():
    """
    Tests prompt assembly with memory, RAG, and tools placeholders (Milestones 8-10 extension points).
    """
    builder = PromptBuilder()
    await builder.initialize()

    prompt = builder.build_prompt(
        current_user_message="Draft reply",
        memory_context="User prefers formal tone.",
        rag_context="Email Subject: Q3 Budget Review",
        tools_context="tool_send_email()",
    )

    assert "=== PERSONAL MEMORY CONTEXT ===" in prompt
    assert "User prefers formal tone." in prompt
    assert "=== EMAIL KNOWLEDGE CONTEXT ===" in prompt
    assert "Email Subject: Q3 Budget Review" in prompt
    assert "=== AVAILABLE TOOLS ===" in prompt
    assert "tool_send_email()" in prompt


@pytest.mark.asyncio
async def test_prompt_builder_empty_history_handling():
    """
    Tests prompt building when history is empty or None.
    """
    builder = PromptBuilder()
    await builder.initialize()

    prompt = builder.build_prompt(history=[], current_user_message="Hello MailMind")
    assert "=== CONVERSATION HISTORY ===" not in prompt
    assert "User: Hello MailMind" in prompt
