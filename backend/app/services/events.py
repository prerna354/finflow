"""Publishes transaction updates to Redis so the WebSocket can push them live."""
import json
import logging

from app.core.redis import CHANNEL, redis_client

log = logging.getLogger(__name__)


def txn_to_dict(txn) -> dict:
    return {
        "id": str(txn.id),
        "sender_id": str(txn.sender_id),
        "receiver_id": str(txn.receiver_id),
        "amount": str(txn.amount),
        "currency": txn.currency,
        "status": txn.status,
        "idempotency_key": txn.idempotency_key,
        "fraud_score": txn.fraud_score,
        "fraud_reason": txn.fraud_reason,
        "created_at": txn.created_at.isoformat() if txn.created_at else None,
        "updated_at": txn.updated_at.isoformat() if txn.updated_at else None,
    }


def publish_transaction_event(txn):
    try:
        message = {"type": "transaction_update", "transaction": txn_to_dict(txn)}
        redis_client.publish(CHANNEL, json.dumps(message))
    except Exception:
        log.exception("publish_transaction_event failed")
