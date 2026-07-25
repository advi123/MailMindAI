"""
MailMind AI - Conversation Intelligence Domain Models.

Architectural Decision Rationale:
---------------------------------
1. Strongly Typed Domain Models: Uses Pydantic BaseModel to enforce strict schemas, type validation,
   and serialization for turn history, metadata telemetry, and session state.
2. Immutability & Traceability: Every `ConversationTurn` contains an assigned turn number, role type,
   UTC timestamp, and content string for complete auditability.
3. Clean Separation of Session State & Telemetry: `ConversationMetadata` isolates aggregate stats
   (total user messages, total AI responses, language) from turn history.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ConversationRole(str, Enum):
    """
    Role enumerations for conversation turns.
    """

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConversationTurn(BaseModel):
    """
    Represents a single turn in a multi-turn conversation.
    """

    role: ConversationRole = Field(..., description="Role of the speaker (user, assistant, system)")
    content: str = Field(..., min_length=1, description="Text content of the conversation turn")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the turn was created",
    )
    turn_number: int = Field(..., ge=1, description="Sequential 1-based turn number within the session")


class ConversationMetadata(BaseModel):
    """
    Session telemetry and metadata tracking aggregate session stats.
    """

    total_user_messages: int = Field(default=0, ge=0, description="Total count of user turns")
    total_ai_messages: int = Field(default=0, ge=0, description="Total count of assistant turns")
    last_activity: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of most recent activity in session",
    )
    language: str = Field(default="en", description="ISO language code for the session")
    extra: dict[str, Any] = Field(
        default_factory=dict,
        description="Extensibility container for future tool calls, RAG, and memory attributes",
    )


class ConversationSession(BaseModel):
    """
    Domain model representing an active conversation session bound to a WebSocket connection.
    """

    session_id: str = Field(..., description="Unique WebSocket session identifier")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of session creation",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of last session update",
    )
    conversation_history: list[ConversationTurn] = Field(
        default_factory=list,
        description="Ordered list of historical conversation turns",
    )
    turn_counter: int = Field(default=0, ge=0, description="Monotonically increasing turn counter")
    metadata: ConversationMetadata = Field(
        default_factory=ConversationMetadata,
        description="Session telemetry and language metadata",
    )
