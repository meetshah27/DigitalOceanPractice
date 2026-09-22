import json
import sqlite3
from datetime import datetime, timezone

from app import rules
from app.db import connection
from app.schemas import ReviewIn, ReviewOut

# Fixed-width UTC format so TEXT ordering matches time ordering.
_TS_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


class ReviewConflict(Exception):
    """Same review_id already stored with a different payload."""


def _ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(_TS_FORMAT)


def _to_out(row: sqlite3.Row) -> ReviewOut:
    return ReviewOut(
        review_id=row["review_id"],
        product_id=row["product_id"],
        user_id=row["user_id"],
        rating=row["rating"],
        text=row["text"],
        submitted_at=datetime.fromisoformat(row["submitted_at"]),
        received_at=datetime.fromisoformat(row["received_at"]),
        is_flagged=bool(row["is_flagged"]),
        flag_reasons=json.loads(row["flag_reasons"]),
    )


def _same_payload(row: sqlite3.Row, review: ReviewIn) -> bool:
    return (
        row["product_id"] == review.product_id
        and row["user_id"] == review.user_id
        and row["rating"] == review.rating
        and row["text"] == review.text
        and row["submitted_at"] == _ts(review.submitted_at)
    )


def ingest(review: ReviewIn) -> tuple[ReviewOut, bool]:
    """Store a review with its spam evaluation. Returns (review, created).

    Idempotent: an identical retry returns the stored review with created=False.
    """
    text_norm = rules.normalize_text(review.text)
    with connection() as conn:
        # IMMEDIATE takes the write lock up front, so the duplicate lookups
        # and the insert see a consistent view under concurrent ingests.
        conn.execute("BEGIN IMMEDIATE")
        try:
            existing = conn.execute(
                "SELECT * FROM reviews WHERE review_id = ?", (review.review_id,)
            ).fetchone()
            if existing:
                conn.execute("ROLLBACK")
                if _same_payload(existing, review):
                    return _to_out(existing), False
                raise ReviewConflict(review.review_id)

            history = rules.History(
                same_text_other_user=conn.execute(
                    "SELECT 1 FROM reviews WHERE text_norm = ? AND user_id != ? LIMIT 1",
                    (text_norm, review.user_id),
                ).fetchone() is not None,
                same_user_same_product=conn.execute(
                    "SELECT 1 FROM reviews WHERE user_id = ? AND product_id = ? LIMIT 1",
                    (review.user_id, review.product_id),
                ).fetchone() is not None,
            )
            reasons = rules.evaluate(text_norm, history)

            conn.execute(
                "INSERT INTO reviews (review_id, product_id, user_id, rating, text, text_norm,"
                " submitted_at, received_at, is_flagged, flag_reasons)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    review.review_id, review.product_id, review.user_id, review.rating,
                    review.text, text_norm, _ts(review.submitted_at),
                    _ts(datetime.now(timezone.utc)), int(bool(reasons)), json.dumps(reasons),
                ),
            )
            row = conn.execute(
                "SELECT * FROM reviews WHERE review_id = ?", (review.review_id,)
            ).fetchone()
            conn.execute("COMMIT")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    return _to_out(row), True


def get(review_id: str) -> ReviewOut | None:
    with connection() as conn:
        row = conn.execute("SELECT * FROM reviews WHERE review_id = ?", (review_id,)).fetchone()
    return _to_out(row) if row else None


def list_flagged(
    product_id: str | None, user_id: str | None, limit: int, offset: int
) -> tuple[list[ReviewOut], int]:
    where = ["is_flagged = 1"]
    params: list = []
    if product_id is not None:
        where.append("product_id = ?")
        params.append(product_id)
    if user_id is not None:
        where.append("user_id = ?")
        params.append(user_id)
    clause = " AND ".join(where)
    with connection() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM reviews WHERE {clause}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM reviews WHERE {clause}"
            " ORDER BY submitted_at DESC, review_id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
    return [_to_out(r) for r in rows], total
