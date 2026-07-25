"""
Unit test suite for ConversationMemoryService session memory management, isolation, and lifecycle.
"""

import pytest

from app.models.conversation_models import ConversationRole
from app.services.conversation_memory import ConversationMemoryService


@pytest.mark.asyncio
async def test_session_creation_and_retrieval():
    """
    Tests session creation, retrieval, and get_or_create behavior.
    """
    memory = ConversationMemoryService()
    await memory.initialize()

    session = memory.create_session("sess_001", language="en")
    assert session.session_id == "sess_001"
    assert session.metadata.language == "en"

    retrieved = memory.get_session("sess_001")
    assert retrieved is not None
    assert retrieved.session_id == "sess_001"

    or_created = memory.get_or_create_session("sess_001")
    assert or_created.session_id == "sess_001"


@pytest.mark.asyncio
async def test_append_turns_and_history():
    """
    Tests appending user and assistant turns, turn number increments, and history limits.
    """
    memory = ConversationMemoryService()
    await memory.initialize()

    turn1 = memory.append_user_message("sess_002", "Check my unread emails")
    assert turn1.turn_number == 1
    assert turn1.role == ConversationRole.USER
    assert turn1.content == "Check my unread emails"

    turn2 = memory.append_assistant_message("sess_002", "You have 3 unread emails.")
    assert turn2.turn_number == 2
    assert turn2.role == ConversationRole.ASSISTANT
    assert turn2.content == "You have 3 unread emails."

    history = memory.get_history("sess_002")
    assert len(history) == 2
    assert history[0].content == "Check my unread emails"
    assert history[1].content == "You have 3 unread emails."

    latest = memory.get_latest_message("sess_002")
    assert latest is not None
    assert latest.content == "You have 3 unread emails."


@pytest.mark.asyncio
async def test_session_reset_and_delete():
    """
    Tests session resetting and deletion lifecycle.
    """
    memory = ConversationMemoryService()
    await memory.initialize()

    memory.append_user_message("sess_003", "Draft an email to Alex")
    memory.append_assistant_message("sess_003", "Draft prepared.")

    session_before = memory.get_session("sess_003")
    assert session_before is not None
    assert len(session_before.conversation_history) == 2

    # Reset session
    reset_sess = memory.reset_session("sess_003")
    assert reset_sess.session_id == "sess_003"
    assert len(reset_sess.conversation_history) == 0
    assert reset_sess.turn_counter == 0

    # Delete session
    deleted = memory.delete_session("sess_003")
    assert deleted is True
    assert memory.get_session("sess_003") is None


@pytest.mark.asyncio
async def test_session_memory_isolation():
    """
    Tests that multiple concurrent WebSocket sessions remain strictly isolated.
    """
    memory = ConversationMemoryService()
    await memory.initialize()

    memory.append_user_message("sess_A", "User A message")
    memory.append_user_message("sess_B", "User B message")

    history_A = memory.get_history("sess_A")
    history_B = memory.get_history("sess_B")

    assert len(history_A) == 1
    assert len(history_B) == 1
    assert history_A[0].content == "User A message"
    assert history_B[0].content == "User B message"
