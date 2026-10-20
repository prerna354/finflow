from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import models  # noqa: F401  (makes Python load our tables)
from app.api.routes import admin, auth, payments, users, websocket
from app.core.config import settings
from app.core.security import hash_password
from app.db.session import Base, SessionLocal, engine
from app.models import User


def seed_admin():
    """Creates the first admin user from ADMIN_EMAIL / ADMIN_PASSWORD in .env (only if missing)."""
    if not (settings.ADMIN_EMAIL and settings.ADMIN_PASSWORD):
        return
    db = SessionLocal()
    try:
        email = settings.ADMIN_EMAIL.lower()
        if not db.query(User).filter(User.email == email).first():
            db.add(
                User(
                    email=email,
                    full_name="FinFlow Admin",
                    hashed_password=hash_password(settings.ADMIN_PASSWORD),
                    role="admin",
                )
            )
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_admin()
    yield


app = FastAPI(title="FinFlow", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(websocket.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "FinFlow API"}
