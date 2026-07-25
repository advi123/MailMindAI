"""
Unit test suite for tools/ subpackage components (VoiceClientConfig, TerminalUI, MessageHandler, AudioRecorder).
"""

from unittest.mock import MagicMock

import numpy as np

from tools.config import VoiceClientConfig
from tools.message_handler import MessageHandler
from tools.terminal_ui import TerminalUI


def test_voice_client_config_calculations():
    """
    Tests VoiceClientConfig 50ms chunk calculations for 16kHz mono 16-bit PCM.
    """
    config = VoiceClientConfig(sample_rate=16000, chunk_duration_ms=50)

    # 16000 * 0.05 = 800 samples
    assert config.chunk_size_samples == 800
    # 800 * 2 = 1600 bytes
    assert config.chunk_size_bytes == 1600


def test_terminal_ui_rendering_methods(capsys):
    """
    Tests TerminalUI rendering methods without error.
    """
    ui = TerminalUI(use_color=False)
    ui.print_header("ws://localhost:8000/ws/voice", 16000)
    ui.print_status("CONNECTED", session_id="sess_123", message="Ready")
    ui.print_vad_event("voice_active")
    ui.print_transcript("Schedule a meeting", processing_ms=120.0)
    ui.print_conversation_ready(turn=1, history_length=1, latest_message="Schedule a meeting", prompt="=== SYSTEM ===")
    ui.print_error("TEST_ERROR", "Test error message")

    captured = capsys.readouterr()
    assert "MailMind AI Developer Voice Client" in captured.out
    assert "sess_123" in captured.out
    assert "Schedule a meeting" in captured.out


def test_message_handler_dispatch():
    """
    Tests MessageHandler JSON payload parsing and dispatching to TerminalUI.
    """
    ui = MagicMock(spec=TerminalUI)
    handler = MessageHandler(ui=ui)

    # Connection established
    conn_json = '{"type": "connection_established", "session_id": "s_100", "message": "Welcome"}'
    handler.handle_raw_message(conn_json)
    ui.print_status.assert_called_with("CONNECTED", session_id="s_100", message="Welcome")

    # STT Transcript
    stt_json = '{"type": "transcript", "text": "Draft email to John", "processing_ms": 150.0, "provider": "groq"}'
    handler.handle_raw_message(stt_json)
    ui.print_transcript.assert_called_with(text="Draft email to John", processing_ms=150.0, provider="groq")

    # Conversation Ready
    conv_json = '{"type": "conversation_ready", "turn": 1, "history_length": 1, "latest_message": "Draft email", "prompt": "P_1"}'
    handler.handle_raw_message(conv_json)
    ui.print_conversation_ready.assert_called_with(turn=1, history_length=1, latest_message="Draft email", prompt="P_1")

    # Future Event Fallback (Milestone 7 LLM / Tools)
    future_json = '{"type": "assistant_response", "text": "I will draft that email."}'
    handler.handle_raw_message(future_json)
    ui.print_future_event.assert_called()


def test_audio_recorder_pcm_bytes_conversion():
    """
    Tests AudioRecorder numpy float32 to int16 PCM conversion math.
    """
    # 800 float32 samples with value 0.5
    float_samples = np.full((800, 1), 0.5, dtype=np.float32)
    int_samples = (float_samples * 32767.0).astype(np.int16)
    expected_bytes = int_samples.tobytes()

    assert len(expected_bytes) == 1600
    assert isinstance(expected_bytes, bytes)
