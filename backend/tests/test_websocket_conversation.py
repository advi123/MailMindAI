"""
Integration test suite for WebSocket Conversation Intelligence Engine pipeline (Audio -> STT -> Conversation Engine -> conversation_ready Event).
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


def test_websocket_conversation_ready_pipeline_flow(client: TestClient):
    """
    Tests complete end-to-end WebSocket voice streaming & conversation engine pipeline:
    1. Connect to /ws/voice & receive connection_established payload.
    2. Stream 400ms voice + 800ms silence to complete VAD utterance.
    3. Mock stt_service.transcribe to return transcript text.
    4. Assert WebSocket receives "conversation_ready" JSON event payload with prompt, turn, and history length.
    5. Assert AudioBuffer and VADState are automatically reset.
    6. Assert WebSocket connection remains open.
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
        conv_ready_received = False
        for _ in range(16):
            websocket.send_bytes(silence_chunk)
            ack = websocket.receive_json()

            if ack["vad"]["ready_for_transcription"]:
                event_msg = websocket.receive_json()
                assert event_msg["type"] == "conversation_ready"
                assert event_msg["session_id"] == session_id
                assert event_msg["turn"] == 1
                assert event_msg["history_length"] == 1
                assert event_msg["latest_message"] == "Schedule an executive sync for tomorrow morning."
                assert "=== SYSTEM MESSAGE ===" in event_msg["prompt"]
                assert "User: Schedule an executive sync for tomorrow morning." in event_msg["prompt"]
                conv_ready_received = True
                break

        assert conv_ready_received is True

        # Step 3: Verify AudioBuffer and VADState are automatically reset
        session = connection_manager.get_session(session_id)
        assert session is not None
        assert session.audio_buffer.total_bytes == 0
        assert session.vad_state.ready_for_transcription is False

        # Step 4: Verify WebSocket remains open for heartbeat ping control frame
        websocket.send_json({"type": "ping"})
        ping_ack = websocket.receive_json()
        assert ping_ack["type"] == "heartbeat_ack"
