"""
Integration test suite verifying independent per-session VAD states across concurrent clients.
"""

import math
import struct

from fastapi.testclient import TestClient

from app.models.vad_state import VADState
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


def test_concurrent_clients_vad_isolation(client: TestClient):
    """
    Tests that two simultaneous clients maintain isolated VAD state machines:
    - Client 1 streams active voice -> triggers VOICE_ACTIVE and utterance completion.
    - Client 2 streams silence -> remains in IDLE state with 0 utterance counter.
    """
    with client.websocket_connect("/ws/voice") as ws1, client.websocket_connect("/ws/voice") as ws2:
        conn1 = ws1.receive_json()
        conn2 = ws2.receive_json()

        session_id1 = conn1["session_id"]
        session_id2 = conn2["session_id"]
        assert session_id1 != session_id2

        voice_chunk = create_pcm_sine_voice(50)
        silence_chunk = create_pcm_silence(50)

        # Step 1: Client 1 streams 400ms voice
        for _ in range(8):
            ws1.send_bytes(voice_chunk)
            _ = ws1.receive_json()

        # Client 2 streams 400ms silence simultaneously
        for _ in range(8):
            ws2.send_bytes(silence_chunk)
            ack2 = ws2.receive_json()
            assert ack2["vad"]["current_state"] == "idle"

        # Verify in ConnectionManager
        session1 = connection_manager.get_session(session_id1)
        session2 = connection_manager.get_session(session_id2)

        assert session1 is not None and session2 is not None
        assert session1.vad_state.state in [VADState.VOICE_ACTIVE, VADState.VOICE_STARTED]
        assert session2.vad_state.state == VADState.IDLE

        # Step 2: Client 1 streams silence to complete utterance (800ms silence = 16 frames)
        for _ in range(16):
            ws1.send_bytes(silence_chunk)
            ack1 = ws1.receive_json()
            if ack1["vad"]["ready_for_transcription"]:
                event_msg1 = ws1.receive_json()
                assert event_msg1["type"] in ["transcript", "transcription_failed", "utterance_ready"]
                break

        # Client 1 completed utterance 1; Client 2 still IDLE at 0
        assert session1.vad_state.utterance_counter == 1
        assert session2.vad_state.utterance_counter == 0
        assert session2.vad_state.state == VADState.IDLE
