# Review Spam Service

FastAPI service that ingests user-submitted product reviews, flags potential spam at ingest time, and exposes an endpoint to query flagged reviews.

## Run locally

Requires Python 3.11.

```bash
py -3.11 -m venv .venv                      # macOS/Linux: python3.11 -m venv .venv
.venv/Scripts/activate                      # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt

uvicorn app.main:app --reload --port 8080   # http://localhost:8080/docs
pytest -q                                   # full test suite
```

Config via env vars: `DB_PATH` (default `data/reviews.db`), `LOG_LEVEL` (default `INFO`).
Deployment: see [DEPLOY.md](DEPLOY.md).

## Layout

```
app/
  main.py            routes, request-id + logging middleware
  schemas.py         Pydantic input/output models (validation lives here)
  rules.py           spam rules: pure functions, no I/O
  store.py           SQLite access: ingest transaction, queries
  db.py              connection + schema
  logging_config.py  JSON log formatter
tests/
  test_rules.py  test_api.py  test_validation.py  test_concurrency.py  test_health.py
```

Flow of `POST /reviews`: `schemas` validates → `store` opens a write transaction, looks up duplicate facts → `rules.evaluate` decides → `store` inserts → `main` logs the decision.

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

## Tradeoffs

**What this optimizes for right now:** correctness and explainability under a 3-hour time box. Every flag carries its reasons, rules are deterministic and unit-tested, input is strictly validated, and there is one process and one file to operate. It does *not* optimize for scale, availability, or catch rate against adversarial spammers.

| Decision | Chosen | Alternative | What the alternative gets that this doesn't | What this gets that the alternative doesn't |
|---|---|---|---|---|
| When to flag | At ingest | At query time | Rule changes apply to all reviews instantly; no stale flags | Cheap, indexed queries; decision fixed at write time and auditable; flag logged once |
| Detection | Deterministic rules | ML classifier / 3rd-party spam API | Catches novel and paraphrased spam; learns from labels | Explainable reasons, zero training data, predictable, trivially testable, no external latency or cost |
| Storage | SQLite | Managed PostgreSQL | Durability across deploys, multiple instances, backups, concurrent writers | No extra service or cost, zero setup, one file; stdlib only |
| Ingest path | Synchronous | Queue + async worker | Absorbs spikes; slow/expensive checks don't block clients | Client gets the verdict in the response; no queue to run; simpler failure modes |
| Pagination | `limit`/`offset` | Cursor (keyset) | Stable pages while new reviews arrive; constant cost at deep pages | Simple for clients, supports jumping to a page, easy `total` |
| Validation | Strict (reject `"5"`, naive times, extra fields, epochs) | Lenient coercion | Accepts more client variants without errors | Bad data fails loudly at the boundary instead of silently corrupting rules/ordering |
| Retries | Idempotent on `review_id` (200 / 409) | Always 409 on existing id | Simpler | Safe client retries after timeouts; real conflicts still surfaced |
| Flag reasons | JSON column | Separate `review_flags` table | Indexed filter by reason; per-rule analytics in SQL | One row per review, simpler writes and reads |
| Hosting | App Platform | Droplet / Kubernetes | Persistent disk (Droplet); fine-grained control and scaling (K8s) | Git push → deploy, managed TLS, health checks, logs; no server admin |

**Known rule weaknesses (accepted for now):**
- `contains_url` flags legitimate mentions like "bought on amazon.com" (false positive).
- `duplicate_product_review` flags a user who legitimately updates their review.
- Keyword and URL rules are easy to evade (`b u y  n o w`, `example[dot]com`).
- Duplicate detection is exact (after normalization); near-duplicates slip through.
- Only the later duplicate is flagged; the original is never re-flagged.

## Future work and scalability

**Next (small, high value)**
- `user_burst` rule: too many reviews from one user in a time window.
- Thresholds and keyword list via env/config; `rules_version` stored per review so every verdict is traceable to the rule set that produced it.
- Moderation workflow: `PATCH /reviews/{id}` to mark flagged reviews as `confirmed_spam` / `cleared`; these labels become training data later.
- Filter flagged query by `reason`; cursor pagination.
- Authentication (API keys) and rate limiting on ingest; request body size limit.
- CI (GitHub Actions: lint + tests on every push).

**Scale**
- **Storage:** Managed PostgreSQL → durable data, multiple app instances, backups. Same schema; the transaction becomes a unique constraint + `INSERT ... ON CONFLICT` plus row-level locking or advisory locks for duplicate checks.
- **Throughput:** put a queue (e.g. Redis/Kafka) between the API and a worker pool; API returns `202` with status `pending`; flagged state becomes eventually consistent.
- **Duplicate detection at scale:** exact match via a hash index on `text_norm`; near-duplicates via MinHash/SimHash locality-sensitive hashing instead of scanning.
- **Re-scoring:** background job that re-evaluates existing reviews when rules change, driven by `rules_version`.
- **Smarter detection:** keep rules as a fast first pass; add an ML score (text + user behavior features such as account age, review velocity, rating distribution), trained on moderator labels; run new rules/models in *shadow mode* (log verdicts, don't flag) before enabling.
- **Observability:** metrics for ingest rate, latency, and flag rate *per rule* (a sudden spike means a spam wave or a broken rule); alerts; log shipping.
- **Privacy:** retention policy for review text; avoid logging user content (already enforced).
