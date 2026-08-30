"""
POST /api/v1/signals/evaluate — resolve ACTIVE signals against their price path.
Walks the OHLC bars between creation and expiry and closes on the first barrier
the price actually crossed.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user
from app.db.database import get_db
from app.services.signal_resolver import resolve_open_signals

router = APIRouter(prefix="/api/v1/signals", tags=["evaluation"])


@router.post("/evaluate")
async def evaluate_signals(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resolve this user's ACTIVE signals against their actual price path.

    Delegates to the shared resolver so this endpoint, the signals list and the
    scheduled sweep all score a signal the same way. The previous version
    compared a single spot price, which could not see a target that was touched
    and given back, and read any momentary excursion through the nearer stop as
    a loss.
    """
    user_id = user.get("sub") or user.get("id") or user.get("user_id")
    return await resolve_open_signals(db, user_id=user_id)
