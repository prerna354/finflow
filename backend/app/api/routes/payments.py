import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import AuditLog, Transaction, User
from app.schemas.transaction import PaymentCreate, TransactionOut
from app.services.cache import (
    STATS_CACHE_KEY,
    cache_delete,
    cache_get,
    cache_set,
    payments_cache_key,
)
from app.services.events import publish_transaction_event
from app.workers.tasks import process_transaction

log = logging.getLogger(__name__)
router = APIRouter(prefix="/payments", tags=["Payments"])


def find_existing(db: Session, sender_id, key: str):
    return (
        db.query(Transaction)
        .filter(Transaction.sender_id == sender_id, Transaction.idempotency_key == key)
        .first()
    )


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_payment(
    data: PaymentCreate,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=64),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 1. Same key used before? Return the old payment, do NOT create a new one.
    existing = find_existing(db, current_user.id, idempotency_key)
    if existing:
        if existing.receiver_id != data.receiver_id or existing.amount != data.amount:
            raise HTTPException(
                status_code=409,
                detail="This Idempotency-Key was already used with a different payment",
            )
        response.status_code = status.HTTP_200_OK
        return existing

    # 2. Basic checks
    if data.receiver_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot pay yourself")

    receiver = db.query(User).filter(User.id == data.receiver_id).first()
    if not receiver or not receiver.is_active:
        raise HTTPException(status_code=404, detail="Receiver not found")

    # 3. Save the payment as PENDING and write an audit log in ONE transaction
    txn = Transaction(
        sender_id=current_user.id,
        receiver_id=data.receiver_id,
        amount=data.amount,
        currency=data.currency.upper(),
        status="PENDING",
        idempotency_key=idempotency_key,
    )
    try:
        db.add(txn)
        db.flush()
        db.add(
            AuditLog(
                user_id=current_user.id,
                transaction_id=txn.id,
                action="PAYMENT_CREATED",
                details=f"{txn.amount} {txn.currency} to {txn.receiver_id}",
            )
        )
        db.commit()
    except IntegrityError:
        # Two identical requests arrived at the same moment: keep only the first one
        db.rollback()
        existing = find_existing(db, current_user.id, idempotency_key)
        if existing:
            response.status_code = status.HTTP_200_OK
            return existing
        raise

    db.refresh(txn)

    # 4. Clear old cached lists, tell the screen "PENDING", and start the fraud check in the background
    cache_delete(payments_cache_key(txn.sender_id), payments_cache_key(txn.receiver_id), STATS_CACHE_KEY)
    publish_transaction_event(txn)
    try:
        process_transaction.delay(str(txn.id))
    except Exception:
        log.exception("Could not queue fraud check for %s", txn.id)
    return txn


@router.get("", response_model=list[TransactionOut])
def list_my_payments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    key = payments_cache_key(current_user.id)
    cached = cache_get(key)
    if cached is not None:
        return cached

    rows = (
        db.query(Transaction)
        .filter(
            or_(
                Transaction.sender_id == current_user.id,
                Transaction.receiver_id == current_user.id,
            )
        )
        .order_by(Transaction.created_at.desc())
        .limit(50)
        .all()
    )
    result = [TransactionOut.model_validate(t).model_dump(mode="json") for t in rows]
    cache_set(key, result, ttl=30)
    return result


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_payment(
    transaction_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    txn = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Payment not found")

    is_party = current_user.id in (txn.sender_id, txn.receiver_id)
    if not is_party and current_user.role not in ("admin", "analyst"):
        raise HTTPException(status_code=403, detail="You do not have permission to view this payment")
    return txn
