"""
MailMind AI - WebSocket Connection Manager.

Responsibility & Architectural Role:
------------------------------------
- Single Responsibility: Thread-safe, asynchronous lifecycle management for active WebSocket connections.
- Clean Architecture: Decouples socket management (accepting sockets, connection tracking, broadcast, disconnect, metrics)
  from HTTP/WebSocket path controllers.

Architectural Decision Rationale:
---------------------------------
1. Centralized Connection Registry: Maintains in-memory map of `session_id -> (WebSocket, VoiceSession)`.
   Enables fast lookup, connection count tracking, targeted message delivery, and global broadcast.
2. Graceful Resource Cleanup: Ensures socket disconnects clean up session state, mark session as DISCONNECTED,
   and log total active connection duration for analytics.
3. Heartbeat & Activity Tracking: Updates session `last_activity` on every incoming frame to detect stale or dropped connections.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, status

from app.core.logging import get_logger
from app.models.voice_session import SessionStatus, VoiceSession
from app.services.base import BaseService

logger = get_logger("services.connection_manager")


class ConnectionManager(BaseService):
    """
    Asynchronous connection manager responsible for accepting, tracking, messaging,
    and closing WebSocket client sessions.
    """

    def __init__(self) -> None:
        # Internal registry: session_id -> (WebSocket instance, VoiceSession metadata model)
        self._active_connections: dict[str, tuple[WebSocket, VoiceSession]] = {}
        self._is_initialized: bool = False

    async def initialize(self) -> None:
        """Initialize connection manager resources."""
        logger.info("Initializing ConnectionManager...")
        self._active_connections.clear()
        self._is_initialized = True

    async def is_ready(self) -> bool:
        """Check connection manager operational status."""
        return self._is_initialized

    @property
    def active_count(self) -> int:
        """Returns the current number of active connected clients."""
        return len(self._active_connections)

    async def connect(self, websocket: WebSocket) -> VoiceSession:
        """
        Accepts an inbound WebSocket connection, assigns a unique session ID,
        instantiates a VoiceSession model, and registers it in the active registry.

        :param websocket: FastAPI WebSocket connection instance.
        :return: Initialized VoiceSession model.
        """
        await websocket.accept()
        session = VoiceSession()

        self._active_connections[session.session_id] = (websocket, session)

        logger.info(
            f"Client connected | Session ID: {session.session_id} | "
            f"Active connections: {self.active_count}"
        )
        return session

    async def disconnect(self, session_id: str) -> VoiceSession | None:
        """
        Safely disconnects a client session, cleans up resources, marks session as
        DISCONNECTED, logs duration metrics, and removes it from active registry.

        :param session_id: Session identifier to disconnect.
        :return: Updated VoiceSession model, or None if session was not found.
        """
        if session_id not in self._active_connections:
            logger.warning(f"Disconnect attempted for unknown session ID: {session_id}")
            return None

        websocket, session = self._active_connections.pop(session_id)
        session.close()

        duration = session.duration_seconds
        logger.info(
            f"Client disconnected | Session ID: {session_id} | "
            f"Session duration: {duration:.2f}s | Active connections: {self.active_count}"
        )

        try:
            await websocket.close(code=status.WS_1000_NORMAL_CLOSURE)
        except RuntimeError:
            logger.debug("WebSocket already closed.")

        return session

    async def send_json(self, session_id: str, message: dict[str, Any]) -> bool:
        """
        Sends a JSON payload to a specific connected client session.

        :param session_id: Target session identifier.
        :param message: Dict payload to serialize and send as JSON.
        :return: True if sent successfully, False otherwise.
        """
        if session_id not in self._active_connections:
            logger.warning(f"Send failed. Session ID not active: {session_id}")
            return False

        websocket, session = self._active_connections[session_id]
        try:
            await websocket.send_json(message)
            session.touch()
            return True
        except Exception:
            logger.exception(
                f"Connection error sending message to session ID {session_id}"
            )
            await self.disconnect(session_id)
            return False

    async def broadcast(self, message: dict[str, Any]) -> None:
        """
        Broadcasts a JSON payload to all currently active connected clients.

        :param message: Dict payload to broadcast.
        """
        logger.info(f"Broadcasting message to {self.active_count} active sessions.")
        disconnected_sessions: list[str] = []

        for session_id, (websocket, session) in list(self._active_connections.items()):
            try:
                await websocket.send_json(message)
                session.touch()
            except RuntimeError:
                logger.exception(
                    f"Broadcast failed for session ID {session_id}"
                )
                disconnected_sessions.append(session_id)

        for session_id in disconnected_sessions:
            await self.disconnect(session_id)

    async def handle_heartbeat(self, session_id: str) -> dict[str, Any]:
        """
        Updates session activity timestamp and returns a standardized heartbeat acknowledgement payload.

        :param session_id: Target session identifier.
        :return: JSON-serializable heartbeat acknowledgment dict.
        """
        session = self.get_session(session_id)
        if session:
            session.touch()

        return {
            "type": "heartbeat_ack",
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_session(self, session_id: str) -> VoiceSession | None:
        """Retrieves VoiceSession metadata model for an active session ID."""
        if session_id in self._active_connections:
            return self._active_connections[session_id][1]
        return None

    async def cleanup_stale_connections(self, max_idle_seconds: int = 60) -> list[str]:
        """
        Scans active connections and disconnects any session exceeding max_idle_seconds of inactivity.

        :param max_idle_seconds: Max allowed idle duration in seconds before declaring connection stale.
        :return: List of stale session IDs that were disconnected.
        """
        now = datetime.now(timezone.utc)
        stale_sessions: list[str] = []

        for session_id, (_, session) in list(self._active_connections.items()):
            idle_seconds = (now - session.last_activity).total_seconds()
            if idle_seconds > max_idle_seconds:
                logger.warning(
                    f"Session ID {session_id} is stale (idle for {idle_seconds:.1f}s). Disconnecting."
                )
                session.connection_status = SessionStatus.STALE
                stale_sessions.append(session_id)

        for session_id in stale_sessions:
            await self.disconnect(session_id)

        return stale_sessions


# Global singleton ConnectionManager instance
connection_manager = ConnectionManager()
