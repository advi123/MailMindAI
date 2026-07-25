"""
Unit test suite for ConversationService high-level engine orchestration.
"""

import pytest

from app.services.conversation_manager_service import ConversationManager
from app.services.conversation_memory import ConversationMemoryService
from app.services.conversation_service import ConversationService
from app.services.prompt_builder import PromptBuilder


@pytest.mark.asyncio
async def test_conversation_service_orchestration_flow():
    """
    Tests ConversationService process_transcript orchestration flow:
    1. Validates and appends user message to memory.
    2. Builds LLM prompt.
    3. Returns standardized conversation_ready result dictionary.
    """
    memory = ConversationMemoryService()
    await memory.initialize()
    manager = ConversationManager(memory_service=memory)
    builder = PromptBuilder()

    service = ConversationService(
        conversation_manager=manager,
        memory_service=memory,
        prompt_builder=builder,
    )
    await service.initialize()

    result = await service.process_transcript("sess_svc_01", "Summarize email from Sarah")

    assert result["success"] is True
    assert result["session_id"] == "sess_svc_01"
    assert result["turn_number"] == 1
    assert result["history_length"] == 1
    assert result["latest_user_message"] == "Summarize email from Sarah"
    assert "=== SYSTEM MESSAGE ===" in result["prompt"]
    assert "User: Summarize email from Sarah" in result["prompt"]
    assert "timestamp" in result


@pytest.mark.asyncio
async def test_conversation_service_multi_turn_history():
    """
    Tests multi-turn history accumulation in ConversationService.
    """
    memory = ConversationMemoryService()
    await memory.initialize()
    manager = ConversationManager(memory_service=memory)
    builder = PromptBuilder()

    service = ConversationService(
        conversation_manager=manager,
        memory_service=memory,
        prompt_builder=builder,
    )
    await service.initialize()

    res1 = await service.process_transcript("sess_svc_02", "Turn 1: Hello MailMind")
    assert res1["turn_number"] == 1
    assert res1["history_length"] == 1

    # Simulate assistant turn response (as LLM provider will do in Milestone 7)
    memory.append_assistant_message("sess_svc_02", "Hello! How can I assist with your emails?")

    res2 = await service.process_transcript("sess_svc_02", "Turn 2: Show my meetings today")
    assert res2["turn_number"] == 3  # Turn 1 (user) + Turn 2 (assistant) + Turn 3 (user)
    assert res2["history_length"] == 3
    assert "User: Turn 1: Hello MailMind" in res2["prompt"]
    assert "Assistant: Hello! How can I assist with your emails?" in res2["prompt"]
    assert "User: Turn 2: Show my meetings today" in res2["prompt"]
