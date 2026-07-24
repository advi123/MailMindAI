"""
Tests AudioBuffer overflow protection.

Objective:
- Ensure the server rejects audio exceeding the maximum buffer size.
- Ensure the WebSocket connection remains alive.
- Ensure heartbeat still works after overflow.
"""

from fastapi.testclient import TestClient

from app.services.connection_manager import connection_manager

# ----------------------------------------------------------
# Test AudioBuffer Overflow Protection
# ----------------------------------------------------------


def test_audio_buffer_overflow(client: TestClient):
    """
    Streams audio frames until the AudioBuffer exceeds its
    configured maximum capacity.

    Expected behaviour:

    ✔ Overflow error returned
    ✔ Connection remains alive
    ✔ Heartbeat still works
    ✔ Buffer never exceeds configured limit
    """

    with client.websocket_connect("/ws/voice") as websocket:

        # --------------------------------------------------
        # Consume initial handshake
        # --------------------------------------------------

        welcome = websocket.receive_json()

        session_id = welcome["session_id"]

        session = connection_manager.get_session(session_id)

        assert session is not None

        # --------------------------------------------------
        # Generate a 1 MB fake audio frame
        # --------------------------------------------------

        frame = b"\x01" * (1024 * 1024)

        overflow_received = False

        # --------------------------------------------------
        # Send enough frames to exceed 10 MB
        # --------------------------------------------------

        for _ in range(11):

            websocket.send_bytes(frame)

            response = websocket.receive_json()

            if response["type"] == "error":

                overflow_received = True

                assert response["code"] == "AUDIO_BUFFER_ERROR"

                break

        # --------------------------------------------------
        # Overflow should have happened
        # --------------------------------------------------

        assert overflow_received

        # --------------------------------------------------
        # Connection should still be alive
        # --------------------------------------------------

        websocket.send_json({"type": "ping"})

        pong = websocket.receive_json()

        assert pong["type"] == "heartbeat_ack"

        assert pong["session_id"] == session_id

        # --------------------------------------------------
        # Verify buffer did not exceed limit
        # --------------------------------------------------

        assert session.audio_buffer.total_bytes <= session.audio_buffer.max_buffer_bytes

    # ------------------------------------------------------
    # After disconnect everything should be cleaned up
    # ------------------------------------------------------

    assert connection_manager.active_count == 0
