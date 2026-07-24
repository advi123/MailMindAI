from fastapi.testclient import TestClient

from app.services.connection_manager import connection_manager


def test_multiple_websocket_connections(client: TestClient):
    """
    Test that multiple WebSocket clients can connect simultaneously,
    each receives a unique session ID, and the ConnectionManager
    correctly tracks active connections.
    """

    with client.websocket_connect("/ws/voice") as ws1, client.websocket_connect(
        "/ws/voice"
    ) as ws2, client.websocket_connect("/ws/voice") as ws3:

        # Receive initial connection payloads
        data1 = ws1.receive_json()
        data2 = ws2.receive_json()
        data3 = ws3.receive_json()

        session1 = data1["session_id"]
        session2 = data2["session_id"]
        session3 = data3["session_id"]

        # Verify all session IDs are unique
        assert session1 != session2
        assert session1 != session3
        assert session2 != session3

        # Verify active connections
        assert connection_manager.active_count == 3

    # After exiting the 'with' block,
    # all connections should be closed automatically.

    assert connection_manager.active_count == 0
