# Review Spam Service

FastAPI service that ingests user-submitted product reviews, flags potential spam at ingest time, and exposes an endpoint to query flagged reviews.

## Requirements

### Functional
- Ingest a single review per request.
- Evaluate each review against deterministic spam rules at ingest time; store the result with the reasons.
- Query flagged reviews, filterable by `product_id` / `user_id`, paginated, newest first.
- Fetch a single review by id.
- `/health` endpoint for platform health checks.

### Non-functional
- Strict input validation; clear error codes.
- Idempotent ingest (safe client retries).
- Structured logs with a request id; flag decisions logged with reasons (review text never logged).
- Deployed on DigitalOcean App Platform.

### Out of scope (for now)
Batch ingest, authentication, rate limiting, re-scoring existing reviews when rules change.

## API

| Method | Path | Success | Errors |
|---|---|---|---|
| POST | `/reviews` | `201` created, `200` identical retry | `409` same `review_id`, different payload; `422` invalid |
| GET | `/reviews/flagged` | `200` | `422` invalid query params |
| GET | `/reviews/{review_id}` | `200` | `404` |
| GET | `/health` | `200` | — |

### Input schema (`POST /reviews`)
```json
{
  "review_id": "rev_5521",
  "product_id": "prod_88",
  "user_id": "usr_301",
  "rating": 5,
  "text": "Great product, fast shipping!",
  "submitted_at": "2026-09-21T11:00:00Z"
}
```

| Field | Rule |
|---|---|
| `review_id` | `^rev_[A-Za-z0-9]+$`, max 64 chars |
| `product_id` | `^prod_[A-Za-z0-9]+$`, max 64 chars |
| `user_id` | `^usr_[A-Za-z0-9]+$`, max 64 chars |
| `rating` | strict integer 1–5 (`"5"`, `4.5`, `true` rejected) |
| `text` | trimmed; 1–5000 chars |
| `submitted_at` | ISO 8601 with timezone; normalized to UTC; not more than 5 min in the future |
| extra fields | rejected |

### Output schema (review)
Input fields plus:
```json
{
  "is_flagged": true,
  "flag_reasons": ["contains_url", "spam_keywords"],
  "received_at": "2026-09-21T11:00:02Z"
}
```

### Flagged query
`GET /reviews/flagged?product_id=&user_id=&limit=20&offset=0`
- `limit` 1–100 (default 20), `offset` ≥ 0.
- Ordered by `submitted_at` desc, then `review_id` desc (deterministic).
- Response: `{ "items": [...], "total": N, "limit": 20, "offset": 0 }`.

## Spam rules

Rules are pure functions evaluated at ingest. A review is flagged if any rule fires; all firing rules are recorded in `flag_reasons`.

Text normalization (used by rules): Unicode NFKC, casefold, collapse whitespace, trim.

| Reason | Fires when |
|---|---|
| `duplicate_text` | Normalized text (≥ 20 chars) already exists from a **different** user |
| `duplicate_product_review` | Same user already has a review for the same product |
| `contains_url` | Text contains a URL (`http(s)://`, `www.`, bare domain) or email address |
| `spam_keywords` | Text contains a phrase from the spam keyword list (word-boundary match) |

## Edge cases and decisions

- **Idempotency:** same `review_id` + identical payload → `200` with stored review (no re-evaluation). Different payload → `409`.
- **Duplicate ordering:** only the later-ingested review is flagged; the original may be genuine.
- **Short generic text** ("Great!") is excluded from `duplicate_text` by the 20-char minimum to avoid false positives.
- **Timestamps:** naive datetimes rejected; all stored as UTC. Numeric epoch values rejected (seconds vs. milliseconds is ambiguous). Retries with the same instant in a different offset are treated as identical.
- **Consistency:** rule checks and insert run in one SQLite transaction.
- **Privacy:** review text is never logged.

## Storage

SQLite (stdlib `sqlite3`). On App Platform the filesystem is ephemeral, so data resets on redeploy/restart; the service runs as a single instance. Upgrade path: DigitalOcean Managed PostgreSQL.
