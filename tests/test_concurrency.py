"""Concurrent ingests against the store: the transaction must keep
idempotency and duplicate detection correct under races."""
from concurrent.futures import ThreadPoolExecutor

from app import store
from app.schemas import ReviewIn
from tests.conftest import make_review

N = 10


def run_parallel(fn, args):
    with ThreadPoolExecutor(max_workers=N) as pool:
        return list(pool.map(lambda a: _capture(fn, a), args))


def _capture(fn, arg):
    try:
        return fn(arg)
    except Exception as exc:
        return exc


def test_same_review_in_parallel_created_once(client):
    review = ReviewIn(**make_review())
    results = run_parallel(store.ingest, [review] * N)
    assert [created for _, created in results].count(True) == 1
    assert client.get("/reviews/flagged").json()["total"] == 0
    assert client.get("/reviews/rev_1").status_code == 200


def test_same_id_different_payloads_in_parallel(client):
    reviews = [ReviewIn(**make_review(text=f"Version {i} of my review")) for i in range(N)]
    results = run_parallel(store.ingest, reviews)
    created = [r for r in results if isinstance(r, tuple) and r[1]]
    conflicts = [r for r in results if isinstance(r, store.ReviewConflict)]
    assert len(created) == 1
    assert len(conflicts) == N - 1


def test_duplicate_text_race_flags_all_but_one(client):
    text = "Amazing quality, would recommend to everyone!"
    reviews = [
        ReviewIn(**make_review(review_id=f"rev_{i}", user_id=f"usr_{i}", product_id=f"prod_{i}", text=text))
        for i in range(N)
    ]
    results = run_parallel(store.ingest, reviews)
    flagged = [out for out, _ in results if out.flag_reasons == ["duplicate_text"]]
    assert len(flagged) == N - 1
