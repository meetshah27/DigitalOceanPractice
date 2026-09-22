import pytest

from app.rules import History, evaluate, normalize_text

CLEAN = History(same_text_other_user=False, same_user_same_product=False)


def reasons(text: str, history: History = CLEAN) -> list[str]:
    return evaluate(normalize_text(text), history)


def test_normalize_text():
    assert normalize_text("  Great\n\tPRODUCT   here ") == "great product here"
    # NFKC folds full-width characters.
    assert normalize_text("ＢＵＹ ＮＯＷ") == "buy now"


def test_clean_review_not_flagged():
    assert reasons("Great product, fast shipping!") == []


@pytest.mark.parametrize("text", [
    "see http://example.com",
    "see https://example.com/x",
    "go to www.example.org",
    "cheap at deals.xyz today",
    "mail me at spam@example.com",
])
def test_contains_url(text):
    assert reasons(text) == ["contains_url"]


def test_url_rule_ignores_ordinary_periods():
    assert reasons("Works well. Battery lasts all day.") == []


@pytest.mark.parametrize("text", ["BUY NOW before it's gone", "click here", "use promo code X"])
def test_spam_keywords(text):
    assert reasons(text) == ["spam_keywords"]


def test_keywords_match_whole_words_only():
    assert reasons("I like to buy nowhere else") == []


def test_duplicate_text_requires_min_length():
    dup = History(same_text_other_user=True, same_user_same_product=False)
    assert reasons("Great!", dup) == []
    assert reasons("Great product, fast shipping!", dup) == ["duplicate_text"]


def test_duplicate_product_review():
    dup = History(same_text_other_user=False, same_user_same_product=True)
    assert reasons("Great!", dup) == ["duplicate_product_review"]


def test_multiple_reasons_all_reported():
    both = History(same_text_other_user=True, same_user_same_product=True)
    assert reasons("Buy now at www.cheap-deals.xyz please", both) == [
        "duplicate_text", "duplicate_product_review", "contains_url", "spam_keywords",
    ]
