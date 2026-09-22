# Deploying to DigitalOcean App Platform

Deploy via the web UI, connected to GitHub. Pushes to `main` auto-deploy.

## Cost check (do this first)

The UI defaults to **1 GB RAM × 2 containers ≈ $24/month**. Change it:

| Setting | Value | Why |
|---|---|---|
| Plan | Basic (shared CPU) | Cheapest tier |
| Instance size | Smallest (512 MB / 1 shared vCPU, ≈ $5/month) | Enough for this service |
| Containers | **1** | Required: each container has its own SQLite file, so >1 splits data |

- Billing is hourly, capped at the monthly price. A few days ≈ cents.
- Check **Billing** for free trial credit.
- **Destroy the app when done** (App → Settings → Destroy) to stop billing.

## Steps (web UI)

1. **Apps → Create App → GitHub.** Authorize DigitalOcean; grant access to `meetshah27/DigitalOceanPractice`.
2. Repository `meetshah27/DigitalOceanPractice`, branch `main`, source directory `/`, **Autodeploy on**.
3. Confirm **"Docker build detected"** → build strategy **Dockerfile**. Leave run command empty (Dockerfile `CMD` is used).
4. **Size → Edit:** smallest instance, **1 container** (see cost check above). Verify total ≈ $5/month.
5. **Network:** public HTTP port **8080**.
6. **Environment variables (optional):** `LOG_LEVEL=INFO`. `DB_PATH` is already set in the Dockerfile.
7. **Database:** do not add one (SQLite in container).
8. Region: nearest to you. App name: `review-spam-service` (becomes part of the URL).
9. **Create App.** First build ≈ 3–5 min.
10. After creation: **Settings → web service → Health Checks → Edit** → HTTP, path `/health`, port `8080`.

Alternative to steps 2–8: **Create App → "Import from app spec"** and upload [`.do/app.yaml`](.do/app.yaml). Review the size and region before creating.

## Verify live

```bash
URL=https://<your-app>.ondigitalocean.app

curl -i $URL/health                      # 200 {"status":"ok"}

curl -i -X POST $URL/reviews -H "Content-Type: application/json" -d '{
  "review_id": "rev_1", "product_id": "prod_1", "user_id": "usr_1",
  "rating": 5, "text": "Great product, fast shipping!",
  "submitted_at": "2026-09-21T11:00:00Z"}'      # 201, is_flagged=false

curl -i -X POST $URL/reviews -H "Content-Type: application/json" -d '{
  "review_id": "rev_2", "product_id": "prod_1", "user_id": "usr_2",
  "rating": 5, "text": "Buy now at www.cheap-deals.xyz",
  "submitted_at": "2026-09-21T11:05:00Z"}'      # 201, is_flagged=true

curl -s "$URL/reviews/flagged"             # contains rev_2
```

Also open `$URL/docs` for the interactive Swagger UI (good for demos).

## Logs

App → **Runtime Logs**. One JSON line per request:
```json
{"level": "INFO", "request_id": "…", "msg": "request", "method": "POST", "path": "/reviews", "status": 201, "duration_ms": 3.1}
```
- Search by `request_id` to trace one request; clients can send `X-Request-ID`, and it is echoed back in the response.
- Flag decisions log `review_id` + `flag_reasons` (never review text).
- Build failures: App → **Activity** → failed deployment → build logs.

## Known behavior

- Filesystem is ephemeral: **data resets on every redeploy/restart**. Expected for this demo; upgrade path is DigitalOcean Managed PostgreSQL.
- Single instance only (SQLite).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Health check fails, deploy rolls back | Port mismatch; app must listen on `$PORT` (Dockerfile does) and HTTP port set to 8080 |
| Build fails at `pip install` | Version pin unavailable; check `requirements.txt` |
| Reviews "disappear" | Redeploy/restart (ephemeral disk) or >1 container |
