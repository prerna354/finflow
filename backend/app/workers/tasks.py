import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func

from app import models  # noqa: F401  (loads all tables)
from app.db.session import SessionLocal
from app.models import AuditLog, Transaction, User
from app.services.cache import cache_delete, payments_cache_key, STATS_CACHE_KEY
from app.services.events import publish_transaction_event
from app.services.fraud_rules import decide_status, score_transaction
from app.workers.celery_app import celery_app

IST = timezone(timedelta(hours=5, minutes=30))


@celery_app.task(name="process_transaction", bind=True, autoretry_for=(Exception,),
                 retry_backoff=True, max_retries=3)
def process_transaction(self, transaction_id: str):
    """Runs in the background: checks a PENDING payment for fraud and updates its status."""
    db = SessionLocal()
    try:
        txn = db.get(Transaction, uuid.UUID(transaction_id))
        if txn is None or txn.status != "PENDING":
            return  # already processed (safe if the task runs twice)

        sender = db.get(User, txn.sender_id)
        now = datetime.now(timezone.utc)

        recent_count = (
            db.query(func.count(Transaction.id))
            .filter(
                Transaction.sender_id == txn.sender_id,
                Transaction.id != txn.id,
                Transaction.created_at >= now - timedelta(seconds=60),
            )
            .scalar()
        )

        created = sender.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        account_age_hours = (now - created).total_seconds() / 3600

        score, reasons = score_transaction(
            amount=txn.amount,
            recent_count=recent_count,
            account_age_hours=account_age_hours,
            local_hour=now.astimezone(IST).hour,
        )
        new_status = decide_status(score)

        txn.fraud_score = score
        txn.fraud_reason = "; ".join(reasons) if reasons else "No risk found"
        txn.status = new_status
        db.add(
            AuditLog(
                user_id=txn.sender_id,
                transaction_id=txn.id,
                action={"APPROVED": "PAYMENT_APPROVED", "FLAGGED": "FRAUD_FLAGGED",
                        "REJECTED": "PAYMENT_REJECTED"}[new_status],
                details=f"score={score}; {txn.fraud_reason}",
            )
        )
        db.commit()
        db.refresh(txn)

        cache_delete(payments_cache_key(txn.sender_id), payments_cache_key(txn.receiver_id), STATS_CACHE_KEY)
        publish_transaction_event(txn)
    finally:
        db.close()
