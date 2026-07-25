"""
Integration test suite verifying utterance boundary detection and conversation engine processing over WebSocket.
"""

import math
import struct

from fastapi.testclient import TestClient

from app.services.connection_manager import connection_manager


def create_pcm_silence(duration_ms: int = 50, sample_rate: int = 16000) -> bytes:
    """Helper creating raw PCM silence frame (0 amplitude)."""
    sample_count = int(sample_rate * (duration_ms / 1000.0))
    return b"\x00\x00" * sample_count


def create_pcm_sine_voice(duration_ms: int = 50, sample_rate: int = 16000, frequency: int = 440, amplitude: int = 12000) -> bytes:
    """Helper creating synthetic PCM audio frame simulating active voice signal."""
    sample_count = int(sample_rate * (duration_ms / 1000.0))
    samples = [int(amplitude * math.sin(2 * math.pi * frequency * i / sample_rate)) for i in range(sample_count)]
    return struct.pack(f"<{sample_count}h", *samples)


def test_full_utterance_lifecycle_over_websocket(client: TestClient):
    """
    Tests complete utterance lifecycle over WebSocket /ws/voice:
    1. Connect & consume welcome payload
    2. Stream initial silence (100ms)
    3. Stream active voice (500ms)
    4. Stream trailing silence (800ms threshold)
    5. Assert receipt of conversation_ready notification
    6. Verify AudioBuffer is automatically reset for the next utterance turn
    """
    with client.websocket_connect("/ws/voice") as websocket:
        conn = websocket.receive_json()
        session_id = conn["session_id"]

        silence_chunk = create_pcm_silence(50)  # 50ms silence frame (1600 bytes)
        voice_chunk = create_pcm_sine_voice(50)  # 50ms voice frame (1600 bytes)

        # 1. Initial Silence (100ms = 2 frames)
        for _ in range(2):
            websocket.send_bytes(silence_chunk)
            ack = websocket.receive_json()
            assert ack["type"] == "audio_ack"
            assert ack["vad"]["current_state"] == "idle"

        # 2. Active Voice (500ms = 10 frames)
        for _ in range(10):
            websocket.send_bytes(voice_chunk)
            ack = websocket.receive_json()
            assert ack["type"] == "audio_ack"

        # 3. Trailing Silence (800ms = 16 frames @ 50ms each)
        received_utterance_event = False
        for _ in range(16):
            websocket.send_bytes(silence_chunk)
            ack = websocket.receive_json()
            assert ack["type"] == "audio_ack"

            # Check if conversation event follows
            if ack["vad"]["ready_for_transcription"]:
                event_msg = websocket.receive_json()
                assert event_msg["type"] in ["conversation_ready", "transcript", "transcription_failed", "utterance_ready"]
                assert event_msg["session_id"] == session_id
                received_utterance_event = True
                break

        assert received_utterance_event is True

        # Verify AudioBuffer and VADState are automatically reset
        session = connection_manager.get_session(session_id)
        assert session is not None
        assert session.audio_buffer.total_bytes == 0
        assert session.vad_state.ready_for_transcription is False


def test_rapid_speech_start_stop(client: TestClient):
    """
    Tests handling of rapid start/stop speech patterns without false utterance completions.
    """
    with client.websocket_connect("/ws/voice") as websocket:
        _ = websocket.receive_json()

        voice_chunk = create_pcm_sine_voice(50)
        silence_chunk = create_pcm_silence(50)

        # Burst 1: 300ms voice
        for _ in range(6):
            websocket.send_bytes(voice_chunk)
            _ = websocket.receive_json()

        # Short pause: 200ms silence (< 800ms threshold)
        for _ in range(4):
            websocket.send_bytes(silence_chunk)
            ack = websocket.receive_json()
            assert ack["vad"]["ready_for_transcription"] is False

        # Burst 2: 300ms voice resumes
        for _ in range(6):
            websocket.send_bytes(voice_chunk)
            ack = websocket.receive_json()
            assert ack["vad"]["current_state"] in ["voice_active", "voice_started"]
