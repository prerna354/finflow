import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models import AuditLog, Transaction, User
from app.schemas.transaction import TransactionOut
from app.schemas.user import UserOut
from app.services.cache import STATS_CACHE_KEY, cache_get, cache_set

router = APIRouter(prefix="/admin", tags=["Admin"])


class AuditLogOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    transaction_id: uuid.UUID | None
    action: str
    details: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleUpdate(BaseModel):
    role: str  # customer / analyst / admin


@router.get("/transactions", response_model=list[TransactionOut])
def all_transactions(
    status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "analyst")),
):
    query = db.query(Transaction)
    if status:
        query = query.filter(Transaction.status == status.upper())
    return query.order_by(Transaction.created_at.desc()).limit(100).all()


@router.get("/stats")
def stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "analyst")),
):
    cached = cache_get(STATS_CACHE_KEY)
    if cached is not None:
        return cached

    rows = (
        db.query(Transaction.status, func.count(Transaction.id), func.coalesce(func.sum(Transaction.amount), 0))
        .group_by(Transaction.status)
        .all()
    )
    by_status = {s: {"count": c, "amount": str(a)} for s, c, a in rows}
    result = {"total": sum(v["count"] for v in by_status.values()), "by_status": by_status}
    cache_set(STATS_CACHE_KEY, result, ttl=10)
    return result


@router.get("/audit-logs", response_model=list[AuditLogOut])
def audit_logs(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin")),
):
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100).all()


@router.patch("/users/{user_id}/role", response_model=UserOut)
def change_role(
    user_id: uuid.UUID,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    if data.role not in ("customer", "analyst", "admin"):
        raise HTTPException(status_code=400, detail="Role must be customer, analyst or admin")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_role = user.role
    user.role = data.role
    db.add(AuditLog(user_id=admin.id, action="ROLE_CHANGED", details=f"{user.email}: {old_role} -> {data.role}"))
    db.commit()
    db.refresh(user)
    return user
