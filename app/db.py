import sqlite3
from pathlib import Path

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
    review_id    TEXT PRIMARY KEY,
    product_id   TEXT NOT NULL,
    user_id      TEXT NOT NULL,
    rating       INTEGER NOT NULL,
    text         TEXT NOT NULL,
    text_norm    TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    received_at  TEXT NOT NULL,
    is_flagged   INTEGER NOT NULL,
    flag_reasons TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_flagged_submitted ON reviews (is_flagged, submitted_at);
CREATE INDEX IF NOT EXISTS ix_text_norm ON reviews (text_norm);
CREATE INDEX IF NOT EXISTS ix_user_product ON reviews (user_id, product_id);
"""


def connect() -> sqlite3.Connection:
    # isolation_level=None: we manage transactions explicitly (BEGIN IMMEDIATE on ingest).
    conn = sqlite3.connect(config.DB_PATH, timeout=5, isolation_level=None)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    Path(config.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
    finally:
        conn.close()
