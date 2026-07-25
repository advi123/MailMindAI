"""
Unit test suite for Conversation Intelligence Pydantic domain models.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models.conversation_models import (
    ConversationMetadata,
    ConversationRole,
    ConversationSession,
    ConversationTurn,
)


def test_conversation_turn_model():
    """
    Tests ConversationTurn instantiation, default UTC timestamp, and validation.
    """
    now = datetime.now(timezone.utc)
    turn = ConversationTurn(
        role=ConversationRole.USER,
        content="Schedule an executive sync",
        turn_number=1,
    )

    assert turn.role == ConversationRole.USER
    assert turn.content == "Schedule an executive sync"
    assert turn.turn_number == 1
    assert isinstance(turn.timestamp, datetime)
    assert turn.timestamp >= now


def test_conversation_turn_invalid_role():
    """
    Tests that invalid role strings trigger validation errors.
    """
    with pytest.raises(ValidationError):
        ConversationTurn(
            role="invalid_role",  # type: ignore[arg-type]
            content="Hello",
            turn_number=1,
        )


def test_conversation_session_model():
    """
    Tests ConversationSession model initialization and defaults.
    """
    session = ConversationSession(
        session_id="test_session_123",
        metadata=ConversationMetadata(language="en"),
    )

    assert session.session_id == "test_session_123"
    assert session.turn_counter == 0
    assert len(session.conversation_history) == 0
    assert session.metadata.total_user_messages == 0
    assert session.metadata.total_ai_messages == 0
    assert session.metadata.language == "en"
