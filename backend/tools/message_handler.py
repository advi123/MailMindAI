"""
MailMind AI Developer CLI Voice Client - Server Message Handler.

Architectural Decision Rationale:
---------------------------------
1. Strategy / Mapping Handler Pattern: Maps incoming WebSocket JSON event types to terminal UI handlers.
2. Open/Closed Principle (OCP): New event types for future milestones (Milestones 7-12: LLM responses,
   tool execution, email actions, RAG retrieval) can be registered via `register_handler(event_type, fn)`
   without modifying existing connection or audio capture logic.
"""

import json
from collections.abc import Callable
from typing import Any

from tools.terminal_ui import TerminalUI


class MessageHandler:
    """
    Parses and dispatches server WebSocket JSON payloads to terminal UI handlers.
    """

    def __init__(self, ui: TerminalUI) -> None:
        self.ui: TerminalUI = ui
        self._last_vad_state: str = ""
        self._handlers: dict[str, Callable[[dict[str, Any]], None]] = {
            "connection_established": self._handle_connection_established,
            "audio_ack": self._handle_audio_ack,
            "transcript": self._handle_transcript,
            "conversation_ready": self._handle_conversation_ready,
            "transcription_failed": self._handle_transcription_failed,
            "error": self._handle_error,
            "buffer_cleared": self._handle_buffer_cleared,
            "vad_reset": self._handle_vad_reset,
            "conversation_reset": self._handle_conversation_reset,
        }

    def register_handler(
        self, event_type: str, handler: Callable[[dict[str, Any]], None]
    ) -> None:
        """
        Registers a new event handler function dynamically for future milestone event types.
        """
        self._handlers[event_type.lower().strip()] = handler

    def handle_raw_message(self, raw_message: str) -> None:
        """
        Parses raw text JSON message from server and dispatches to registered handler.
        """
        try:
            payload = json.loads(raw_message)
        except json.JSONDecodeError:
            self.ui.print_error("PARSE_ERROR", f"Invalid JSON received: {raw_message}")
            return

        event_type = payload.get("type", "").lower().strip()
        handler = self._handlers.get(event_type)

        if handler:
            handler(payload)
        else:
            # Fallback for future unhandled milestone event payloads (LLM response, Tools, RAG)
            self.ui.print_future_event(event_type or "unknown_event", payload)

    def _handle_connection_established(self, payload: dict[str, Any]) -> None:
        session_id = payload.get("session_id")
        msg = payload.get("message", "Connection acknowledged")
        self.ui.print_status("CONNECTED", session_id=session_id, message=msg)

    def _handle_audio_ack(self, payload: dict[str, Any]) -> None:
        vad_meta = payload.get("vad", {})
        current_state = vad_meta.get("current_state", "")

        # Render VAD transition only when state changes to avoid CLI spam
        if current_state and current_state != self._last_vad_state:
            self._last_vad_state = current_state
            speech_ms = vad_meta.get("speech_duration_ms", 0.0)
            silence_ms = vad_meta.get("silence_duration_ms", 0.0)
            details = f"Speech: {speech_ms:.0f}ms, Silence: {silence_ms:.0f}ms"
            self.ui.print_vad_event(current_state, details)

    def _handle_transcript(self, payload: dict[str, Any]) -> None:
        text = payload.get("text", "")
        latency = payload.get("processing_ms", 0.0)
        provider = payload.get("provider", "groq")
        self.ui.print_transcript(text=text, processing_ms=latency, provider=provider)

    def _handle_conversation_ready(self, payload: dict[str, Any]) -> None:
        turn = payload.get("turn", 1)
        history = payload.get("history_length", 1)
        msg = payload.get("latest_message", "")
        prompt = payload.get("prompt", "")
        self.ui.print_conversation_ready(
            turn=turn, history_length=history, latest_message=msg, prompt=prompt
        )

    def _handle_transcription_failed(self, payload: dict[str, Any]) -> None:
        reason = payload.get("reason", "Unknown transcription error")
        self.ui.print_error("TRANSCRIPTION_FAILED", reason)

    def _handle_error(self, payload: dict[str, Any]) -> None:
        code = payload.get("code", "SERVER_ERROR")
        msg = payload.get("message", "An unexpected server error occurred.")
        self.ui.print_error(code, msg)

    def _handle_buffer_cleared(self, payload: dict[str, Any]) -> None:
        self.ui.print_status("BUFFER_CLEARED", message="Session audio buffer cleared.")

    def _handle_vad_reset(self, payload: dict[str, Any]) -> None:
        self.ui.print_status("VAD_RESET", message="VAD state reset.")

    def _handle_conversation_reset(self, payload: dict[str, Any]) -> None:
        self.ui.print_status("CONVERSATION_RESET", message="Conversation memory reset.")
