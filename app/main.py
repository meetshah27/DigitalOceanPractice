import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from app import config, store
from app.db import init_db
from app.logging_config import request_id_var, setup_logging
from app.schemas import FlaggedPage, ReviewIn, ReviewOut

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
        try:
            response = await call_next(request)
        except Exception:
            # Details go to logs only; the client gets a generic body plus the request id.
            log.exception("unhandled error", extra={"fields": {"path": request.url.path}})
            response = JSONResponse({"detail": "Internal Server Error"}, status_code=500)
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
    finally:
        request_id_var.reset(token)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/reviews", response_model=ReviewOut, status_code=201)
def create_review(review: ReviewIn, response: Response):
    try:
        stored, created = store.ingest(review)
    except store.ReviewConflict:
        log.warning("review_conflict", extra={"fields": {"review_id": review.review_id}})
        raise HTTPException(409, "review_id already exists with a different payload")
    if not created:
        response.status_code = 200
    log.info(
        "review_ingested",
        extra={"fields": {
            "review_id": stored.review_id,
            "product_id": stored.product_id,
            "user_id": stored.user_id,
            "created": created,
            "is_flagged": stored.is_flagged,
            "flag_reasons": stored.flag_reasons,
        }},
    )
    return stored


# Declared before /reviews/{review_id} so "flagged" isn't captured as an id.
@app.get("/reviews/flagged", response_model=FlaggedPage)
def flagged_reviews(
    product_id: Annotated[str | None, Query(max_length=64)] = None,
    user_id: Annotated[str | None, Query(max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    items, total = store.list_flagged(product_id, user_id, limit, offset)
    return FlaggedPage(items=items, total=total, limit=limit, offset=offset)


@app.get("/reviews/{review_id}", response_model=ReviewOut)
def get_review(review_id: str):
    review = store.get(review_id)
    if review is None:
        raise HTTPException(404, "review not found")
    return review
