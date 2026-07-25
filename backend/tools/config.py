"""
MailMind AI Developer CLI Voice Client - Configuration Dataclass.

Architectural Decision Rationale:
---------------------------------
1. Centralized Dataclass Configuration: Encapsulates all audio capture specs, WebSocket URLs, reconnection
   delays, and timeout settings into an immutable typed dataclass.
2. 16-bit PCM Audio Calculations: Automatically computes exact chunk size in samples (800) and raw binary
   bytes (1600) for 50ms audio frames at 16000Hz mono.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class VoiceClientConfig:
    """
    Configuration settings for the MailMind AI Developer Voice Client.
    """

    server_url: str = "ws://localhost:8000/ws/voice"
    sample_rate: int = 16000
    channels: int = 1
    chunk_duration_ms: int = 50
    reconnect_delay: float = 2.0
    timeout: float = 30.0
    log_level: str = "INFO"
    device_index: int | None = field(default=None)

    @property
    def chunk_size_samples(self) -> int:
        """
        Calculates the sample count per 50ms frame.
        At 16000Hz, 50ms = 800 samples.
        """
        return int(self.sample_rate * (self.chunk_duration_ms / 1000.0))

    @property
    def chunk_size_bytes(self) -> int:
        """
        Calculates the raw PCM byte size per 50ms frame (16-bit = 2 bytes/sample).
        At 16000Hz mono 16-bit, 800 samples = 1600 bytes.
        """
        return self.chunk_size_samples * 2
