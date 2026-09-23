# Interview Build Prompts — Data Ingestion & Processing REST API

For the DigitalOcean build session: **3 hours**, Python, **Claude Code in VS Code** on the provided laptop
(Copilot as fallback), **deploy to DigitalOcean** with provided credits, then a **30-min trade-offs discussion**.
Replace `<...>` placeholders. AI tools are explicitly allowed — use them openly, understand every line.

## What they evaluate → where each step scores

| Evaluation area | Scored by steps |
|---|---|
| **Engineering quality** — organization, validation, error handling | 2 Spec, 4 Core |
| **Testing** — structured, automated | 4 Core, 5 Edge cases |
| **Automation & workflow** — consistent delivery, streamlined lifecycle | 3 CI, 6 Deploy |
| **Operational excellence** — observability, configurability, scalability | 3 Scaffold, 5 Ops, 6 Deploy, 7 Trade-offs |
| **30-min discussion** — prioritized, skipped, how to scale | 7 Trade-offs |

## 3-hour timeline

| Time | Step | Done when |
|---|---|---|
| 0:00–0:15 | 1 Clarify + 2 Spec | Spec committed |
| 0:15–0:40 | 3 Scaffold + CI | `/health` local, CI green on GitHub |
| 0:40–1:00 | 6a **First deploy** (skeleton) | Live `/health` = 200 |
| 1:00–1:50 | 4 Core | Endpoints + tests green, auto-deployed |
| 1:50–2:20 | 5 Edge cases + ops (config, readiness, metrics) | Tests green, CI green |
| 2:20–2:40 | 6b Verify live | Smoke tests pass on live URL, logs checked |
| 2:40–3:00 | 7 README trade-offs + final push | Final checklist done |

**Rule:** deploy a thin version early, then deepen. Something live and tested beats something clever and unfinished.
If behind schedule at 2:00 → use the "Running out of time" prompt (section E).

---

## Before the timer starts (laptop setup, ~10 min)

- Ask first: "I'd like to use Claude Code in VS Code — OK to install the extension?" (AI tools are allowed.)
- VS Code → Extensions → install **Claude Code** → sign in with your account. Have your login/2FA ready.
- Check tools: `python --version` (or `py -0`), `git --version`, `gh auth status` (or sign in to GitHub in the browser).
- Open this file: from your secret gist / email / private repo. Keep it in a VS Code tab.
- **Fallback if Claude Code can't be installed:** Copilot Chat in **Agent mode** — paste step 0 at the start of every
  new chat (no CLAUDE.md support there), and point at files with `#file:` / `#codebase`.

## Using Claude Code

- **CLAUDE.md** at the repo root is read automatically in every session → put the step 0 rules there once
  (commit it: shows your AI workflow openly). No need to repeat them per prompt.
