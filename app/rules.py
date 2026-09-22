"""Spam rules. Pure functions: no I/O.

Facts that need stored data (duplicates) are looked up by the store and
passed in as `History`; the policy of what counts as spam lives here.
"""
import re
import unicodedata
from dataclasses import dataclass

DUPLICATE_TEXT_MIN_LEN = 20

SPAM_KEYWORDS = (
    "buy now",
    "click here",
    "promo code",
    "discount code",
    "limited offer",
    "act now",
    "free money",
    "free gift",
    "earn money",
    "work from home",
    "check out my",
    "visit my",
)

_URL_RE = re.compile(
    r"https?://\S+"
    r"|\bwww\.\S+"
    r"|\b[a-z0-9-]+\.(?:com|net|org|io|co|biz|info|xyz|shop|ru)\b"
    r"|\b[\w.+-]+@[\w-]+\.[\w.-]+\b"
)
_KEYWORD_RE = re.compile(r"\b(?:" + "|".join(re.escape(k) for k in SPAM_KEYWORDS) + r")\b")


@dataclass(frozen=True)
class History:
    same_text_other_user: bool
    same_user_same_product: bool


def normalize_text(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def evaluate(text_norm: str, history: History) -> list[str]:
    reasons = []
    if history.same_text_other_user and len(text_norm) >= DUPLICATE_TEXT_MIN_LEN:
        reasons.append("duplicate_text")
    if history.same_user_same_product:
        reasons.append("duplicate_product_review")
    if _URL_RE.search(text_norm):
        reasons.append("contains_url")
    if _KEYWORD_RE.search(text_norm):
        reasons.append("spam_keywords")
    return reasons
