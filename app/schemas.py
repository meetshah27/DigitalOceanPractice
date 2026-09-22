from datetime import datetime, timedelta, timezone
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, field_validator

MAX_FUTURE_SKEW = timedelta(minutes=5)

ReviewId = Annotated[str, StringConstraints(pattern=r"^rev_[A-Za-z0-9]+$", max_length=64)]
ProductId = Annotated[str, StringConstraints(pattern=r"^prod_[A-Za-z0-9]+$", max_length=64)]
UserId = Annotated[str, StringConstraints(pattern=r"^usr_[A-Za-z0-9]+$", max_length=64)]


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_id: ReviewId
    product_id: ProductId
    user_id: UserId
    rating: Annotated[int, Field(strict=True, ge=1, le=5)]
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
    submitted_at: AwareDatetime

    @field_validator("submitted_at")
    @classmethod
    def normalize_submitted_at(cls, v: datetime) -> datetime:
        v = v.astimezone(timezone.utc)
        if v > datetime.now(timezone.utc) + MAX_FUTURE_SKEW:
            raise ValueError("submitted_at is in the future")
        return v


class ReviewOut(BaseModel):
    review_id: str
    product_id: str
    user_id: str
    rating: int
    text: str
    submitted_at: datetime
    received_at: datetime
    is_flagged: bool
    flag_reasons: list[str]


class FlaggedPage(BaseModel):
    items: list[ReviewOut]
    total: int
    limit: int
    offset: int
