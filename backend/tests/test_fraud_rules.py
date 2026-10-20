from decimal import Decimal

from app.services.fraud_rules import decide_status, score_transaction

DAYTIME = 14
OLD_ACCOUNT = 500  # hours


def test_small_payment_is_approved():
    score, reasons = score_transaction(Decimal("500"), 0, OLD_ACCOUNT, DAYTIME)
    assert score == 0 and reasons == []
    assert decide_status(score) == "APPROVED"


def test_large_payment_alone_is_still_approved():
    score, _ = score_transaction(Decimal("60000"), 0, OLD_ACCOUNT, DAYTIME)
    assert score == 30
    assert decide_status(score) == "APPROVED"


def test_many_quick_payments_are_flagged():
    score, reasons = score_transaction(Decimal("500"), 5, OLD_ACCOUNT, DAYTIME)
    assert score == 40
    assert decide_status(score) == "FLAGGED"
    assert any("last minute" in r for r in reasons)


def test_night_plus_large_amount_is_flagged():
    score, _ = score_transaction(Decimal("55000"), 0, OLD_ACCOUNT, 3)
    assert score == 45
    assert decide_status(score) == "FLAGGED"


def test_new_account_with_very_high_amount_is_rejected():
    score, _ = score_transaction(Decimal("120000"), 0, 2, DAYTIME)
    assert score == 70
    assert decide_status(score) == "REJECTED"


def test_score_never_goes_above_100():
    score, _ = score_transaction(Decimal("999999"), 10, 1, 2)
    assert score == 100
