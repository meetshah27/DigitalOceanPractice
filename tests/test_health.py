def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_request_id_echoed(client):
    resp = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert resp.headers["X-Request-ID"] == "abc123"


def test_request_id_generated(client):
    resp = client.get("/health")
    assert len(resp.headers["X-Request-ID"]) == 32
