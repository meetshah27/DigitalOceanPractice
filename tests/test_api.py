from tests.conftest import make_review


def post(client, **overrides):
    return client.post("/reviews", json=make_review(**overrides))


# --- ingest ---

def test_ingest_clean_review(client):
    resp = post(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_flagged"] is False
    assert body["flag_reasons"] == []
    assert body["submitted_at"] == "2026-09-21T11:00:00Z"
    assert "received_at" in body


def test_ingest_spam_review_is_flagged(client):
    resp = post(client, text="Buy now at www.cheap-deals.xyz")
    assert resp.status_code == 201
    assert resp.json()["flag_reasons"] == ["contains_url", "spam_keywords"]


def test_identical_retry_is_idempotent(client):
    first = post(client)
    retry = post(client)
    assert retry.status_code == 200
    assert retry.json() == first.json()


def test_same_id_different_payload_conflicts(client):
    post(client)
    resp = post(client, rating=1)
    assert resp.status_code == 409


def test_duplicate_text_flags_only_later_review(client):
    text = "Amazing quality, would recommend to everyone!"
    post(client, review_id="rev_1", user_id="usr_1", text=text)
    resp = post(client, review_id="rev_2", user_id="usr_2", product_id="prod_2", text=text)
    assert resp.json()["flag_reasons"] == ["duplicate_text"]
    assert client.get("/reviews/rev_1").json()["is_flagged"] is False


def test_duplicate_text_matches_after_normalization(client):
    post(client, review_id="rev_1", user_id="usr_1", text="Amazing quality, would recommend!")
    resp = post(client, review_id="rev_2", user_id="usr_2", product_id="prod_2",
                text="  AMAZING quality,   would recommend! ")
    assert resp.json()["flag_reasons"] == ["duplicate_text"]


def test_same_user_same_text_is_not_duplicate_text(client):
    text = "Amazing quality, would recommend to everyone!"
    post(client, review_id="rev_1", product_id="prod_1", text=text)
    resp = post(client, review_id="rev_2", product_id="prod_2", text=text)
    assert resp.json()["is_flagged"] is False


def test_same_user_same_product_flagged(client):
    post(client, review_id="rev_1")
    resp = post(client, review_id="rev_2", text="Changed my mind, it broke.")
    assert resp.json()["flag_reasons"] == ["duplicate_product_review"]


# --- get ---

def test_get_review(client):
    post(client)
    resp = client.get("/reviews/rev_1")
    assert resp.status_code == 200
    assert resp.json()["review_id"] == "rev_1"


def test_get_missing_review_404(client):
    assert client.get("/reviews/rev_nope").status_code == 404


# --- flagged query ---

def seed_flagged(client):
    post(client, review_id="rev_a", product_id="prod_1", user_id="usr_1",
         text="click here", submitted_at="2026-09-21T10:00:00Z")
    post(client, review_id="rev_b", product_id="prod_2", user_id="usr_2",
         text="click here now", submitted_at="2026-09-21T12:00:00Z")
    post(client, review_id="rev_c", product_id="prod_1", user_id="usr_3",
         text="visit my shop", submitted_at="2026-09-21T11:00:00Z")
    post(client, review_id="rev_clean", product_id="prod_1", user_id="usr_4",
         text="Solid product.", submitted_at="2026-09-21T13:00:00Z")


def ids(resp):
    return [r["review_id"] for r in resp.json()["items"]]


def test_flagged_excludes_clean_and_orders_newest_first(client):
    seed_flagged(client)
    resp = client.get("/reviews/flagged")
    assert resp.status_code == 200
    assert ids(resp) == ["rev_b", "rev_c", "rev_a"]
    assert resp.json()["total"] == 3


def test_flagged_filter_by_product(client):
    seed_flagged(client)
    assert ids(client.get("/reviews/flagged", params={"product_id": "prod_1"})) == ["rev_c", "rev_a"]


def test_flagged_filter_by_user(client):
    seed_flagged(client)
    assert ids(client.get("/reviews/flagged", params={"user_id": "usr_2"})) == ["rev_b"]


def test_flagged_pagination(client):
    seed_flagged(client)
    resp = client.get("/reviews/flagged", params={"limit": 2, "offset": 1})
    assert ids(resp) == ["rev_c", "rev_a"]
    assert resp.json()["total"] == 3
    assert resp.json()["limit"] == 2
    assert resp.json()["offset"] == 1


def test_flagged_empty(client):
    resp = client.get("/reviews/flagged")
    assert resp.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}


def test_flagged_tie_on_submitted_at_ordered_by_review_id(client):
    post(client, review_id="rev_x1", user_id="usr_1", text="click here")
    post(client, review_id="rev_x2", user_id="usr_2", product_id="prod_2", text="click here")
    assert ids(client.get("/reviews/flagged")) == ["rev_x2", "rev_x1"]
