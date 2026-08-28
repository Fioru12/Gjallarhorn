import importlib
import os
import tempfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    monkeypatch.setenv("GJALLARHORN_API_KEY", "test-api-key-123")
    monkeypatch.setenv("GJALLARHORN_CONFIG", "this-file-does-not-exist.yaml")
    monkeypatch.setenv("GJALLARHORN_DB_PATH", db_path)
    # No channels configured -> notify() will just report sent_to: [] without
    # ever touching the network, which is exactly what we want in a test.
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("WEBHOOK_URL", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)

    import api.server as server_module

    importlib.reload(server_module)

    with TestClient(server_module.app) as test_client:
        yield test_client

    server_module.db.close()
    try:
        os.remove(db_path)
    except OSError:
        pass  # Windows may keep a brief lock on the sqlite file handle


class TestNotifyEndpoint:
    def test_missing_api_key_returns_401(self, client):
        response = client.post(
            "/api/v1/notify",
            json={"source": "test", "severity": "high", "title": "T", "message": "M"},
        )
        assert response.status_code == 401

    def test_wrong_api_key_returns_401(self, client):
        response = client.post(
            "/api/v1/notify",
            json={"source": "test", "severity": "high", "title": "T", "message": "M"},
            headers={"X-API-Key": "wrong-key"},
        )
        assert response.status_code == 401

    def test_correct_api_key_returns_200(self, client):
        response = client.post(
            "/api/v1/notify",
            json={"source": "test", "severity": "high", "title": "T", "message": "M"},
            headers={"X-API-Key": "test-api-key-123"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "sent"

    def test_malformed_payload_returns_422(self, client):
        response = client.post(
            "/api/v1/notify",
            json={"source": "test", "severity": "not-a-real-severity", "title": "T", "message": "M"},
            headers={"X-API-Key": "test-api-key-123"},
        )
        assert response.status_code == 422

    def test_missing_required_field_returns_422(self, client):
        response = client.post(
            "/api/v1/notify",
            json={"severity": "high", "title": "T", "message": "M"},
            headers={"X-API-Key": "test-api-key-123"},
        )
        assert response.status_code == 422

    def test_duplicate_notification_is_suppressed(self, client):
        headers = {"X-API-Key": "test-api-key-123"}
        payload = {"source": "dup-test", "severity": "high", "title": "Same alert", "message": "M"}

        first = client.post("/api/v1/notify", json=payload, headers=headers)
        second = client.post("/api/v1/notify", json=payload, headers=headers)

        assert first.json()["status"] == "sent"
        assert second.json()["status"] == "suppressed"


class TestHistoryEndpoint:
    def test_history_requires_api_key(self, client):
        response = client.get("/api/v1/history")
        assert response.status_code == 401

    def test_history_returns_recorded_notifications(self, client):
        headers = {"X-API-Key": "test-api-key-123"}
        client.post(
            "/api/v1/notify",
            json={"source": "history-test", "severity": "low", "title": "T", "message": "M"},
            headers=headers,
        )

        response = client.get("/api/v1/history", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["total"] >= 1
        assert any(item["source"] == "history-test" for item in body["items"])


class TestRoot:
    def test_root_is_public(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["service"] == "Gjallarhorn Alerting Hub"
