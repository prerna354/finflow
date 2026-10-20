from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models import User
from app.schemas.user import UserLookup, UserOut

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserOut)
def read_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/lookup", response_model=UserLookup)
def lookup_user(email: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    """Find a receiver by email (returns only id and name)."""
    user = db.query(User).filter(User.email == email.lower(), User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=404, detail="No user with this email")
    return user


@router.get("/admin-only")
def admin_only(current_user: User = Depends(require_roles("admin"))):
    return {"message": f"Welcome admin {current_user.full_name}"}
