"""
POST /api/v1/signals/generate  — trigger multi-agent pipeline
GET  /api/v1/signals/{id}      — retrieve signal by ID
GET  /api/v1/signals           — list recent signals for user
"""
import math
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_optional_user
from app.db.database import get_db
from app.models.signal import Signal
from app.models.user import User
from app.pipeline.graph import run_pipeline

router = APIRouter(prefix="/api/v1/signals", tags=["signals"])

VALID_ASSET_CLASSES = {"stocks", "etfs", "fixed_income", "fx", "commodities", "crypto", "futures", "global_macro", "indices"}

# ── Ticker allowlist (built from market catalogue + common special-format symbols) ──
_ALLOWED_TICKER_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-^=")

def _is_valid_ticker(ticker: str) -> bool:
    """Accept tickers that are alphanumeric with allowed punctuation, 1–15 chars."""
    if not ticker or len(ticker) > 15:
        return False
    return all(c in _ALLOWED_TICKER_CHARS for c in ticker.upper())

# ── Layer 0: IP-based rate limiter — max 10 requests per minute per IP ──────────
_rate_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT = 10
_RATE_WINDOW = 60  # seconds

def _check_ip_rate_limit(ip: str) -> None:
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

# ── Layer 1: Per-user daily quota by tier ────────────────────────────────────────
_DAILY_QUOTA: dict[str, int] = {
    "free":       5,
    "retail":    50,
    "pro":       200,
    "enterprise": 9999,
    "admin":      9999,
}

async def _check_daily_quota(user_id: str, tier: str, db: AsyncSession) -> None:
    quota = _DAILY_QUOTA.get(tier, 5)
    now_utc = datetime.now(timezone.utc)
    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count()).select_from(Signal)
        .where(Signal.user_id == user_id)
        .where(Signal.created_at >= today_start)
    )
    count_today = result.scalar() or 0
    if count_today >= quota:
        # Retry-After = seconds until next midnight UTC
        next_midnight = today_start + timedelta(days=1)
        retry_after = int((next_midnight - now_utc).total_seconds())
        raise HTTPException(
            status_code=429,
            detail=f"Daily signal quota reached ({count_today}/{quota} for {tier} tier). Resets at midnight UTC.",
            headers={"Retry-After": str(retry_after)},
        )

# ── Layer 2: Per-user cooldown — minimum 60s between consecutive requests ────────
_user_last_request: dict[str, float] = {}
_USER_COOLDOWN_S = 15  # seconds

def _check_user_cooldown(user_id: str) -> None:
    now = time.time()
    last = _user_last_request.get(user_id, 0)
    elapsed = now - last
    if elapsed < _USER_COOLDOWN_S:
        wait = math.ceil(_USER_COOLDOWN_S - elapsed)
        raise HTTPException(
            status_code=429,
            detail=f"Please wait {wait}s before generating another signal.",
            headers={"Retry-After": str(wait)},
        )
    _user_last_request[user_id] = now

# ── Layer 3: Burst circuit breaker — >15 signals in 1 hour suspends user ────────
_user_burst_store: dict[str, list[float]] = defaultdict(list)
_BURST_LIMIT = 15
_BURST_WINDOW = 3600  # 1 hour

def _check_burst(user_id: str) -> None:
    now = time.time()
    window_start = now - _BURST_WINDOW
    _user_burst_store[user_id] = [t for t in _user_burst_store[user_id] if t > window_start]
    if len(_user_burst_store[user_id]) >= _BURST_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Burst limit exceeded ({_BURST_LIMIT} signals/hour). Account temporarily restricted. Try again in 1 hour.",
            headers={"Retry-After": "3600"},
        )
    _user_burst_store[user_id].append(now)

# ── Layer 4: Result cache — same user+ticker within 10 min returns cached signal ─
_signal_cache: dict[str, tuple[float, dict]] = {}  # key → (expires_at, signal_dict)
_CACHE_TTL_S = 30  # 30 seconds — keeps price fresh, avoids duplicate API calls

def _get_cached_signal(user_id: str, ticker: str) -> dict | None:
    key = f"{user_id}:{ticker}"
    entry = _signal_cache.get(key)
    if entry and time.time() < entry[0]:
        return entry[1]
    return None

