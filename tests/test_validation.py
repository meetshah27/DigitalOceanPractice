from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import make_review


def post(client, **overrides):
    return client.post("/reviews", json=make_review(**overrides))


def error_fields(resp) -> set[str]:
    return {e["loc"][-1] for e in resp.json()["detail"]}


def iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


# --- ids ---

@pytest.mark.parametrize("field,value", [
    ("review_id", "5521"),
    ("review_id", "rev_"),
    ("review_id", "rev_55-21"),
    ("review_id", "rev_" + "a" * 61),  # 65 chars
    ("product_id", "rev_88"),
    ("user_id", "usr 301"),
    ("user_id", ""),
])
def test_invalid_ids_rejected(client, field, value):
    resp = post(client, **{field: value})
    assert resp.status_code == 422
    assert error_fields(resp) == {field}


def test_id_at_max_length_accepted(client):
    assert post(client, review_id="rev_" + "a" * 60).status_code == 201  # 64 chars


# --- rating ---

@pytest.mark.parametrize("value", [0, 6, -1, 4.5, 5.0, "5", True, None])
def test_invalid_rating_rejected(client, value):
    resp = post(client, rating=value)
    assert resp.status_code == 422
    assert error_fields(resp) == {"rating"}


@pytest.mark.parametrize("value", [1, 5])
def test_rating_bounds_accepted(client, value):
    assert post(client, rating=value).status_code == 201


# --- text ---

@pytest.mark.parametrize("value", ["", "   ", "\n\t", "a" * 5001])
def test_invalid_text_rejected(client, value):
    resp = post(client, text=value)
    assert resp.status_code == 422
    assert error_fields(resp) == {"text"}


def test_text_is_trimmed(client):
    assert post(client, text="  Nice.  ").json()["text"] == "Nice."


def test_text_at_max_length_accepted(client):
    assert post(client, text="a" * 5000).status_code == 201


def test_unicode_and_emoji_text(client):
    text = "Très bien 👍 非常好"
    resp = post(client, text=text)
    assert resp.status_code == 201
    assert client.get("/reviews/rev_1").json()["text"] == text


# --- submitted_at ---

@pytest.mark.parametrize("value", [
    "2026-09-21T11:00:00",  # naive
    "not-a-date",
    "2026-13-01T00:00:00Z",
    1758452400,  # epoch seconds: no timezone info
])
def test_invalid_submitted_at_rejected(client, value):
    resp = post(client, submitted_at=value)
    assert resp.status_code == 422
    assert error_fields(resp) == {"submitted_at"}


def test_submitted_at_normalized_to_utc(client):
    resp = post(client, submitted_at="2026-09-21T13:00:00+02:00")
    assert resp.json()["submitted_at"] == "2026-09-21T11:00:00Z"


def test_submitted_at_far_future_rejected(client):
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    assert post(client, submitted_at=iso(future)).status_code == 422


def test_submitted_at_within_clock_skew_accepted(client):
    near = datetime.now(timezone.utc) + timedelta(minutes=1)
    assert post(client, submitted_at=iso(near)).status_code == 201


def test_retry_with_same_instant_different_offset_is_idempotent(client):
    post(client, submitted_at="2026-09-21T11:00:00Z")
    assert post(client, submitted_at="2026-09-21T13:00:00+02:00").status_code == 200


# --- body shape ---

def test_extra_field_rejected(client):
    resp = client.post("/reviews", json={**make_review(), "is_flagged": False})
    assert resp.status_code == 422
    assert error_fields(resp) == {"is_flagged"}


@pytest.mark.parametrize("field", ["review_id", "product_id", "user_id", "rating", "text", "submitted_at"])
def test_missing_field_rejected(client, field):
    body = make_review()
    del body[field]
    resp = client.post("/reviews", json=body)
    assert resp.status_code == 422
    assert error_fields(resp) == {field}


def test_malformed_json_rejected(client):
    resp = client.post("/reviews", content=b"{not json", headers={"Content-Type": "application/json"})
    assert resp.status_code == 422


def test_array_body_rejected(client):
    assert client.post("/reviews", json=[make_review()]).status_code == 422


def test_rejected_review_not_stored(client):
    post(client, rating=9)
    assert client.get("/reviews/rev_1").status_code == 404


# --- flagged query params ---

@pytest.mark.parametrize("params", [
    {"limit": 0},
    {"limit": 101},
    {"limit": "abc"},
    {"offset": -1},
    {"product_id": "p" * 65},
])
def test_invalid_query_params_rejected(client, params):
    assert client.get("/reviews/flagged", params=params).status_code == 422


def test_limit_upper_bound_accepted(client):
    assert client.get("/reviews/flagged", params={"limit": 100}).status_code == 200


def test_offset_past_end_returns_empty_items_with_total(client):
    post(client, text="click here")
    resp = client.get("/reviews/flagged", params={"offset": 10})
    assert resp.json()["items"] == []
    assert resp.json()["total"] == 1
