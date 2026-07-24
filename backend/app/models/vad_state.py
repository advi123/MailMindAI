"""
MailMind AI - VAD State Machine & Session Model.

Architectural Decision Rationale:
---------------------------------
1. Deterministic State Machine: Decouples VAD state transitions (IDLE -> VOICE_STARTED -> VOICE_ACTIVE -> SILENCE_DETECTED -> UTTERANCE_COMPLETE)
   from network transport and speech inference.
2. Per-Session State Isolation: Each client connection maintains an independent VADSessionState instance.
   Guarantees zero cross-client state leakage during concurrent voice streams.
3. Event-Driven Design: Emits structured VADEvents on state changes to notify loggers and WebSocket endpoints when an utterance is ready.
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class VADState(str, Enum):
    """
    Finite state machine enumeration for Voice Activity Detection lifecycle.
    """
    IDLE = "idle"                        # No speech detected, waiting for input
    VOICE_STARTED = "voice_started"      # Initial speech detected, validating minimum speech threshold
    VOICE_ACTIVE = "voice_active"        # Sustained human voice actively detected
    SILENCE_DETECTED = "silence_detected"# Speech was active, now observing silence below energy threshold
    UTTERANCE_COMPLETE = "utterance_complete" # Silence threshold exceeded, utterance complete!
    RESET = "reset"                      # State machine reset after utterance consumption


class VADEvent(str, Enum):
    """
    VAD lifecycle events emitted during state transitions.
    """
    VOICE_STARTED = "VOICE_STARTED"
    VOICE_CONTINUING = "VOICE_CONTINUING"
    VOICE_STOPPED = "VOICE_STOPPED"
    UTTERANCE_COMPLETED = "UTTERANCE_COMPLETED"
    BUFFER_RESET = "BUFFER_RESET"


class VADSessionState(BaseModel):
    """
    Data model encapsulating the per-session Voice Activity Detection state and timing metrics.
    """
    model_config = ConfigDict(arbitrary_types_allowed=True)

    state: VADState = Field(
        default=VADState.IDLE,
        description="Current state of the VAD finite state machine",
    )
    speech_started: bool = Field(
        default=False,
        description="Flag indicating if an active speech utterance has commenced",
    )
    last_voice_timestamp: float | None = Field(
        default=None,
        description="POSIX UTC timestamp of the most recent voice frame",
    )
    last_silence_timestamp: float | None = Field(
        default=None,
        description="POSIX UTC timestamp of the most recent silence frame",
    )
    speech_duration_ms: float = Field(
        default=0.0,
        description="Accumulated duration of continuous speech in milliseconds",
    )
    silence_duration_ms: float = Field(
        default=0.0,
        description="Accumulated duration of continuous silence in milliseconds",
    )
    utterance_counter: int = Field(
        default=0,
        description="Total count of completed speech utterances in this session",
    )
    ready_for_transcription: bool = Field(
        default=False,
        description="Flag set to True when an utterance is complete and ready for downstream STT",
    )

    def transition_to(self, new_state: VADState) -> None:
        """
        Transitions the state machine to a new state.

        :param new_state: Target VADState.
        """
        self.state = new_state
        if new_state == VADState.UTTERANCE_COMPLETE:
            self.ready_for_transcription = True
            self.utterance_counter += 1
            self.speech_started = False
        elif new_state in [VADState.IDLE, VADState.RESET]:
            self.ready_for_transcription = False
            self.speech_started = False
            self.speech_duration_ms = 0.0
            self.silence_duration_ms = 0.0

    def reset_session_vad(self) -> None:
        """
        Resets session VAD timing metrics and transitions to IDLE state.
        """
        self.state = VADState.RESET
        self.speech_started = False
        self.last_voice_timestamp = None
        self.last_silence_timestamp = None
        self.speech_duration_ms = 0.0
        self.silence_duration_ms = 0.0
        self.ready_for_transcription = False
        self.state = VADState.IDLE

    def mark_utterance_consumed(self) -> None:
        """
        Clears ready_for_transcription flag after downstream consumer processes the utterance.
        """
        self.ready_for_transcription = False
        self.state = VADState.IDLE
        self.speech_duration_ms = 0.0
        self.silence_duration_ms = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Returns JSON-serializable representation of VAD state."""
        return {
            "state": self.state.value,
            "speech_started": self.speech_started,
            "speech_duration_ms": round(self.speech_duration_ms, 2),
            "silence_duration_ms": round(self.silence_duration_ms, 2),
            "utterance_counter": self.utterance_counter,
            "ready_for_transcription": self.ready_for_transcription,
        }
