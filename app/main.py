import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app import config
from app.db import init_db
from app.logging_config import request_id_var, setup_logging

setup_logging(config.LOG_LEVEL)
log = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log.info("startup", extra={"fields": {"db_path": config.DB_PATH}})
    yield


app = FastAPI(title="Review Spam Service", lifespan=lifespan)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    token = request_id_var.set(request_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
        log.info(
            "request",
            extra={"fields": {
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start) * 1000, 1),
            }},
        )
        response.headers["X-Request-ID"] = request_id
        return response
    except Exception:
        log.exception("unhandled error", extra={"fields": {"path": request.url.path}})
        raise
    finally:
        request_id_var.reset(token)


@app.get("/health")
def health():
    return {"status": "ok"}
