"""
MailMind AI - Session Audio Buffer Model.

Architectural Decision Rationale:
---------------------------------
1. Dedicated Session Isolation: Every connected voice session owns an independent AudioBuffer.
   This guarantees strict memory isolation and eliminates cross-session data leakage in concurrent environments.
2. Raw Byte Accumulation: Audio frames are appended directly as immutable `bytes` chunks without CPU-heavy
   decoding, resampling, or format conversion. This keeps stream ingestion ultra-fast and lightweight.
3. Memory Overflow & DoS Protection: Includes configurable `max_buffer_bytes` threshold (default 10 MB).
   Prevents memory exhaustion attacks by raising a controlled validation error if a client sends excessive audio.
"""


from app.core.exceptions import AppValidationError
from app.core.logging import get_logger

logger = get_logger("models.audio_buffer")

# Default PCM Audio Specs for Duration Estimation (16kHz, 16-bit Mono = 32,000 bytes/sec)
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_BYTES_PER_SAMPLE = 2
DEFAULT_CHANNELS = 1
DEFAULT_MAX_BUFFER_BYTES = 10 * 1024 * 1024  # 10 MB Maximum Buffer Size


class AudioBuffer:
    """
    In-memory raw audio frame buffer dedicated to a single WebSocket voice session.
    Accumulates raw binary chunks and computes byte/frame metrics.
    """

    def __init__(self, max_buffer_bytes: int = DEFAULT_MAX_BUFFER_BYTES) -> None:
        self._frames: list[bytes] = []
        self._total_bytes: int = 0
        self._frame_count: int = 0
        self.max_buffer_bytes: int = max_buffer_bytes

    @property
    def total_bytes(self) -> int:
        """Total accumulated byte size of all stored audio frames."""
        return self._total_bytes

    @property
    def frame_count(self) -> int:
        """Total number of binary audio frames appended to this buffer."""
        return self._frame_count

    def duration_estimate(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        bytes_per_sample: int = DEFAULT_BYTES_PER_SAMPLE,
        channels: int = DEFAULT_CHANNELS,
    ) -> float:
        """
        Calculates estimated audio duration in seconds based on accumulated byte size.

        Formula: total_bytes / (sample_rate * bytes_per_sample * channels)
        Default (16kHz 16-bit Mono): 32,000 bytes = 1.0 second of audio.
        """
        bytes_per_second = sample_rate * bytes_per_sample * channels
        if bytes_per_second <= 0:
            return 0.0
        return round(self._total_bytes / bytes_per_second, 3)

    def append_frame(self, frame: bytes) -> bool:
        """
        Appends a raw binary audio frame chunk to the session buffer.

        :param frame: Raw binary bytes chunk.
        :return: True if frame appended successfully.
        :raises AppValidationError: If frame is empty, not bytes, or exceeds max buffer capacity.
        """
        if not isinstance(frame, (bytes, bytearray)):
            raise AppValidationError("Audio frame must be raw binary bytes.")

        frame_len = len(frame)
        if frame_len == 0:
            raise AppValidationError("Cannot append empty audio frame (0 bytes).")

        if self._total_bytes + frame_len > self.max_buffer_bytes:
            logger.warning(
                f"Buffer overflow limit reached: {self._total_bytes + frame_len} > {self.max_buffer_bytes} bytes."
            )
            raise AppValidationError(
                f"Audio buffer capacity exceeded ({self.max_buffer_bytes} bytes limit)."
            )

        self._frames.append(bytes(frame))
        self._total_bytes += frame_len
        self._frame_count += 1
        return True

    def clear(self) -> None:
        """Clears all stored audio frame chunks and resets metrics to 0."""
        self._frames.clear()
        self._total_bytes = 0
        self._frame_count = 0

    def export_raw(self) -> bytes:
        """
        Concatenates and returns the complete buffered raw binary audio data.

        :return: Contiguous raw bytes object containing all appended audio frames.
        """
        return b"".join(self._frames)
