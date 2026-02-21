from fastapi.testclient import TestClient

import core.db.database as db
from core.main import app


def test_healthz_ok():
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert "uptimeSeconds" in payload


def test_readyz_503_when_db_unavailable(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(db, "async_session", None, raising=False)

    def _broken_init_db():
        db.async_session = None

    monkeypatch.setattr(db, "init_db", _broken_init_db, raising=True)
    response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
