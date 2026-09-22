import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    with TestClient(app) as c:
        yield c


def make_review(**overrides) -> dict:
    review = {
        "review_id": "rev_1",
        "product_id": "prod_1",
        "user_id": "usr_1",
        "rating": 5,
        "text": "Great product, fast shipping!",
        "submitted_at": "2026-09-21T11:00:00Z",
    }
    review.update(overrides)
    return review
