"""
Integration test suite for WebSocket Speech-To-Text (STT) transcription pipeline and auto-reset lifecycle.
"""

import math
import struct
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.services.connection_manager import connection_manager
from app.services.stt_service import stt_service


def create_pcm_silence(duration_ms: int = 50, sample_rate: int = 16000) -> bytes:
    """Helper creating raw PCM silence frame (0 amplitude)."""
    sample_count = int(sample_rate * (duration_ms / 1000.0))
    return b"\x00\x00" * sample_count


def create_pcm_sine_voice(duration_ms: int = 50, sample_rate: int = 16000, frequency: int = 440, amplitude: int = 12000) -> bytes:
    """Helper creating synthetic PCM audio frame simulating active voice signal."""
    sample_count = int(sample_rate * (duration_ms / 1000.0))
    samples = [int(amplitude * math.sin(2 * math.pi * frequency * i / sample_rate)) for i in range(sample_count)]
    return struct.pack(f"<{sample_count}h", *samples)


def test_websocket_successful_transcription_flow(client: TestClient):
    """
    Tests end-to-end WebSocket voice streaming pipeline:
    1. Connect & receive connection_established payload.
    2. Stream 400ms active voice + 800ms silence to trigger VAD utterance completion.
    3. Mock stt_service.transcribe to return success transcript response dict.
    4. Assert WebSocket receives "transcript" JSON event payload.
    5. Assert AudioBuffer and VADState are automatically reset.
    6. Assert WebSocket connection remains open and functional.
    """
    mock_stt_result = {
        "success": True,
        "text": "Schedule an executive sync for tomorrow morning.",
        "language": "en",
        "processing_ms": 145.0,
        "provider": "groq",
        "model": "whisper-large-v3-turbo",
        "word_count": 7,
    }

    with (
        patch.object(stt_service, "transcribe", new=AsyncMock(return_value=mock_stt_result)),
        client.websocket_connect("/ws/voice") as websocket,
    ):
        conn = websocket.receive_json()
        session_id = conn["session_id"]

        voice_chunk = create_pcm_sine_voice(50)
        silence_chunk = create_pcm_silence(50)

        # Step 1: Send active voice (400ms = 8 frames)
        for _ in range(8):
            websocket.send_bytes(voice_chunk)
            _ = websocket.receive_json()

        # Step 2: Send trailing silence (800ms = 16 frames) to complete utterance
        transcript_received = False
        for _ in range(16):
            websocket.send_bytes(silence_chunk)
            ack = websocket.receive_json()

            if ack["vad"]["ready_for_transcription"]:
                event_msg = websocket.receive_json()
                assert event_msg["type"] == "transcript"
                assert event_msg["session_id"] == session_id
                assert event_msg["utterance_index"] == 1
                assert event_msg["text"] == "Schedule an executive sync for tomorrow morning."
                assert "processing_ms" in event_msg
                transcript_received = True
                break

        assert transcript_received is True

        # Step 3: Verify AudioBuffer and VADState are automatically reset
        session = connection_manager.get_session(session_id)
        assert session is not None
        assert session.audio_buffer.total_bytes == 0
        assert session.audio_buffer.frame_count == 0
        assert session.vad_state.ready_for_transcription is False

        # Step 4: Verify WebSocket remains open for next ping control frame
        websocket.send_json({"type": "ping"})
        ping_ack = websocket.receive_json()
        assert ping_ack["type"] == "heartbeat_ack"


def test_websocket_transcription_failure_handling(client: TestClient):
    """
    Tests handling of STT provider failures over WebSocket:
    1. VAD completes utterance.
    2. Mock stt_service.transcribe returns a failure dict response.
    3. Assert WebSocket receives "transcription_failed" JSON event payload.
    4. Assert AudioBuffer and VADState are reset.
    5. Assert WebSocket connection does NOT disconnect.
    """
    mock_failure_result = {
        "success": False,
        "provider": "groq",
        "error": "Groq API Timeout",
        "processing_ms": 30000.0,
    }

    with (
        patch.object(stt_service, "transcribe", new=AsyncMock(return_value=mock_failure_result)),
        client.websocket_connect("/ws/voice") as websocket,
    ):
        conn = websocket.receive_json()
        session_id = conn["session_id"]

        voice_chunk = create_pcm_sine_voice(50)
        silence_chunk = create_pcm_silence(50)

        # Stream voice (400ms)
        for _ in range(8):
            websocket.send_bytes(voice_chunk)
            _ = websocket.receive_json()

        # Stream silence (800ms) to trigger utterance completion
        failure_received = False
        for _ in range(16):
            websocket.send_bytes(silence_chunk)
            ack = websocket.receive_json()

            if ack["vad"]["ready_for_transcription"]:
                event_msg = websocket.receive_json()
                assert event_msg["type"] == "transcription_failed"
                assert event_msg["session_id"] == session_id
                assert "Groq API Timeout" in event_msg["reason"]
                failure_received = True
                break

        assert failure_received is True

        # Verify AudioBuffer and VADState are reset
        session = connection_manager.get_session(session_id)
        assert session is not None
        assert session.audio_buffer.total_bytes == 0
        assert session.vad_state.ready_for_transcription is False

        # Connection remains open
        websocket.send_json({"type": "ping"})
        ping_ack = websocket.receive_json()
        assert ping_ack["type"] == "heartbeat_ack"
