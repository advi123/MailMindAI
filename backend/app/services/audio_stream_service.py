"""
MailMind AI - Audio Stream Service.

Responsibility & Architectural Role:
------------------------------------
- Single Responsibility: Validates binary WebSocket audio packets, appends packets to the session's
  AudioBuffer, emits structured log entries per frame, and constructs acknowledgment (ACK) response payloads.
- Clean Architecture: Decouples binary streaming network protocols from memory storage and metrics aggregation.

Architectural Decision Rationale:
---------------------------------
1. Zero Media Processing Overhead: In Milestone 3, AudioStreamService acts strictly as a byte stream gateway.
   It refrains from performing noise reduction, resampling, or speech decoding, maintaining low CPU usage.
2. Structured Frame Logging: Emits a structured log payload for every ingested frame:
   [Session ID | Frame # | Frame Size | Total Bytes | Estimated Duration | UTC Timestamp]
"""

from datetime import datetime, timezone
from typing import Any

from app.core.exceptions import AppValidationError
from app.core.logging import get_logger
from app.models.audio_buffer import AudioBuffer
from app.services.base import BaseService

logger = get_logger("services.audio_stream_service")

# Maximum allowed size for a single binary audio packet (1 MB safety limit)
MAX_SINGLE_FRAME_BYTES = 1 * 1024 * 1024


class AudioStreamService(BaseService):
    """
    Asynchronous service responsible for ingesting, validating, and recording
    raw binary audio WebSocket stream packets.
    """

    def __init__(self) -> None:
        self._is_initialized = False

    async def initialize(self) -> None:
        """Initialize AudioStreamService resources."""
        logger.info("Initializing AudioStreamService...")
        self._is_initialized = True

    async def is_ready(self) -> bool:
        """Check operational readiness status."""
        return self._is_initialized

    def process_audio_frame(
        self,
        session_id: str,
        frame_bytes: bytes,
        session_buffer: AudioBuffer,
    ) -> dict[str, Any]:
        """
        Validates, logs, and stores an incoming binary audio packet into the session's AudioBuffer.

        :param session_id: Active session identifier.
        :param frame_bytes: Inbound raw binary bytes chunk.
        :param session_buffer: Session's dedicated AudioBuffer instance.
        :return: JSON-serializable frame acknowledgment dict payload.
        :raises AppValidationError: If frame is invalid, empty, or exceeds single frame capacity.
        """
        if not frame_bytes or not isinstance(frame_bytes, (bytes, bytearray)):
            raise AppValidationError(
                "Invalid binary audio frame: payload must be non-empty bytes."
            )

        frame_size = len(frame_bytes)
        if frame_size > MAX_SINGLE_FRAME_BYTES:
            raise AppValidationError(
                f"Single audio frame exceeds maximum allowed size ({frame_size} > {MAX_SINGLE_FRAME_BYTES} bytes)."
            )

        # Append frame to session memory buffer
        session_buffer.append_frame(frame_bytes)

        frame_number = session_buffer.frame_count
        accumulated_bytes = session_buffer.total_bytes
        duration_estimate = session_buffer.duration_estimate()
        now_timestamp = datetime.now(timezone.utc).isoformat()

        # Structured log entry per received audio frame
        logger.info(
            f"Audio frame ingested | Session ID: {session_id} | Frame #: {frame_number} | "
            f"Frame Size: {frame_size} bytes | Total Bytes: {accumulated_bytes} bytes | "
            f"Duration Est: {duration_estimate:.3f}s | Timestamp: {now_timestamp}"
        )

        return {
            "type": "audio_ack",
            "session_id": session_id,
            "frame_number": frame_number,
            "frame_bytes": frame_size,
            "total_bytes": accumulated_bytes,
            "duration_estimate": duration_estimate,
            "timestamp": now_timestamp,
        }


# Global singleton instance of AudioStreamService
audio_stream_service = AudioStreamService()