def _cache_signal(user_id: str, ticker: str, signal_dict: dict) -> None:
    key = f"{user_id}:{ticker}"
    _signal_cache[key] = (time.time() + _CACHE_TTL_S, signal_dict)


class GenerateRequest(BaseModel):
    ticker: str
    asset_class: str = "stocks"
    timeframe: str = "1D"
    profile: str = "balanced"


@router.post("/generate")
async def generate_signal(
    request: Request,
    body: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_optional_user),
):
    # ── Layer 0: IP rate limit (protects unauthenticated + authenticated) ────────
    client_ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown").split(",")[0].strip()
    _check_ip_rate_limit(client_ip)

    # ── Authenticated user guards ────────────────────────────────────────────────
    db_user = None
    if user:
        user_id = user.get("sub") or user.get("id") or user.get("user_id") or ""
        # Fetch real tier from DB — Supabase JWTs don't carry a tier claim
        db_user_result = await db.execute(select(User).where(User.id == user_id))
        db_user = db_user_result.scalar_one_or_none()
        tier = (db_user.tier if db_user else None) or user.get("tier", "free") or "free"
        is_admin = tier == "admin"

        if not is_admin:
            # Layer 2: cooldown check BEFORE burst/quota (cheapest check first)
            _check_user_cooldown(user_id)

            # Layer 3: burst circuit breaker
            _check_burst(user_id)

            # Layer 4: result cache — return immediately without hitting Claude API
            cached = _get_cached_signal(user_id, body.ticker.upper().strip())
            if cached:
                return {**cached, "cached": True}

            # Block if user already has an ACTIVE signal for this ticker
            existing = await db.execute(
                select(Signal)
                .where(Signal.user_id == user_id)
                .where(Signal.ticker == body.ticker.upper().strip())
                .where(Signal.status == "ACTIVE")
                .limit(1)
            )
            if existing.scalar_one_or_none():
                raise HTTPException(
                    status_code=409,
                    detail=f"You already have an active signal for {body.ticker.upper().strip()}. Mark it as WIN or LOSS before generating a new one.",
                )

            # Layer 1: daily quota (DB query — do last to avoid unnecessary I/O)
            await _check_daily_quota(user_id, tier, db)

    if body.asset_class not in VALID_ASSET_CLASSES:
        raise HTTPException(status_code=400, detail=f"Invalid asset_class. Choose from: {VALID_ASSET_CLASSES}")

    ticker = body.ticker.upper().strip()

    # Ticker allowlist validation
    if not _is_valid_ticker(ticker):
        raise HTTPException(status_code=400, detail="Invalid ticker format. Use standard exchange symbols (e.g. AAPL, BTC-USD, EURUSD=X).")

    # Run multi-agent pipeline
    # Resolve profile: request param takes priority, then user's DB setting, then default
    profile_slug = body.profile
    if profile_slug == "balanced" and user:
        # Check if user has a non-default profile stored
        if db_user and hasattr(db_user, "active_profile") and db_user.active_profile:
            profile_slug = db_user.active_profile

    state = await run_pipeline(ticker=ticker, asset_class=body.asset_class, timeframe=body.timeframe, profile=profile_slug)

    final = state.get("final_signal", {})
    if not final:
        raise HTTPException(status_code=503, detail="Pipeline failed to generate signal")

    direction = final.get("direction", "LONG")
    if direction not in ("LONG", "SHORT"):
        direction = "LONG"

    # Build agent_votes summary (all 7 analysts + risk + quant)
    agent_votes = {}
    for key, label in [
        ("fundamental_analysis", "fundamental"),
        ("technical_analysis", "technical"),
        ("sentiment_analysis", "sentiment"),
        ("macro_analysis", "macro"),
        ("order_flow_analysis", "order_flow"),
        ("regime_change_analysis", "regime_change"),
        ("correlation_analysis", "correlation"),
    ]:
        analysis = state.get(key, {})
        agent_votes[label] = {
            "direction": analysis.get("direction"),
            "confidence": analysis.get("confidence"),
            "bullish_contribution": analysis.get("bullish_contribution"),
            "bearish_contribution": analysis.get("bearish_contribution"),
        }
    agent_votes["risk_approved"] = state.get("risk_assessment", {}).get("approved", True)
    agent_votes["quant_validated"] = state.get("quant_validation", {}).get("statistical_edge")

    user_id = (user.get("sub") or user.get("id") or user.get("user_id")) if user else None

    signal = Signal(
        user_id=user_id,
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
        timeframe_levels=final.get("timeframe_levels", {}),
        status="ACTIVE",
        expiry_time=datetime.utcnow() + timedelta(hours=24),
    )

    # Save to DB — non-blocking: return signal even if DB write fails
    signal_id = None
    try:
        db.add(signal)
        await db.commit()
        await db.refresh(signal)
        signal_id = str(signal.id)
    except Exception:
        pass  # DB unavailable — analysis result is still returned

    result = _signal_to_dict(signal, state) if signal_id else {
        "signal_id": None,
        "ticker": ticker,
        "asset_class": body.asset_class,
        "timeframe": body.timeframe,
        "direction": direction,
        "entry_price": final.get("entry_price", 0),
        "stop_loss": final.get("stop_loss", 0),
        "take_profit_1": final.get("take_profit_1", 0),
        "take_profit_2": final.get("take_profit_2", 0),
        "take_profit_3": final.get("take_profit_3", 0),
        "confidence_score": final.get("confidence_score", 0),
        "agent_votes": agent_votes,
        "reasoning_chain": state.get("reasoning_chain", []),
        "strategy_sources": final.get("strategy_sources", []),
        "timeframe_levels": final.get("timeframe_levels", {}),
        "status": "ACTIVE",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "expiry_time": (datetime.utcnow() + timedelta(hours=24)).isoformat() + "Z",
        "pipeline_latency_ms": state.get("pipeline_latency_ms"),
        "agent_detail": _build_agent_detail(state),
    }

    # Store in cache so repeat requests for the same ticker are instant
    if user:
        _cache_signal(user.get("sub", ""), ticker, result)

    return result


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
        uid = user.get("sub") or user.get("id") or user.get("user_id")
        if uid:
            query = query.where(Signal.user_id == uid)
    result = await db.execute(query)
    signals = result.scalars().all()
    return [_signal_to_dict(s) for s in signals]


