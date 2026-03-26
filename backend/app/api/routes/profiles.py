"""
GET  /api/v1/profiles           — list all available strategy profiles
GET  /api/v1/profiles/active    — get current user's active profile
PUT  /api/v1/profiles/active    — set user's active profile
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.profiles.manager import profile_manager

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


@router.get("")
async def list_profiles():
    """Return all available strategy profiles."""
    return {"profiles": profile_manager.list_profiles()}


@router.get("/active")
async def get_active_profile(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user_id = user.get("sub") or user.get("id") or user.get("user_id") or ""
    result = await db.execute(select(User).where(User.id == user_id))
    db_user = result.scalar_one_or_none()

    slug = db_user.active_profile if db_user else "balanced"
    profile = profile_manager.get_profile(slug)
    return {"profile": profile.to_dict()}


class SetProfileRequest(BaseModel):
    profile: str


@router.put("/active")
async def set_active_profile(
    body: SetProfileRequest,
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate profile exists
    available = [p["slug"] for p in profile_manager.list_profiles()]
    if body.profile not in available:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown profile '{body.profile}'. Available: {available}",
        )

    user_id = user.get("sub") or user.get("id") or user.get("user_id") or ""
    result = await db.execute(select(User).where(User.id == user_id))
    db_user = result.scalar_one_or_none()

    if db_user:
        db_user.active_profile = body.profile
        await db.commit()

    profile = profile_manager.get_profile(body.profile)
    return {"profile": profile.to_dict()}
