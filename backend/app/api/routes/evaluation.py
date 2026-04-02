"""
POST /api/v1/signals/evaluate — check all ACTIVE signals against current prices.
Auto-resolves signals where TP1 or SL has been hit.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user
from app.db.database import get_db
from app.models.signal import Signal
from app.data.market_data import fetch_market_data

router = APIRouter(prefix="/api/v1/signals", tags=["evaluation"])


@router.post("/evaluate")
async def evaluate_signals(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check this user's ACTIVE signals and auto-resolve if TP1 or SL hit."""
    user_id = user.get("sub") or user.get("id") or user.get("user_id")
    result = await db.execute(
        select(Signal).where(Signal.status == "ACTIVE", Signal.user_id == user_id)
    )
    active_signals = result.scalars().all()

    evaluated = []
    resolved = []
    errors = []

    for signal in active_signals:
        try:
            market = await fetch_market_data(signal.ticker)
            current_price = market.get("current_price") or market.get("price", 0)
            if not current_price:
                errors.append({"signal_id": str(signal.id), "ticker": signal.ticker, "error": "no price data"})
                continue

            # Calculate excursion from entry
            if signal.entry_price and signal.entry_price > 0:
                if signal.direction == "LONG":
                    excursion_pct = ((current_price - signal.entry_price) / signal.entry_price) * 100
                else:
                    excursion_pct = ((signal.entry_price - current_price) / signal.entry_price) * 100

                current_mfe = getattr(signal, "max_favorable_excursion", None) or 0
                current_mae = getattr(signal, "max_adverse_excursion", None) or 0
                if excursion_pct > current_mfe:
                    signal.max_favorable_excursion = round(excursion_pct, 4)
                if excursion_pct < current_mae:
                    signal.max_adverse_excursion = round(excursion_pct, 4)

            # Check TP/SL hit
            outcome = _check_tp_sl(signal, current_price)

            if outcome:
                pnl_pct = _calc_pnl_pct(signal, current_price)
                signal.status = outcome
                signal.outcome = outcome
                signal.exit_price = current_price
                signal.pnl_pct = round(pnl_pct, 4)
                signal.resolved_at = datetime.utcnow()
                resolved.append({
                    "signal_id": str(signal.id),
                    "ticker": signal.ticker,
                    "direction": signal.direction,
                    "outcome": outcome,
                    "exit_price": current_price,
                    "pnl_pct": round(pnl_pct, 4),
                })
            else:
                evaluated.append({
                    "signal_id": str(signal.id),
                    "ticker": signal.ticker,
                    "current_price": current_price,
                    "status": "STILL_ACTIVE",
                })

        except Exception as exc:
            errors.append({"signal_id": str(signal.id), "ticker": signal.ticker, "error": str(exc)})

    # Check for expired signals (past expiry_time)
    now = datetime.utcnow()
    for signal in active_signals:
        if signal.expiry_time and signal.expiry_time < now and signal.status == "ACTIVE":
            signal.status = "EXPIRED"
            signal.outcome = "EXPIRED"
            signal.resolved_at = now
            resolved.append({
                "signal_id": str(signal.id),
                "ticker": signal.ticker,
                "outcome": "EXPIRED",
            })

    await db.commit()

    return {
        "total_active": len(active_signals),
        "still_active": len(evaluated),
        "resolved": len(resolved),
        "errors": len(errors),
        "resolved_signals": resolved,
        "error_details": errors,
    }


def _check_tp_sl(signal: Signal, current_price: float) -> str | None:
    """Return 'WIN' if TP1 hit, 'LOSS' if SL hit, None otherwise."""
    if signal.direction == "LONG":
        if current_price >= signal.take_profit_1:
            return "WIN"
        if current_price <= signal.stop_loss:
            return "LOSS"
    else:
        if current_price <= signal.take_profit_1:
            return "WIN"
        if current_price >= signal.stop_loss:
            return "LOSS"
    return None


def _calc_pnl_pct(signal: Signal, exit_price: float) -> float:
    """Calculate P&L percentage based on direction."""
    if not signal.entry_price or signal.entry_price == 0:
        return 0.0
    if signal.direction == "LONG":
        return ((exit_price - signal.entry_price) / signal.entry_price) * 100
    else:
        return ((signal.entry_price - exit_price) / signal.entry_price) * 100
