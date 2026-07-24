"""
Unit and integration test suite for AudioBuffer, AudioStreamService, and binary WebSocket streaming.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AppValidationError
from app.models.audio_buffer import AudioBuffer
from app.services.connection_manager import connection_manager


def test_audio_buffer_operations():
    """
    Tests AudioBuffer unit methods: append_frame, clear, total_bytes, frame_count,
    duration_estimate, and export_raw integrity.
    """
    buffer = AudioBuffer()
    assert buffer.total_bytes == 0
    assert buffer.frame_count == 0
    assert buffer.duration_estimate() == 0.0

    chunk1 = (
        b"\x01\x02\x03\x04" * 8000
    )  # 32,000 bytes = 1.0s of 16kHz 16-bit mono audio
    chunk2 = b"\x05\x06\x07\x08" * 4000  # 16,000 bytes = 0.5s

    assert buffer.append_frame(chunk1) is True
    assert buffer.frame_count == 1
    assert buffer.total_bytes == 32000
    assert buffer.duration_estimate() == 1.0

    assert buffer.append_frame(chunk2) is True
    assert buffer.frame_count == 2
    assert buffer.total_bytes == 48000
    assert buffer.duration_estimate() == 1.5

    assert buffer.export_raw() == chunk1 + chunk2

    # Test clear
    buffer.clear()
    assert buffer.total_bytes == 0
    assert buffer.frame_count == 0
    assert buffer.duration_estimate() == 0.0
    assert buffer.export_raw() == b""


def test_audio_buffer_invalid_and_overflow():
    """
    Tests AudioBuffer rejection of invalid inputs and buffer capacity overflow.
    """
    buffer = AudioBuffer(max_buffer_bytes=100)

    # Empty frame rejection
    with pytest.raises(AppValidationError):
        buffer.append_frame(b"")

    # Non-bytes rejection
    with pytest.raises(AppValidationError):
        buffer.append_frame("invalid_string_type")  # type: ignore

    # Append valid chunk
    buffer.append_frame(b"X" * 60)
    assert buffer.total_bytes == 60

    # Capacity overflow rejection (60 + 50 = 110 > 100 limit)
    with pytest.raises(AppValidationError):
        buffer.append_frame(b"Y" * 50)


def test_websocket_single_audio_frame(client: TestClient):
    """
    Tests streaming a single binary audio frame over WebSocket.
    """
    with client.websocket_connect("/ws/voice") as websocket:
        _ = websocket.receive_json()  # Consume initial connection payload

        sample_pcm = b"\x00\xff" * 500  # 1000 bytes binary chunk
        websocket.send_bytes(sample_pcm)

        ack = websocket.receive_json()
        assert ack["type"] == "audio_ack"
        assert ack["frame_number"] == 1
        assert ack["frame_bytes"] == 1000
        assert ack["total_bytes"] == 1000
        assert ack["duration_estimate"] == 0.031


def test_websocket_multiple_audio_frames_accumulation(client: TestClient):
    """
    Tests streaming multiple sequential binary audio frames over WebSocket.
    """
    with client.websocket_connect("/ws/voice") as websocket:
        data = websocket.receive_json()
        session_id = data["session_id"]

        chunk = b"\x12\x34" * 1000  # 2000 bytes per frame

        for i in range(1, 4):
            websocket.send_bytes(chunk)
            ack = websocket.receive_json()
            assert ack["type"] == "audio_ack"
            assert ack["frame_number"] == i
            assert ack["total_bytes"] == i * 2000

        # Verify session buffer state directly in ConnectionManager
        session = connection_manager.get_session(session_id)
        assert session is not None
        assert session.audio_buffer.frame_count == 3
        assert session.audio_buffer.total_bytes == 6000
        assert len(session.audio_buffer.export_raw()) == 6000

        # Clear buffer via JSON control message
        websocket.send_json({"type": "clear_buffer"})
        clear_ack = websocket.receive_json()
        assert clear_ack["type"] == "buffer_cleared"
        assert session.audio_buffer.total_bytes == 0


def test_websocket_concurrent_session_isolation(client: TestClient):
    """
    Tests that multiple concurrent streaming clients maintain isolated audio buffers.
    """
    with client.websocket_connect("/ws/voice") as ws1, client.websocket_connect(
        "/ws/voice"
    ) as ws2:
        conn1 = ws1.receive_json()
        conn2 = ws2.receive_json()

        session_id1 = conn1["session_id"]
        session_id2 = conn2["session_id"]
        assert session_id1 != session_id2

        # Client 1 sends 3000 bytes audio
        ws1.send_bytes(b"A" * 3000)
        ack1 = ws1.receive_json()
        assert ack1["total_bytes"] == 3000

        # Client 2 sends 1500 bytes audio
        ws2.send_bytes(b"B" * 1500)
        ack2 = ws2.receive_json()
        assert ack2["total_bytes"] == 1500

        # Retrieve sessions from ConnectionManager
        s1 = connection_manager.get_session(session_id1)
        s2 = connection_manager.get_session(session_id2)

        assert s1 is not None and s2 is not None
        assert s1.audio_buffer.total_bytes == 3000
        assert s2.audio_buffer.total_bytes == 1500
        assert s1.audio_buffer.export_raw() == b"A" * 3000
        assert s2.audio_buffer.export_raw() == b"B" * 1500


def test_websocket_empty_frame_rejection(client: TestClient):
    """
    Tests that sending empty binary frames yields an error ACK without crashing the socket stream.
    """
    with client.websocket_connect("/ws/voice") as websocket:
        _ = websocket.receive_json()

        # Send 0-byte empty frame
        websocket.send_bytes(b"")
        err_ack = websocket.receive_json()
        assert err_ack["type"] == "error"
        assert err_ack["code"] == "AUDIO_BUFFER_ERROR"

        # Ensure socket connection remains alive and functional
        websocket.send_json({"type": "ping"})
        ping_ack = websocket.receive_json()
        assert ping_ack["type"] == "heartbeat_ack"