class OutcomeRequest(BaseModel):
    outcome: str  # "WIN" or "LOSS"


@router.patch("/{signal_id}/outcome")
async def set_signal_outcome(
    signal_id: str,
    body: OutcomeRequest,
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_optional_user),
):
    if body.outcome not in ("WIN", "LOSS"):
        raise HTTPException(status_code=400, detail="outcome must be WIN or LOSS")

    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    # Only the owner can resolve their signal
    owner_id = (user.get("sub") or user.get("id") or user.get("user_id")) if user else None
    if user and signal.user_id and signal.user_id != owner_id:
        raise HTTPException(status_code=403, detail="Not your signal")

    signal.status = body.outcome
    await db.commit()
    await db.refresh(signal)
    return _signal_to_dict(signal)


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
        "timeframe_levels": signal.timeframe_levels or {},
        "status": signal.status,
        "timestamp": (signal.created_at.isoformat() + "Z") if signal.created_at else None,
        "expiry_time": (signal.expiry_time.isoformat() + "Z") if signal.expiry_time else None,
    }
    if state:
        d["pipeline_latency_ms"] = state.get("pipeline_latency_ms")
        d["agent_detail"] = _build_agent_detail(state)
    return d


def _build_agent_detail(state: dict) -> dict:
    """Build the full agent detail dict including all 9 agents."""
    return {
        "fundamental": state.get("fundamental_analysis"),
        "technical": state.get("technical_analysis"),
        "sentiment": state.get("sentiment_analysis"),
        "macro": state.get("macro_analysis"),
        "order_flow": state.get("order_flow_analysis"),
        "regime_change": state.get("regime_change_analysis"),
        "correlation": state.get("correlation_analysis"),
        "quant": state.get("quant_validation"),
        "risk": state.get("risk_assessment"),
        "risk_gate": state.get("risk_gate_result"),
        "agent_attribution": state.get("final_signal", {}).get("agent_attribution", []),
    }
