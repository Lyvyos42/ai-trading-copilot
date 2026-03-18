"""
POST /api/v1/signals/generate  — trigger multi-agent pipeline
GET  /api/v1/signals/{id}      — retrieve signal by ID
GET  /api/v1/signals           — list recent signals for user
"""
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_optional_user
from app.db.database import get_db
from app.models.signal import Signal
from app.pipeline.graph import run_pipeline

router = APIRouter(prefix="/api/v1/signals", tags=["signals"])

VALID_ASSET_CLASSES = {"stocks", "etfs", "fixed_income", "fx", "commodities", "crypto", "futures", "global_macro"}

# ── Ticker allowlist (built from market catalogue + common special-format symbols) ──
_ALLOWED_TICKER_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-^=")

def _is_valid_ticker(ticker: str) -> bool:
    """Accept tickers that are alphanumeric with allowed punctuation, 1–15 chars."""
    if not ticker or len(ticker) > 15:
        return False
    return all(c in _ALLOWED_TICKER_CHARS for c in ticker.upper())

# ── In-memory rate limiter: max 10 signal generations per IP per minute ──
_rate_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT = 10
_RATE_WINDOW = 60  # seconds

def _check_rate_limit(ip: str) -> None:
    now = time.time()
    window_start = now - _RATE_WINDOW
    _rate_store[ip] = [t for t in _rate_store[ip] if t > window_start]
    if len(_rate_store[ip]) >= _RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {_RATE_LIMIT} signals per minute per IP.",
            headers={"Retry-After": "60"},
        )
    _rate_store[ip].append(now)


class GenerateRequest(BaseModel):
    ticker: str
    asset_class: str = "stocks"
    timeframe: str = "1D"


@router.post("/generate")
async def generate_signal(
    request: Request,
    body: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_optional_user),
):
    # Rate limiting
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown").split(",")[0].strip()
    _check_rate_limit(client_ip)

    if body.asset_class not in VALID_ASSET_CLASSES:
        raise HTTPException(status_code=400, detail=f"Invalid asset_class. Choose from: {VALID_ASSET_CLASSES}")

    ticker = body.ticker.upper().strip()

    # Ticker allowlist validation
    if not _is_valid_ticker(ticker):
        raise HTTPException(status_code=400, detail="Invalid ticker format. Use standard exchange symbols (e.g. AAPL, BTC-USD, EURUSD=X).")

    # Run multi-agent pipeline
    state = await run_pipeline(ticker=ticker, asset_class=body.asset_class, timeframe=body.timeframe)

    final = state.get("final_signal", {})
    if not final:
        raise HTTPException(status_code=503, detail="Pipeline failed to generate signal")

    direction = final.get("direction", "LONG")
    if direction not in ("LONG", "SHORT"):
        direction = "LONG"

    # Build agent_votes summary
    agent_votes = {
        "fundamental": {
            "direction": state.get("fundamental_analysis", {}).get("direction"),
            "confidence": state.get("fundamental_analysis", {}).get("confidence"),
        },
        "technical": {
            "direction": state.get("technical_analysis", {}).get("direction"),
            "confidence": state.get("technical_analysis", {}).get("confidence"),
        },
        "sentiment": {
            "direction": state.get("sentiment_analysis", {}).get("direction"),
            "confidence": state.get("sentiment_analysis", {}).get("confidence"),
        },
        "macro": {
            "direction": state.get("macro_analysis", {}).get("direction"),
            "confidence": state.get("macro_analysis", {}).get("confidence"),
        },
        "risk_approved": state.get("risk_assessment", {}).get("approved", True),
    }

    signal = Signal(
        user_id=user["sub"] if user else None,
        ticker=ticker,
        asset_class=body.asset_class,
        timeframe=body.timeframe,
        direction=direction,
        entry_price=final.get("entry_price", 0),
        stop_loss=final.get("stop_loss", 0),
        take_profit_1=final.get("take_profit_1", 0),
        take_profit_2=final.get("take_profit_2", 0),
        take_profit_3=final.get("take_profit_3", 0),
        confidence_score=final.get("confidence_score", 0),
        agent_votes=agent_votes,
        reasoning_chain=state.get("reasoning_chain", []),
        strategy_sources=final.get("strategy_sources", []),
        status="ACTIVE",
        expiry_time=datetime.now(timezone.utc) + timedelta(hours=24),
    )
    db.add(signal)
    await db.commit()
    await db.refresh(signal)

    return _signal_to_dict(signal, state)


@router.get("/{signal_id}")
async def get_signal(
    signal_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    return _signal_to_dict(signal)


@router.get("")
async def list_signals(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_optional_user),
):
    query = select(Signal).order_by(desc(Signal.created_at)).limit(min(limit, 100))
    if user:
        query = query.where(Signal.user_id == user["sub"])
    result = await db.execute(query)
    signals = result.scalars().all()
    return [_signal_to_dict(s) for s in signals]


def _signal_to_dict(signal: Signal, state: dict | None = None) -> dict:
    d = {
        "signal_id": str(signal.id),
        "ticker": signal.ticker,
        "asset_class": signal.asset_class,
        "timeframe": signal.timeframe,
        "direction": signal.direction,
        "entry_price": signal.entry_price,
        "stop_loss": signal.stop_loss,
        "take_profit_1": signal.take_profit_1,
        "take_profit_2": signal.take_profit_2,
        "take_profit_3": signal.take_profit_3,
        "confidence_score": signal.confidence_score,
        "agent_votes": signal.agent_votes,
        "reasoning_chain": signal.reasoning_chain,
        "strategy_sources": signal.strategy_sources,
        "status": signal.status,
        "timestamp": signal.created_at.isoformat() if signal.created_at else None,
        "expiry_time": signal.expiry_time.isoformat() if signal.expiry_time else None,
    }
    if state:
        d["pipeline_latency_ms"] = state.get("pipeline_latency_ms")
        d["agent_detail"] = {
            "fundamental": state.get("fundamental_analysis"),
            "technical": state.get("technical_analysis"),
            "sentiment": state.get("sentiment_analysis"),
            "macro": state.get("macro_analysis"),
            "risk": state.get("risk_assessment"),
        }
    return d
