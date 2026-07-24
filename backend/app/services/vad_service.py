"""
MailMind AI - Voice Activity Detection (VAD) Service.

Responsibility & Architectural Role:
------------------------------------
- Single Responsibility: Analyzes raw PCM audio frames to detect human speech boundaries and manage the VAD state machine.
- Clean Architecture: Operates purely on binary PCM frames and VADSessionState data models.
  Zero coupling to FastAPI, WebSockets, ConnectionManager, STT, LLM, or TTS.

Architectural Decision Rationale:
---------------------------------
1. Deterministic State Machine: Implements strict state transitions:
   IDLE -> VOICE_STARTED -> VOICE_ACTIVE -> SILENCE_DETECTED -> UTTERANCE_COMPLETE -> RESET.
   Prevents premature utterance truncation and eliminates false-positive noise triggers.
2. Root Mean Square (RMS) Signal Analysis: Computes normalized RMS energy amplitude on 16-bit PCM samples.
   Provides fast, reliable, zero-C-dependency voice energy detection suitable for real-time streaming.
3. Structured Transition Logging: Emits a structured log payload whenever a VAD state change or event occurs:
   [Session ID | Previous State | Current State | Speech Duration (ms) | Silence Duration (ms) | UTC Timestamp]
"""

import math
import struct
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.models.vad_state import VADEvent, VADSessionState, VADState
from app.services.base import BaseService

logger = get_logger("services.vad_service")


