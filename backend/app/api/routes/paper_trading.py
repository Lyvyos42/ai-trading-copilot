"""
Paper trading endpoints — powered by Alpaca paper trading API.
Only available to paid tier users with Alpaca configured.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from app.auth.jwt import get_current_user
from app.data.alpaca_provider import (
    is_configured,
    get_account,
    submit_order,
    get_positions,
    get_order_history,
)
from app.db.database import get_db
from app.models.user import User

router = APIRouter(prefix="/api/v1/paper-trading", tags=["paper-trading"])

_PAID_TIERS = {"retail", "pro", "enterprise", "admin"}


def _require_alpaca():
    if not is_configured():
        raise HTTPException(status_code=503, detail="Paper trading not configured")


async def _require_paid(user: dict, db: AsyncSession):
    user_id = user.get("sub", "")
    tier = user.get("tier", "") or ""
    if tier not in _PAID_TIERS:
        result = await db.execute(select(User).where(User.id == user_id))
        db_user = result.scalar_one_or_none()
        tier = db_user.tier if db_user else "free"
    if tier not in _PAID_TIERS:
        raise HTTPException(status_code=403, detail="Paper trading requires a paid subscription")


class OrderRequest(BaseModel):
    symbol: str
    qty: float
    side: str  # "buy" or "sell"
    order_type: str = "market"
    time_in_force: str = "day"


@router.get("/account")
async def paper_account(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    _require_alpaca()
    await _require_paid(user, db)
    account = await get_account()
    if account is None:
        raise HTTPException(status_code=502, detail="Failed to fetch Alpaca account")
    return account


@router.post("/orders")
async def paper_order(req: OrderRequest, db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    _require_alpaca()
    await _require_paid(user, db)
    if req.side not in ("buy", "sell"):
        raise HTTPException(status_code=400, detail="side must be 'buy' or 'sell'")
    result = await submit_order(req.symbol, req.qty, req.side, req.order_type, req.time_in_force)
    if result is None:
        raise HTTPException(status_code=502, detail="Failed to submit order")
    return result


@router.get("/positions")
async def paper_positions(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    _require_alpaca()
    await _require_paid(user, db)
    positions = await get_positions()
    if positions is None:
        raise HTTPException(status_code=502, detail="Failed to fetch positions")
    return positions


@router.get("/orders")
async def paper_orders(db: AsyncSession = Depends(get_db), user: dict = Depends(get_current_user)):
    _require_alpaca()
    await _require_paid(user, db)
    orders = await get_order_history()
    if orders is None:
        raise HTTPException(status_code=502, detail="Failed to fetch orders")
    return orders
