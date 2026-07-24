"""
Unit and integration test suite for /ws/voice WebSocket endpoint and ConnectionManager.
"""

from fastapi.testclient import TestClient

from app.services.connection_manager import connection_manager


def test_websocket_connection_and_heartbeat(client: TestClient):
    """
    Tests WebSocket handshake, initial welcome payload, heartbeat ping/pong, and disconnection.
    """
    with client.websocket_connect("/ws/voice") as websocket:
        # Step 1: Receive connection_established event payload
        data = websocket.receive_json()
        assert data["type"] == "connection_established"
        assert "session_id" in data
        assert data["status"] == "connected"

        session_id = data["session_id"]

        # Verify active connection in manager
        assert connection_manager.active_count == 1
        session = connection_manager.get_session(session_id)
        assert session is not None
        assert session.session_id == session_id

        # Step 2: Send ping request
        websocket.send_json({"type": "ping"})
        ack = websocket.receive_json()
        assert ack["type"] == "heartbeat_ack"
        assert ack["session_id"] == session_id

        # Step 3: Send audio_frame placeholder payload
        websocket.send_json({"type": "audio_frame", "data": "BASE64_PLACEHOLDER"})
        frame_ack = websocket.receive_json()
        assert frame_ack["type"] == "audio_frame_ack"
        assert frame_ack["status"] == "received"

    # Step 4: Disconnection check
    assert connection_manager.active_count == 0


def test_websocket_invalid_payload(client: TestClient):
    """
    Tests handling of malformed or invalid JSON WebSocket payloads.
    """
    with client.websocket_connect("/ws/voice") as websocket:
        _ = websocket.receive_json()  # Consume initial connection payload

        # Send invalid non-JSON payload
        websocket.send_text("NOT_VALID_JSON")
        err_response = websocket.receive_json()
        assert err_response["type"] == "error"
        assert err_response["code"] == "INVALID_JSON"
