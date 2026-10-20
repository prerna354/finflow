"""Simple, explainable fraud rules.

Each rule adds points to a risk score (0 to 100).
Score 70+  -> REJECTED
Score 40+  -> FLAGGED (needs manual review)
Below 40   -> APPROVED
"""
from decimal import Decimal

HIGH_AMOUNT = Decimal("100000")
LARGE_AMOUNT = Decimal("50000")
NEW_ACCOUNT_AMOUNT = Decimal("10000")
VELOCITY_LIMIT = 5          # other payments by same sender in the last minute
NEW_ACCOUNT_HOURS = 24
NIGHT_HOURS = range(0, 5)   # 12:00 AM to 4:59 AM (India time)
REJECT_AT = 70
FLAG_AT = 40


def score_transaction(amount: Decimal, recent_count: int, account_age_hours: float, local_hour: int):
    score = 0
    reasons = []

    if amount >= HIGH_AMOUNT:
        score += 50
        reasons.append("Very high amount")
    elif amount >= LARGE_AMOUNT:
        score += 30
        reasons.append("Large amount")

    if recent_count >= VELOCITY_LIMIT:
        score += 40
        reasons.append(f"{recent_count} other payments in the last minute")

    if local_hour in NIGHT_HOURS:
        score += 15
        reasons.append("Odd-hour payment (12 AM to 5 AM)")

    if account_age_hours < NEW_ACCOUNT_HOURS and amount >= NEW_ACCOUNT_AMOUNT:
        score += 20
        reasons.append("New account sending a big amount")

    return min(score, 100), reasons


def decide_status(score: int) -> str:
    if score >= REJECT_AT:
        return "REJECTED"
    if score >= FLAG_AT:
        return "FLAGGED"
    return "APPROVED"