- **Plan mode** (Shift+Tab to cycle modes) for "plan before code" steps; approve the plan, then let it edit.
- **Permissions:** approve each command/edit; read diffs before accepting. Don't auto-accept everything.
- Reference files with `@app/main.py`; select code in the editor to ask about it.
- One step per prompt; keep the same conversation so context carries. `/clear` only if context gets messy
  (CLAUDE.md is reloaded; say which step you're on).
- **Verify everything:** package versions, APIs, flags. Tests after every change. `pip show <pkg>` to check versions.
- **Esc** interrupts a run that's going the wrong way.

---

## 0. Session setup — save as CLAUDE.md, then send the first message

**0a. Create `CLAUDE.md` in the repo root with:**
```
I'm in a timed interview (3 hours) for a SWE I role at DigitalOcean.
Task: "<paste task verbatim>". Sample input (if given): <paste>.
Stack: Python 3.11 + FastAPI + Pydantic v2. Storage: <SQLite | Postgres>.
Deploy: DigitalOcean App Platform (Dockerfile, GitHub autodeploy). Repo: <url>.
They evaluate: engineering quality, automated testing, automation/CI, operational excellence
(observability, configurability, scalability).

Working rules for this whole session:
1. Plan before code. For each step, explain the plan in plain words and wait for my "go".
2. Small steps, one idea per commit. Run tests (and the app when relevant) before every push.
3. After each change: what changed, why, how it was verified.
4. Simplest correct design; no speculative features. Explain any new dependency.
5. Never log user content, PII, or secrets. Never return internal error details to clients.
6. All tunable values come from environment config with safe defaults, validated at startup.
7. Keep a README "Decisions & trade-offs" section updated as we go.
```

**0b. First message:**
```
Read CLAUDE.md. Check the environment: Python version (need 3.11), git, gh auth, Docker (optional).
Wait for my next message (step 1).
```

---

## 1. Clarify requirements + identify the task shape

```
Before designing:
1. Restate the task in one sentence: what comes in, what processing happens, what can be queried.
2. Identify the task shape(s): single vs batch ingest; sync vs async processing; per-record rules vs
   aggregation; time-window logic; external API calls; file upload; webhook; update/delete.
3. List clarifying questions for the interviewer, grouped: input (shape, volume, required fields, natural ID?),
   processing rules, query needs, persistence (must data survive restart?), non-goals.
   Give a sensible default for each in case they say "your call".
4. Propose scope for 3 hours: must-have, stretch, explicitly cut.
```

Always ask: natural unique ID? Single or batch? Must data survive restart? Exact definition of <the processing outcome>? Expected volume?

---

## 2. Spec (commit before code) — *engineering quality*

```
Write the spec into README.md:
- functional + non-functional requirements, out of scope
- API table: method, path, success codes, error codes
- input schema with a validation rule per field; output schema (server-owned fields separate from input)
- processing rules as a table: name, when it applies, result
- edge-case decisions: idempotency key, duplicates, timestamps/timezones, empty results, ordering, limits
- configuration table: env var, default, meaning
- storage choice and what happens on restart
Keep it short. Init git, .gitignore, commit, push. Tell me which decisions I must be able to defend.
```

---

## 3. Scaffold + CI — *automation, operational excellence*

**3a. Scaffold**
```
Scaffold the app, nothing more:
- venv on Python 3.11; pinned requirements.txt (runtime) + requirements-dev.txt (pytest, httpx, ruff)
- config module: read env vars with defaults, validate types/ranges at startup, fail fast with a clear error;
  .env.example documenting every variable (no secrets committed)
- GET /health (liveness: process up) and GET /ready (readiness: DB reachable, returns 503 if not)
- request-id middleware: accept X-Request-ID or generate; keep in context; return on every response incl. 500s
- structured JSON logs: one line per request (method, path, status, duration_ms, request_id);
  framework logs routed through the same formatter; log effective non-secret config at startup
- unhandled errors → generic JSON 500 with request id; details only in logs
- DB init at startup; graceful shutdown (close connections)
- Dockerfile (slim base, non-root user, binds $PORT), .dockerignore
- test setup + tests for /health, /ready, request id, 500 handling
Verify: tests pass, server starts, /health and /ready return 200, logs are JSON. Commit + push.
```

**3b. CI (GitHub Actions)**
```
Add .github/workflows/ci.yml, triggered on push and pull_request to main:
- set up Python 3.11 (actions/setup-python, pip cache), install requirements-dev.txt
- lint and format check (ruff check . ; ruff format --check .)
- run the full test suite (pytest -q)
- build the Docker image (docker build .) so a broken Dockerfile fails CI, not the deploy
Add a CI status badge to the README. Push and confirm the run is green; if red, show me the log and the root cause.
Explain how I'd gate deploys on CI (branch protection with required checks + PRs, or deploying from Actions
instead of App Platform autodeploy) — implement only if time allows.
```

---

## 4. Core logic — *engineering quality, testing*

```
Implement the core with this layering (one job per layer):
- schemas    = validation at the edge. Strict: no silent type coercion, extra fields rejected,
               timezone-aware times normalized to UTC, bounded strings/numbers/lists.
- processing = business logic as PURE functions (no I/O, no clock): input + facts → result.
               Deterministic; return all reasons/details, not just a boolean. Thresholds come from config.
- store      = persistence. Looks up the facts processing needs. Check + write in ONE transaction
               (avoid check-then-act races). All values as bound parameters.
- handlers   = thin: validate → store/processing → map domain errors to HTTP (409, 404, 422).
               Use sync `def` endpoints when the DB driver blocks (sqlite3, psycopg sync).
Idempotency: <natural ID | Idempotency-Key header | content hash>. Same key + same payload → 200 with the stored
result; same key + different payload → 409.
Query endpoints: filters, capped limit + offset (or cursor), deterministic ORDER BY with a tiebreaker.
Log each processing decision with IDs and outcome (never raw user content).
Write unit tests for processing and API tests alongside. Run the app and curl each endpoint. Commit + push.
Apply the relevant add-ons from section S.
```

---

## 5. Edge cases, tests, ops hardening — *testing, operational excellence*

**5a. Edge-case tests**
```
Write edge-case tests grouped by:
- validation: each field's strictness and bounds, missing/extra fields, malformed JSON, wrong body type
- timestamps: naive, future, other offsets, numeric epoch
- idempotency: identical retry, conflicting retry
- processing: each rule fires / doesn't fire; boundary values; several rules at once
- queries: filters, pagination bounds, empty results, ordering ties
- text: unicode, emoji, whitespace-only, max length
- concurrency: parallel identical writes, conflicting writes, races on any check-then-write rule
- config: invalid env value fails startup with a clear error
Run the suite 3 times to catch flakiness. Prove the concurrency tests have teeth: temporarily weaken the
transaction, show they fail, restore. If a test exposes a real bug, stop and explain before fixing.
```

**5b. Metrics (if time)**
```
Add GET /metrics (prometheus-client): request count + latency histogram by
route and status, items ingested, processing outcomes by reason/rule, errors. Keep label cardinality low
(no ids as labels). Test that counters move. Explain what I'd alert on.
```

**Reproduce-first bug fix**
```
Bug/gap: <describe>. First reproduce it and show me the output. Then explain the fix plan
(which layer owns it, what changes, trade-offs) and wait for my go. Then implement, add a regression test,
run the full suite, commit + push.
```

---

## 6. Deploy to DigitalOcean App Platform — *automation, operational excellence*

**6a. First deploy (skeleton, early)**
```
Walk me through deploying to App Platform via the web UI: Create App → GitHub → repo, branch main,
autodeploy on → Dockerfile detected → settings. List every setting: instance size (smallest is enough),
container count (1 if storage is local to the container), HTTP port matching the app, health check path
(/ready or /health), env vars from the config table. Also write .do/app.yaml (app spec) matching those settings
and DEPLOY.md with the steps. After it's live: curl /health and /ready on the live URL.
```

**6b. Verify live (after core)**
```
Write scripts/smoke_test.sh (or .py) that takes a base URL and checks: /health, /ready, one valid ingest,
one invalid ingest (422), one query, and the X-Request-ID header. Run it against the live URL.
Then show me how to find one request in the App Platform runtime logs by its request id.
```

Notes: local storage (SQLite/files) is wiped on redeploy — say so in the trade-offs. Cost trap in the UI: defaults
may be 1 GB × 2 containers; pick the smallest size and the right container count.

---

## 7. Trade-offs, skipped items, scaling — *30-min discussion*

```
Update README with:
- "What I prioritized" (and explicitly what I did NOT optimize for)
- "What I skipped and why" (time box) — and what I'd do next, in order
- trade-offs table: decision | chosen | alternative | alternative gets | mine gets | when I'd switch
  (storage, sync vs async processing, write-time vs read-time processing, rules vs ML/external service,
   pagination, validation strictness, deploy gating)
- known weaknesses / false positives / failure modes
- operations: config table, health vs readiness, logs + request id, metrics + what I'd alert on
- scaling path ordered by what breaks first, with the fix for each
- live URL, how to run locally, how CI works
Then give me spoken versions: 15-second "what I prioritized", 15-second "what I skipped",
top 3 trade-offs with "when I'd switch", and a 30-second scaling answer.
```

**Final checklist (last 10 minutes)**
```
Run the final checklist: all tests pass locally and CI is green; live URL responds on /health and /ready;
smoke test passes on live; README has run instructions, live URL, config table, trade-offs, skipped items,
scaling; no secrets or local DB files committed; .do/app.yaml matches the deployed settings. List anything missing.
```

---

## S. Task-shape add-ons (paste the relevant ones with step 4)

**Batch ingest**
```
Batch ingest: all-or-nothing vs per-item results (default: per-item status + errors, overall 200/207).
Cap batch size from config (default 100) → 413/422 beyond. Idempotency per item. Test: mixed valid/invalid,
empty batch, over-limit, duplicate IDs within one batch.
```

**Async processing (slow or heavy work)**
```
Async: POST returns 202 + id with status "pending"; GET status endpoint; background worker (in-process for the
demo, queue in production). Statuses: pending → done | failed with reason. Limited retries; processing must be
idempotent. Test: transitions, failure path, retry idempotency.
```

**Aggregation / stats**
```
Aggregation: define metric, grouping, UTC time buckets. Compute-on-read (simple, fresh) vs precompute on write
(fast reads, write cost). Default: compute-on-read with indexes. Test: empty buckets, boundaries, timezones.
```

**Time-window rules** ("more than N in M minutes")
```
Time windows: event time (payload) vs receive time (server) — choose and justify; handle late/out-of-order
events; count inside the same transaction as the write; N and M from config.
Test: exactly N vs N+1, window boundary, out-of-order, concurrent writes.
```

**External API calls**
```
External calls: timeout on every call, limited retries with backoff, defined behavior when down (503, or store as
"unenriched"). Wrap the client in a small function so tests can stub it; never block the event loop; URL/timeouts
from config. Test: success, timeout, error — all stubbed, no network.
```

**File upload** (CSV/JSON)
```
File upload: size limit from config, content-type check, iterate rows (don't load all), validate per row,
per-row errors with row numbers; partial accept vs reject-all. Test: header-only, mixed bad/good rows,
wrong delimiter/encoding, oversized.
```

**Webhook receiver**
```
Webhook: verify signature (HMAC over the raw body, constant-time compare, secret from env) before parsing;
reject stale timestamps; acknowledge fast, process after; dedupe by event id.
Test: bad signature, replay, duplicate delivery, out-of-order.
```

**Update / delete**
```
Update/delete: PUT vs PATCH; re-run processing on update; soft delete (deleted_at) vs hard; optimistic
concurrency with a version field → 409 on stale version. Test: re-processing, stale version, deleted items
excluded, delete idempotent.
```

**No natural unique ID**
```
No natural ID: server generates a UUID and returns it; accept an Idempotency-Key header and store key → response.
Test: same key replay → same response; same key with different payload → 409.
```

---

## Python quick reference (proven in the practice project)

| Concern | Use | Notes |
|---|---|---|
| HTTP | FastAPI + uvicorn | `/docs` gives a free Swagger UI for the demo |
| Validation | Pydantic v2 | `ConfigDict(extra="forbid")`, `Field(strict=True, ge=, le=)`, `StringConstraints`, `AwareDatetime`, `field_validator(mode="before")` |
| Config | `os.getenv` in `app/config.py` (or `pydantic-settings`) | Validate at import/startup; fail fast |
| Request id | middleware + `contextvars.ContextVar` | Reset in `finally` |
| Logging | stdlib `logging` + JSON formatter | Route `uvicorn` / `uvicorn.error` through it; disable `uvicorn.access` |
| SQLite | stdlib `sqlite3`, `isolation_level=None`, `BEGIN IMMEDIATE`, WAL | Connection per call; sync `def` endpoints |
| Tests | pytest + `fastapi.testclient.TestClient`, `monkeypatch`, `tmp_path` | `pytest.ini`: `pythonpath = .`, `testpaths = tests` |
| Lint | ruff | `ruff check .`, `ruff format --check .` |
| Metrics | prometheus-client | Low-cardinality labels only |
| Docker | `python:3.11-slim`, non-root user | `CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]` |

Local commands:
```
py -3.11 -m venv .venv            # macOS/Linux: python3.11 -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload --port 8080
pytest -q
```

---

## U. Understanding prompts (use anytime)

**Code tour**
```
Give me a code tour in request order, one file per stop: key lines with line numbers, why they're written that
way, an interview-ready sentence, one check question. Wait for my answer before the next stop.
```

**Trace one request**
```
Trace one <METHOD /path> request through 5 layers — entry (middleware), validation, logic, storage,
exit (status + logs) — with file:line for each. Then a 45-second spoken version.
```

**Explain a line**
```
Explain <file:line>: what it does, what breaks if removed, how I'd say it in an interview.
```

**Discussion prep (use before the 30-min session)**
```
Act as the interviewer for the 30-minute trade-offs discussion. Ask one question at a time: what I prioritized,
what I skipped, a specific trade-off, how I'd scale to 10x/100x, how I'd know it's broken in production
(observability), how I'd change a config safely, how CI/CD protects main. After each answer: what landed,
what's missing, a stronger version.
```

---

## E. Emergency prompts

**Interviewer asks for a live change** ("add X")
```
The interviewer asked: "<request>". Before coding: which layer owns this (schemas / processing / store / handlers /
config)? Smallest correct change? Which tests change or get added? Plan in 3 bullets I can say out loud first.
```

**Tests or CI fail**
```
<Tests | CI> fail: <paste output>. Find the root cause (don't patch symptoms). Tell me the cause in one sentence
before changing anything.
```

**Deploy fails**
```
Deploy failed. Build/runtime logs: <paste>. Diagnose: build, port/$PORT, health check path, missing env var,
dependency, or runtime crash? Give the fix and how to confirm it.
```

**AI made a wrong/large change**
```
Undo your last change (show me the git diff first). Then redo it as the smallest change that does only <X>.
```

**Blanked on a question**
```
The interviewer asked: "<question>". Give me an answer structure (3 bullets) using what we built — I'll say it
in my own words.
```

**Running out of time**
```
<N> minutes left. What's the minimum to finish so the service works end to end, CI is green, it's deployed,
and I can explain it? List what to cut and what to say about each cut item in "What I skipped".
```
