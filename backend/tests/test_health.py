"""
Unit and integration tests for /health endpoint.
"""


def test_get_health_root(client):
    """
    Test GET /health top-level endpoint.
    """
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert "app_name" in data
    assert "version" in data
    assert data["status"] == "ok"
    assert "timestamp" in data
    assert data["app_name"] == "MailMind AI Backend"


def test_get_health_v1(client):
    """
    Test GET /api/v1/health versioned endpoint.
    """
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data
    assert data["app_name"] == "MailMind AI Backend"