class VADService(BaseService):
    """
    Asynchronous service managing Voice Activity Detection (VAD) processing,
    signal energy evaluation, and utterance boundary detection.
    """

    def __init__(self) -> None:
        self._is_initialized: bool = False

    async def initialize(self) -> None:
        """Initialize VAD Service configurations."""
        logger.info("Initializing VADService engine...")
        self._is_initialized = True

    async def is_ready(self) -> bool:
        """Check operational readiness status."""
        return self._is_initialized

    def calculate_pcm_rms(self, pcm_bytes: bytes) -> float:
        """
        Calculates normalized Root Mean Square (RMS) signal energy amplitude for 16-bit PCM Little-Endian samples.

        :param pcm_bytes: Raw 16-bit PCM audio bytes.
        :return: Normalized RMS energy value between 0.0 and 1.0.
        """
        if not pcm_bytes or len(pcm_bytes) < 2:
            return 0.0

        # Truncate incomplete 2-byte sample boundary if necessary
        sample_count = len(pcm_bytes) // 2
        if sample_count == 0:
            return 0.0

        # Unpack 16-bit signed integers (h = short, Little Endian)
        fmt = f"<{sample_count}h"
        try:
            samples = struct.unpack(fmt, pcm_bytes[: sample_count * 2])
        except struct.error:
            return 0.0

        # Calculate sum of squared normalized samples (16-bit max = 32768.0)
        sum_squares = sum((sample / 32768.0) ** 2 for sample in samples)
        mean_square = sum_squares / sample_count
        return math.sqrt(mean_square)

    def is_voice_detected(
        self, frame_bytes: bytes, threshold: float | None = None
    ) -> bool:
        """
        Determines whether an audio frame contains human voice activity by comparing
        normalized RMS energy against a threshold.

        :param frame_bytes: Raw PCM audio bytes.
        :param threshold: Energy threshold float (defaults to settings.VAD_ENERGY_THRESHOLD).
        :return: True if voice activity is detected, False otherwise.
        """
        target_threshold = threshold if threshold is not None else settings.VAD_ENERGY_THRESHOLD
        rms_energy = self.calculate_pcm_rms(frame_bytes)
        return rms_energy >= target_threshold

    def calculate_frame_duration_ms(
        self,
        frame_bytes: bytes,
        sample_rate: int = settings.VAD_SAMPLE_RATE,
        bytes_per_sample: int = settings.VAD_BYTES_PER_SAMPLE,
        channels: int = settings.VAD_CHANNELS,
    ) -> float:
        """
        Calculates the temporal duration of an audio frame chunk in milliseconds.

        :param frame_bytes: Raw audio frame bytes.
        :param sample_rate: Sample rate in Hz (default 16000).
        :param bytes_per_sample: Bytes per sample (default 2 for 16-bit).
        :param channels: Channel count (default 1 for mono).
        :return: Frame duration in milliseconds.
        """
        bytes_per_sec = sample_rate * bytes_per_sample * channels
        if bytes_per_sec <= 0:
            return 0.0
        return (len(frame_bytes) / bytes_per_sec) * 1000.0

    def process_audio_frame(
        self,
        frame_bytes: bytes,
        vad_state: VADSessionState,
        session_id: str = "default",
    ) -> tuple[VADState, VADEvent | None, dict[str, Any]]:
        """
        Processes a raw PCM audio frame, updates timing metrics, advances the VAD state machine,
        logs transitions, and returns the updated state, emitted event, and metadata.

        :param frame_bytes: Raw binary PCM frame chunk.
        :param vad_state: Per-session VADSessionState model instance.
        :param session_id: Active session identifier for logging.
        :return: Tuple of (new_state, emitted_event, metadata_dict).
        """
        frame_duration_ms = self.calculate_frame_duration_ms(frame_bytes)
        has_voice = self.is_voice_detected(frame_bytes)

        previous_state = vad_state.state
        event: VADEvent | None = None
        now_ts = datetime.now(timezone.utc).timestamp()

        # Update last voice/silence timestamps
        if has_voice:
            vad_state.last_voice_timestamp = now_ts
        else:
            vad_state.last_silence_timestamp = now_ts

        # Finite State Machine Logic
        if vad_state.state in [VADState.IDLE, VADState.RESET]:
            if has_voice:
                vad_state.speech_duration_ms += frame_duration_ms
                vad_state.silence_duration_ms = 0.0
                if vad_state.speech_duration_ms >= settings.VAD_MIN_SPEECH_DURATION_MS:
                    vad_state.speech_started = True
                    vad_state.transition_to(VADState.VOICE_STARTED)
                    event = VADEvent.VOICE_STARTED
            else:
                vad_state.speech_duration_ms = 0.0
                vad_state.silence_duration_ms += frame_duration_ms

        elif vad_state.state == VADState.VOICE_STARTED:
            if has_voice:
                vad_state.speech_duration_ms += frame_duration_ms
                vad_state.silence_duration_ms = 0.0
                vad_state.transition_to(VADState.VOICE_ACTIVE)
                event = VADEvent.VOICE_CONTINUING
            else:
                vad_state.silence_duration_ms += frame_duration_ms
                vad_state.transition_to(VADState.SILENCE_DETECTED)
                event = VADEvent.VOICE_STOPPED

        elif vad_state.state == VADState.VOICE_ACTIVE:
            if has_voice:
                vad_state.speech_duration_ms += frame_duration_ms
                vad_state.silence_duration_ms = 0.0
                event = VADEvent.VOICE_CONTINUING
            else:
                vad_state.silence_duration_ms += frame_duration_ms
                vad_state.transition_to(VADState.SILENCE_DETECTED)
                event = VADEvent.VOICE_STOPPED

        elif vad_state.state == VADState.SILENCE_DETECTED:
            if has_voice:
                vad_state.speech_duration_ms += frame_duration_ms
                vad_state.silence_duration_ms = 0.0
                vad_state.transition_to(VADState.VOICE_ACTIVE)
                event = VADEvent.VOICE_CONTINUING
            else:
                vad_state.silence_duration_ms += frame_duration_ms
                # Check for Utterance Complete Conditions
                if (
                    vad_state.silence_duration_ms >= settings.VAD_SILENCE_THRESHOLD_MS
                    or vad_state.speech_duration_ms >= settings.VAD_MAX_UTTERANCE_DURATION_MS
                ):
                    vad_state.transition_to(VADState.UTTERANCE_COMPLETE)
                    event = VADEvent.UTTERANCE_COMPLETED

        elif vad_state.state == VADState.UTTERANCE_COMPLETE:
            # Utterance complete, awaiting downstream STT consumption or explicit reset
            pass

        # Log state transition or significant events
        if previous_state != vad_state.state or event in [VADEvent.VOICE_STARTED, VADEvent.UTTERANCE_COMPLETED]:
            logger.info(
                f"VAD Transition | Session ID: {session_id} | "
                f"Prev State: {previous_state.value} -> Current State: {vad_state.state.value} | "
                f"Event: {event.value if event else 'NONE'} | "
                f"Speech Duration: {vad_state.speech_duration_ms:.1f}ms | "
                f"Silence Duration: {vad_state.silence_duration_ms:.1f}ms | "
                f"Timestamp: {datetime.now(timezone.utc).isoformat()}"
            )

        metadata = {
            "has_voice": has_voice,
            "previous_state": previous_state.value,
            "current_state": vad_state.state.value,
            "event": event.value if event else None,
            "speech_duration_ms": round(vad_state.speech_duration_ms, 2),
            "silence_duration_ms": round(vad_state.silence_duration_ms, 2),
            "ready_for_transcription": vad_state.ready_for_transcription,
        }

        return vad_state.state, event, metadata

    def has_utterance_completed(self, vad_state: VADSessionState) -> bool:
        """
        Returns True if the session has a completed speech utterance ready for transcription.

        :param vad_state: Per-session VADSessionState instance.
        :return: True if ready for transcription, False otherwise.
        """
        return vad_state.ready_for_transcription

    def reset(self, vad_state: VADSessionState) -> None:
        """
        Resets session VAD state machine and timing metrics back to IDLE.

        :param vad_state: Per-session VADSessionState instance.
        """
        vad_state.reset_session_vad()


# Global singleton instance of VADService
vad_service = VADService()
