from fastapi.testclient import TestClient


def test_health_check_returns_ok(client: TestClient) -> None:
    """Verify /health returns 200 with status ok and healthy database."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["environment"] == "test"
    assert data["database"] == "healthy"
    assert data["version"] == "0.1.0"
