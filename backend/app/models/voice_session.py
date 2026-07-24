"""
MailMind AI - Voice Session Model.

Architectural Decision Rationale:
---------------------------------
1. Session Isolation & Observability: Encapsulating socket metadata (session_id, timestamps,
   activity status, audio buffer) into a dedicated VoiceSession model decouples socket lifecycle tracking
   from WebSocket transport logic.
2. Per-Session Audio Buffer Ownership: Each VoiceSession owns exactly one independent `AudioBuffer` instance
   instantiated via `default_factory=lambda: AudioBuffer()`. Guarantees state isolation across concurrent client streams.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.audio_buffer import AudioBuffer


class SessionStatus(str, Enum):
    """Enumeration of active WebSocket connection states."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    STALE = "stale"


class VoiceSession(BaseModel):
    """
    Data model representing a client's active voice conversation session.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique identifier assigned to each active WebSocket connection",
    )
    connection_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the WebSocket connection was established",
    )
    last_activity: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the last message or heartbeat received from client",
    )
    connection_status: SessionStatus = Field(
        default=SessionStatus.CONNECTED,
        description="Current operational status of the session",
    )
    audio_buffer: AudioBuffer = Field(
        default_factory=lambda: AudioBuffer(),
        description="Dedicated raw audio memory buffer for this session",
    )

    @property
    def duration_seconds(self) -> float:
        """Calculates total active duration of the session in seconds."""
        now = datetime.now(timezone.utc)
        return (now - self.connection_time).total_seconds()

    def touch(self) -> None:
        """Updates last activity timestamp to current UTC time upon message/ping receipt."""
        self.last_activity = datetime.now(timezone.utc)

    def close(self) -> None:
        """Marks the session status as disconnected and clears session audio buffer memory."""
        self.connection_status = SessionStatus.DISCONNECTED
        self.audio_buffer.clear()

    def to_dict(self) -> dict[str, Any]:
        """Returns JSON-serializable representation of session state."""
        return {
            "session_id": self.session_id,
            "connection_time": self.connection_time.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "connection_status": self.connection_status.value,
            "duration_seconds": round(self.duration_seconds, 2),
            "buffer_metrics": {
                "total_bytes": self.audio_buffer.total_bytes,
                "frame_count": self.audio_buffer.frame_count,
                "duration_estimate": self.audio_buffer.duration_estimate(),
            },
        }
