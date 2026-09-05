"""
GET  /api/v1/portfolio/positions  — current open positions with P&L
POST /api/v1/portfolio/execute    — open a paper position from a signal
POST /api/v1/portfolio/close/{id} — close a position (paper)
GET  /api/v1/portfolio/summary    — portfolio-level stats
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user_id
from app.db.database import get_db
from app.models.portfolio import Position
from app.models.signal import Signal

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


class ExecuteRequest(BaseModel):
    signal_id: str
    quantity: float = 1.0
    is_paper: bool = True


@router.get("/positions")
async def get_positions(
    status: str = "OPEN",
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    query = select(Position).where(
        Position.user_id == user_id,
        Position.status == status,
    )
    result = await db.execute(query)
    positions = result.scalars().all()

    enriched = []
    for p in positions:
        # Real spot. When the feed is down the position reports its entry with
        # current_price None and pnl None, so the UI shows an em dash rather
        # than an invented gain.
        live = await _live_price(p.ticker)
        pnl = _calc_pnl(p.direction, p.entry_price, live, p.quantity) if live is not None else None
        enriched.append({
            "id": str(p.id),
            "ticker": p.ticker,
            "asset_class": p.asset_class,
            "direction": p.direction,
            "entry_price": p.entry_price,
            "current_price": live,
            "quantity": p.quantity,
            "stop_loss": p.stop_loss,
            "take_profit_1": p.take_profit_1,
            # None, not 0. A position whose price could not be fetched has an
            # UNKNOWN P&L, and zero would read as flat.
            "unrealized_pnl": round(pnl, 2) if pnl is not None else None,
            "unrealized_pnl_pct": (round(pnl / (p.entry_price * p.quantity) * 100, 2)
                                   if pnl is not None and p.entry_price and p.quantity else None),
            "price_unavailable": live is None,
            "status": p.status,
            "opened_at": (p.opened_at.isoformat() + "Z") if p.opened_at else None,
            "is_paper": p.is_paper,
        })
    return enriched


@router.post("/execute", status_code=201)
async def execute_position(
    body: ExecuteRequest,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    result = await db.execute(select(Signal).where(Signal.id == body.signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    position = Position(
        user_id=user_id,
        signal_id=signal.id,
        ticker=signal.ticker,
        asset_class=signal.asset_class,
        direction=signal.direction,
        entry_price=signal.entry_price,
        quantity=body.quantity,
        stop_loss=signal.stop_loss,
        take_profit_1=signal.take_profit_1,
        is_paper=body.is_paper,
    )
    db.add(position)

    # Mark signal as executed
    signal.status = "EXECUTED"
    await db.commit()
    await db.refresh(position)

    return {"id": str(position.id), "ticker": position.ticker, "status": "OPEN", "is_paper": position.is_paper}


@router.post("/close/{position_id}")
async def close_position(
    position_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    # Check if admin — admins can close any position
    from app.models.user import User
    _u = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    is_admin = (_u.tier if _u else "free") == "admin"

    if is_admin:
        result = await db.execute(select(Position).where(Position.id == position_id))
    else:
        result = await db.execute(
            select(Position).where(Position.id == position_id, Position.user_id == user_id)
        )
    position = result.scalar_one_or_none()
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    if position.status != "OPEN":
        raise HTTPException(status_code=400, detail="Position is not open")

    close_price = await _live_price(position.ticker)
    if close_price is None:
        # Refuse rather than book a made-up realised result. This value is
        # written to realized_pnl and synced back to the linked signal as a
        # WIN or LOSS, so a guess here corrupts the track record permanently.
        raise HTTPException(
            status_code=503,
            detail=(f"No live price for {position.ticker}, so this position cannot be "
                    f"closed at a real level. Try again when the feed recovers."),
        )
    realized = _calc_pnl(position.direction, position.entry_price, close_price, position.quantity)

    position.status = "CLOSED"
    position.closed_at = datetime.utcnow()
    position.close_price = close_price
    position.realized_pnl = round(realized, 2)

    # Sync outcome to linked signal
    if position.signal_id:
        sig_result = await db.execute(select(Signal).where(Signal.id == position.signal_id))
        linked_signal = sig_result.scalar_one_or_none()
        if linked_signal and linked_signal.status in ("ACTIVE", "EXECUTED"):
            linked_signal.outcome = "WIN" if realized > 0 else "LOSS"
            linked_signal.status = linked_signal.outcome
            linked_signal.exit_price = close_price
            linked_signal.pnl_pct = round(
                realized / (position.entry_price * position.quantity) * 100, 4
            ) if position.entry_price and position.quantity else 0
            linked_signal.resolved_at = datetime.utcnow()

    await db.commit()

    return {
        "id": str(position.id),
        "ticker": position.ticker,
        "close_price": close_price,
        "realized_pnl": position.realized_pnl,
        "status": "CLOSED",
    }


@router.get("/summary")
async def portfolio_summary(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    uid = user_id

    open_result = await db.execute(
        select(func.count()).where(Position.user_id == uid, Position.status == "OPEN")
    )
    open_count = open_result.scalar()

    closed_result = await db.execute(
        select(func.sum(Position.realized_pnl)).where(
            Position.user_id == uid, Position.status == "CLOSED"
        )
    )
    total_realized = closed_result.scalar() or 0.0

    total_result = await db.execute(select(func.count()).where(Position.user_id == uid))
    total_trades = total_result.scalar()

    win_result = await db.execute(
        select(func.count()).where(
            Position.user_id == uid,
            Position.status == "CLOSED",
            Position.realized_pnl > 0,
        )
    )
    win_count = win_result.scalar()

    closed_count = total_trades - open_count
    win_rate = round(win_count / closed_count * 100, 1) if closed_count > 0 else 0.0

    return {
        "open_positions": open_count,
        "total_trades": total_trades,
        "win_rate_pct": win_rate,
        "total_realized_pnl": round(total_realized, 2),
        "equity": round(100_000 + total_realized, 2),  # Paper account base $100k
        "paper_mode": True,
    }


async def _live_price(ticker: str) -> float | None:
    """Real spot price for a paper position, or None if the feed is down.

    This replaces _simulate_price, which invented one:

        rng   = random.Random(sum(ord(c) for c in ticker))
        drift = rng.gauss(0.0001, 0.015) * (seconds / 86400)
        return entry * (1 + drift)

    Paper trading exists to tell you whether the signals work. A position
    whose current price is a random walk seeded by the spelling of its ticker
    produces a P&L, an equity curve and a realised result that are all
    fiction - and closing a position wrote that fiction into realized_pnl and
    synced a WIN or LOSS back onto the linked signal, which is the very
    number the track record is built from.

    Paper money is fine. Paper prices are not.
    """
    from app.data.market_data import _fetch_tv_ta_spot, _fetch_rest_spot_price, resolve_ticker
    try:
        price = await _fetch_tv_ta_spot(ticker)
        if price and price > 0:
            return float(price)
        price = await _fetch_rest_spot_price(resolve_ticker(ticker))
        return float(price) if price and price > 0 else None
    except Exception:
        return None


def _calc_pnl(direction: str, entry: float, current: float, qty: float) -> float:
    if direction == "LONG":
        return (current - entry) * qty
    return (entry - current) * qty
