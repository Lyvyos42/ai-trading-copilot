"""
POST /api/v1/auth/register  — create account
POST /api/v1/auth/token     — login, return JWT
GET  /api/v1/auth/me        — current user info
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import hash_password, verify_password, create_access_token, get_current_user_id, decode_token, decode_token_async
from fastapi.security import OAuth2PasswordBearer as _Bearer
_oauth2 = _Bearer(tokenUrl="/api/v1/auth/token", auto_error=False)
from app.config import settings
from app.db.database import get_db
from app.models.user import User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    tier: str


@router.post("/register", status_code=201)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=body.email, hashed_password=hash_password(body.password), tier="free")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": str(user.id), "email": user.email, "tier": user.tier}


@router.post("/token", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == form.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(
        {"sub": str(user.id), "tier": user.tier},
        timedelta(minutes=settings.access_token_expire_minutes),
    )
    return TokenResponse(access_token=token, tier=user.tier)


@router.get("/me")
async def me(token: str = Depends(_oauth2), db: AsyncSession = Depends(get_db)):
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = await decode_token_async(token)
    user_id = payload.get("sub")
    email   = payload.get("email", "")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        # Auto-create on first Supabase login
        user = User(id=user_id, email=email, hashed_password="", tier="free")
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return {"id": str(user.id), "email": user.email, "tier": user.tier, "is_active": user.is_active}


# ── Admin: promote a user tier ────────────────────────────────────────────────

VALID_TIERS = {"free", "retail", "pro", "enterprise", "admin"}


class PromoteRequest(BaseModel):
    email: str
    tier: str
    secret: str


@router.post("/admin/set-tier")
async def admin_set_tier(body: PromoteRequest, db: AsyncSession = Depends(get_db)):
    if body.secret != settings.admin_secret:
        raise HTTPException(status_code=403, detail="Invalid admin secret")
    if body.tier not in VALID_TIERS:
        raise HTTPException(status_code=400, detail=f"Invalid tier. Choose from: {VALID_TIERS}")
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{body.email}' not found in database. Sign in once first so the account is created.")
    user.tier = body.tier
    await db.commit()
    return {"ok": True, "email": user.email, "tier": user.tier}
