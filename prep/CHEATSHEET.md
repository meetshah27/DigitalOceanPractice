# Interview Cheat Sheet — Review Spam Service

## One-line flow
`schemas validates → store locks + looks up facts → rules decide → store inserts → main logs`

## 5-layer request trace (POST /reviews)
1. **Entry** — middleware: X-Request-ID (client's or generated) in a ContextVar, timer. `main.py`
2. **Validation** — Pydantic `ReviewIn`, strict; failure → 422, nothing stored. `schemas.py`
3. **Logic** — normalize text; 4 pure rules return all reasons. `rules.py`
4. **Storage** — `BEGIN IMMEDIATE`; existing id → 200 (same) / 409 (different); look up facts; insert; COMMIT. `store.py`
5. **Exit** — 201 + `is_flagged` + `flag_reasons`; log decision (no text); X-Request-ID header. `main.py`

**45-second answer:**
> "Middleware assigns a request ID so every log line for the request is traceable. Pydantic validates strictly — ID formats, rating as a real integer 1–5, timezone-aware timestamp normalized to UTC, no unknown fields — invalid input is a 422 and never touches the DB. The store opens a SQLite transaction with BEGIN IMMEDIATE, taking the write lock up front. Identical retry → 200, same ID with different payload → 409. Otherwise it looks up two facts — same text from another user, same user and product — and the pure rules module returns a list of reasons. The store inserts and commits, and we return 201 and log the decision without the review text."

## File roles
| File | Job | Key phrase |
|---|---|---|
| `main.py` | HTTP + middleware | "thin endpoints; domain errors → HTTP; sync def for blocking sqlite" |
| `schemas.py` | validation | "strict and declarative; 422 before my code runs" |
| `store.py` | DB + transaction | "BEGIN IMMEDIATE: check + insert atomic, no check-then-act race" |
| `rules.py` | spam policy | "pure functions; store = facts, rules = policy" |
| `db.py` | connection, schema | "connection per call, WAL so reads don't wait on writes" |
| `logging_config.py` | JSON logs | "request_id on every line" |

## Status codes
| Case | Code |
|---|---|
| New review | 201 |
| Same id + same payload (retry) | 200 |
| Same id + different payload | 409 |
| Invalid input / query params | 422 |
| Unknown review id | 404 |
| Crash | 500, generic JSON body + X-Request-ID; details only in logs |

## Validation rules
- IDs: `rev_` / `prod_` / `usr_` + alphanumerics, max 64.
- `rating`: strict int 1–5 (`"5"`, `4.5`, `5.0`, `true` rejected).
- `text`: trimmed at edges (inner spaces kept), 1–5000 chars.
- `submitted_at`: ISO string with timezone → UTC; ≤ 5 min in future; epoch numbers rejected (seconds vs ms ambiguity).
- Extra fields rejected (clients can't send `is_flagged`).
- Separate input/output models: server owns `is_flagged`, `flag_reasons`, `received_at`.

## Rules (all run; every firing reason recorded)
| Reason | Fires | Doesn't fire |
|---|---|---|
| `duplicate_text` | Another user posted same normalized text, ≥ 20 chars | "Great!" twice (too short) |
| `duplicate_product_review` | Same user, same product again | Same user, other product |
| `contains_url` | `http(s)://`, `www.`, `x.com`, emails | "Works well. Battery lasts." |
| `spam_keywords` | "buy now", "click here", "promo code"… (whole words) | "buy nowhere" |

Normalization: NFKC → casefold → collapse whitespace. `"  ＢＵＹ   Now\t"` → `"buy now"`.
Policy change (e.g. flag short duplicates) = change `rules.py` only (`DUPLICATE_TEXT_MIN_LEN`); store unchanged.

## Concepts to name
- **Check-then-act race / TOCTOU** — fix: make check + action one atomic step (one transaction).
- **Keep the critical section small** — normalize before taking the lock.
- **Blocking I/O in `async def` blocks the event loop** → whole server stalls, even /health. Sync `def` runs in a thread pool.
- **Idempotency** — retries are safe after timeouts.
- **Fixed-width UTC timestamps** — text sort = time sort.
- **Bound parameters (`?`)** — no SQL injection; f-string only joins constant clauses.
- **Test doubles (stub)** — monkeypatch `store.ingest` to raise: deterministic, isolates the behavior under test.
- **Mutation check** — weakened BEGIN IMMEDIATE → all 3 concurrency tests failed → tests prove the lock matters.

## Tests (88)
Rules (pure), API (ingest, idempotency, conflict, duplicates, flagged query filters/pagination/ordering), validation matrix, concurrency (10 threads), health + request-id + 500 handling.

## Tradeoffs (chosen vs alternative — when to switch)
| Decision | Alternative gets | Mine gets | Switch when |
|---|---|---|---|
| Flag at ingest | Rule changes apply instantly | Cheap indexed queries, auditable verdict | Rules change often → add re-scoring job |
| Rules | ML: catches paraphrased/new spam | Explainable, no data needed, testable | Labeled data exists + spammers evade |
| SQLite | Postgres: durable, multi-instance, backups | Zero setup/cost | Data must survive restart or >1 instance |
| Sync ingest | Queue: absorbs spikes, slow checks OK | Immediate verdict, simpler | Slow checks or bursty traffic → 202 |
| Offset pagination | Cursor: stable pages, fast deep pages | Simple, jump to page, total | Big lists / continuous paging |
| Strict validation | Lenient: fewer rejects | Bad data fails loudly at edge | — (easy to loosen later, hard to tighten) |
| JSON reasons column | Separate table: filter/analytics by reason | One row, simple | Need filter by reason |
| App Platform | Droplet: persistent disk; K8s: control | Git push → deploy, TLS, health checks | Need disk or fine-grained control |

**Optimizing for:** correctness + explainability in a 3-hour box. **Not** for scale, HA, or adversarial spammers.

## Weaknesses (say them first)
- "amazon.com" mention flagged (URL false positive).
- User updating their own review flagged.
- Evasion: `b u y  n o w`, `example[dot]com`.
- Exact duplicates only; original duplicate never flagged.
- Data resets on redeploy (ephemeral disk); single instance.

## Scaling — what breaks first
1. Storage → Managed Postgres (durable, multi-instance; `INSERT … ON CONFLICT` + row/advisory locks).
2. Spikes/slow checks → queue + workers, API returns 202.
3. Near-duplicates → hash index for exact, MinHash/SimHash for near.
4. Rule changes → re-scoring job keyed on `rules_version`.
5. Adaptive spammers → ML score (text + behavior), trained on moderator labels, shadow mode first.
Always: metrics — ingest rate, latency, flag rate per rule; alerts.

> "First bottleneck is storage: SQLite ties me to one instance and loses data on redeploy → Managed Postgres. Next, a queue to absorb spikes and allow slower checks. For detection: hashed exact duplicates, MinHash for near-duplicates, then an ML score trained on moderator labels, shadow mode first. Per-rule flag-rate metrics throughout."

## Next steps if asked "what would you add?"
`user_burst` rule → configurable thresholds + `rules_version` → moderation `PATCH` (labels = future ML data) → filter by reason + cursor pagination → auth, rate limiting, body size limit → CI.

## SWE I expectations
- Working > impressive. Explain every line you submitted.
- Tradeoffs: 2–3 fluently, both directions + when to switch. Scaling: first two steps confidently.
- Ask clarifying questions; think out loud; name weaknesses; take hints; "I don't know, here's how I'd find out."
- Avoid: buzzwords you can't defend, silence, defensiveness.
- Answer the actual question: finish with the result (status code, which rule fired, exact value).

## Deploy reminders
Smallest Basic instance, **1 container**, port 8080, health check `/health`, autodeploy on `main`. Check cost (≈ $5/mo, not $24). Destroy afterward. Steps: `DEPLOY.md`.
