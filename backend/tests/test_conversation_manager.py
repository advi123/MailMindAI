"""
Unit test suite for ConversationManager transcript normalization, validation, and turn recording.
"""

import pytest

from app.services.conversation_manager_service import ConversationManager
from app.services.conversation_memory import ConversationMemoryService


@pytest.mark.asyncio
async def test_transcript_whitespace_normalization():
    """
    Tests collapsing extra spaces, newlines, and tabs into a single clean space.
    """
    memory = ConversationMemoryService()
    await memory.initialize()
    manager = ConversationManager(memory_service=memory)
    await manager.initialize()

    raw_input = "   Schedule   a meeting \n\n with   John\ttomorrow.   "
    normalized = manager.normalize_transcript(raw_input)

    assert normalized == "Schedule a meeting with John tomorrow."


@pytest.mark.asyncio
async def test_process_valid_transcript():
    """
    Tests processing valid user transcript string into session memory.
    """
    memory = ConversationMemoryService()
    await memory.initialize()
    manager = ConversationManager(memory_service=memory)
    await manager.initialize()

    session, turn = manager.process_user_transcript("sess_mgr_01", "  Check my inbox. ")

    assert session.session_id == "sess_mgr_01"
    assert turn is not None
    assert turn.turn_number == 1
    assert turn.content == "Check my inbox."
    assert session.turn_counter == 1


@pytest.mark.asyncio
async def test_process_empty_or_whitespace_transcript():
    """
    Tests that empty or whitespace-only transcripts are ignored without incrementing turn counter.
    """
    memory = ConversationMemoryService()
    await memory.initialize()
    manager = ConversationManager(memory_service=memory)
    await manager.initialize()

    session, turn = manager.process_user_transcript("sess_mgr_02", "   \n\t  ")

    assert session.session_id == "sess_mgr_02"
    assert turn is None
    assert session.turn_counter == 0
    assert len(session.conversation_history) == 0
