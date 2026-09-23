from app import store
from tests.conftest import make_review


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_request_id_echoed(client):
    resp = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert resp.headers["X-Request-ID"] == "abc123"


def test_unhandled_error_returns_500_with_request_id(client, monkeypatch):
    def boom(review):
        raise RuntimeError("db exploded")

    monkeypatch.setattr(store, "ingest", boom)
    resp = client.post("/reviews", json=make_review(), headers={"X-Request-ID": "abc123"})
    assert resp.status_code == 500
    assert resp.headers["X-Request-ID"] == "abc123"
    assert resp.json() == {"detail": "Internal Server Error"}
    assert "db exploded" not in resp.text


def test_request_id_generated(client):
    resp = client.get("/health")
    assert len(resp.headers["X-Request-ID"]) == 32
