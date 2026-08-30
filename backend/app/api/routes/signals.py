"""
POST /api/v1/signals/generate  — trigger multi-agent pipeline
GET  /api/v1/signals/{id}      — retrieve signal by ID
GET  /api/v1/signals           — list recent signals for user
"""
import asyncio
import hashlib
import math
import os
import random
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, desc, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user, get_optional_user
from app.db.database import get_db
from app.models.signal import Signal
from app.models.user import User
from app.pipeline.graph import run_pipeline
from app.data.market_data import resolve_ticker, _fetch_rest_spot_price, _fetch_tv_ta_spot
from app.services.market_hours import market_status
from app.services.signal_resolver import resolve_open_signals, window_to_hours


# Shared with the auto-scanner and the resolver so every code path agrees on
# how long a thesis is given to play out.
_window_to_hours = window_to_hours


async def _get_spot_price(ticker: str) -> float | None:
    """Get spot price: TradingView scanner first, Yahoo REST fallback."""
    price = await _fetch_tv_ta_spot(ticker)
    if price and price > 0:
        return price
    return await _fetch_rest_spot_price(resolve_ticker(ticker))

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

# ── Layer 0b: IP-based daily limit for visitors (no account) ─────────────────────
_VISITOR_DAILY_LIMIT = 2
_visitor_daily_store: dict[str, list[float]] = defaultdict(list)

def _check_visitor_daily_limit(ip: str) -> None:
    now = time.time()
    day_start = now - 86400  # 24-hour rolling window
    _visitor_daily_store[ip] = [t for t in _visitor_daily_store[ip] if t > day_start]
    if len(_visitor_daily_store[ip]) >= _VISITOR_DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Visitor limit reached ({_VISITOR_DAILY_LIMIT} signals per day). Create a free account for more.",
            headers={"Retry-After": "3600"},
        )
    _visitor_daily_store[ip].append(now)

# ── Layer 1: Per-user daily quota by tier ────────────────────────────────────────
_DAILY_QUOTA: dict[str, int] = {
    "free":       2,
    "retail":     3,
    "pro":       10,
    "enterprise": 30,
    "admin":      9999,
}

async def _check_daily_quota(user_id: str, tier: str, db: AsyncSession) -> None:
    quota = _DAILY_QUOTA.get(tier, 5)
    now_utc = datetime.utcnow()
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


# ── Tiers that get real AI signals (Claude API calls) ─────────────────────────
_PAID_TIERS = {"retail", "pro", "enterprise", "admin"}


# ── Demo signal generator — no Claude API calls ──────────────────────────────
# Produces realistic-looking signals using deterministic randomness seeded by
# ticker + date so the same ticker on the same day returns consistent results.

_DEMO_BULL_CASES = [
    "Price holding above key support with bullish RSI divergence on 4H. Institutional accumulation visible in order flow delta.",
    "Strong earnings momentum with revenue beat. MACD crossover confirmed on daily, aligned with sector rotation into risk-on.",
    "Breakout above consolidation range with volume confirmation. Macro backdrop supportive with dovish central bank guidance.",
    "Multiple timeframe alignment: bullish on daily, 4H, and 1H. Sentiment skewed positive from recent catalyst.",
]
_DEMO_BEAR_CASES = [
    "Approaching major resistance with bearish divergence on RSI. Volume declining on rallies suggests distribution.",
    "Macro headwinds: rising yields compressing multiples. Sector peers showing relative weakness.",
    "Overextended from 20-day moving average. Mean reversion probability elevated based on historical Z-score.",
    "Negative news flow creating sentiment drag. Order flow shows persistent selling pressure at current levels.",
]
_DEMO_STRATEGIES = [
    ["RSI Divergence", "MACD Crossover", "Volume Profile"],
    ["Mean Reversion", "Bollinger Band Squeeze", "Kelly Criterion"],
    ["Momentum Breakout", "Fibonacci Retracement", "ATR Trailing Stop"],
    ["Institutional Order Flow", "Market Profile", "VWAP Deviation"],
]

def _generate_demo_signal(ticker: str, asset_class: str, timeframe: str) -> dict:
    """Generate a realistic simulated signal without calling Claude."""
    # Deterministic seed: same ticker + day = same result
    seed_str = f"{ticker}:{datetime.utcnow().strftime('%Y-%m-%d')}:{timeframe}"
    seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed)

    direction = rng.choice(["LONG", "SHORT"])
    confidence = round(rng.uniform(52, 85), 1)
    bullish_pct = round(rng.uniform(35, 80), 1)
    bearish_pct = round(100 - bullish_pct, 1)
    if direction == "SHORT":
        bullish_pct, bearish_pct = bearish_pct, bullish_pct

    # Price levels — realistic relative distances
    base_prices = {
        "XAUUSD": 2400, "EURUSD": 1.08, "GBPUSD": 1.27, "USDJPY": 155,
        "BTC": 65000, "ETH": 3200, "AAPL": 190, "MSFT": 420, "NVDA": 880,
        "TSLA": 175, "US30": 40000, "US500": 5300, "XAGUSD": 28,
    }
    # Find a matching base price or derive one
    base = None
    for key, val in base_prices.items():
        if key in ticker:
            base = val
            break
    if base is None:
        base = rng.uniform(50, 500)

    entry = round(base * rng.uniform(0.97, 1.03), 2 if base > 100 else 5)
    atr_pct = rng.uniform(0.008, 0.025)
    sl_dist = entry * atr_pct
    if direction == "LONG":
        sl = round(entry - sl_dist, 2 if base > 100 else 5)
        tp1 = round(entry + sl_dist * 1.5, 2 if base > 100 else 5)
        tp2 = round(entry + sl_dist * 2.5, 2 if base > 100 else 5)
        tp3 = round(entry + sl_dist * 3.5, 2 if base > 100 else 5)
    else:
        sl = round(entry + sl_dist, 2 if base > 100 else 5)
        tp1 = round(entry - sl_dist * 1.5, 2 if base > 100 else 5)
        tp2 = round(entry - sl_dist * 2.5, 2 if base > 100 else 5)
        tp3 = round(entry - sl_dist * 3.5, 2 if base > 100 else 5)

    rr = round(abs(tp2 - entry) / abs(sl - entry), 1) if abs(sl - entry) > 0 else 2.0
    idx = rng.randint(0, len(_DEMO_BULL_CASES) - 1)

    agent_names = ["fundamental", "technical", "sentiment", "macro", "order_flow", "regime_change", "correlation"]
    agent_votes = {}
    for name in agent_names:
        a_dir = direction if rng.random() > 0.25 else ("SHORT" if direction == "LONG" else "LONG")
        a_conf = round(rng.uniform(45, 90), 1)
        agent_votes[name] = {
            "direction": a_dir, "confidence": a_conf,
            "bullish_contribution": round(rng.uniform(5, 20), 1),
            "bearish_contribution": round(rng.uniform(5, 20), 1),
        }
    agent_votes["risk_approved"] = True
    agent_votes["quant_validated"] = rng.random() > 0.3

    conviction = "HIGH" if confidence > 72 else "MODERATE" if confidence > 60 else "LOW"
    window_map = {"1m": "1-4 hours", "5m": "4-12 hours", "15m": "12-24 hours",
                  "30m": "1-2 days", "1h": "1-3 days", "4h": "3-7 days", "1D": "3-7 days"}
    analytical_window = window_map.get(timeframe, "3-7 days")

    now = datetime.utcnow()
    return {
        "ticker": ticker, "asset_class": asset_class, "timeframe": timeframe,
        "direction": direction,
        "entry_price": entry, "stop_loss": sl,
        "take_profit_1": tp1, "take_profit_2": tp2, "take_profit_3": tp3,
        "confidence_score": confidence,
        "probability_score": confidence,
        "bullish_pct": bullish_pct, "bearish_pct": bearish_pct,
        "research_target": tp2, "invalidation_level": sl,
        "risk_reward_ratio": rr,
        "analytical_window": analytical_window,
        "bull_case": _DEMO_BULL_CASES[idx],
        "bear_case": _DEMO_BEAR_CASES[idx],
        "conviction_tier": conviction,
        "agent_votes": agent_votes,
        "reasoning_chain": [
            f"7 analyst agents ran parallel analysis on {ticker} ({timeframe})",
            f"Majority consensus: {direction} with {confidence}% confidence",
            f"Risk Manager approved — R:R {rr}:1, Kelly sizing applied",
            "Trader agent synthesized final signal with probability model",
        ],
        "strategy_sources": _DEMO_STRATEGIES[idx],
        "timeframe_levels": {},
        "status": "ACTIVE",
        "timestamp": now.isoformat() + "Z",
        "expiry_time": (now + timedelta(hours=24)).isoformat() + "Z",
        "pipeline_latency_ms": rng.randint(800, 3500),
        "agent_detail": {name: agent_votes.get(name) for name in agent_names},
        "is_demo": True,
    }


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
    user: dict = Depends(get_current_user),
):
    # ── Layer -1: market session ─────────────────────────────────────────────
    # Refuse before the pipeline runs. A signal computed on a closed market
    # prices off a stale print, sizes off yesterday's ATR, and sets an
    # invalidation level nothing can reach. The risk gate did catch these, but
    # only after nine agents had run and a row had been written.
    _session = market_status(body.ticker, body.asset_class)
    if not _session["open"]:
        raise HTTPException(
            status_code=409,
            detail=(f"{body.ticker.upper()} — {_session['reason']}."
                    + (f" Reopens {_session['reopens']}." if _session.get("reopens") else "")),
        )

    # ── Layer 0: IP rate limit (protects unauthenticated + authenticated) ────────
    forwarded = request.headers.get("x-forwarded-for", "")
    client_ip = forwarded.split(",")[-1].strip() if forwarded else (request.client.host if request.client else "unknown")
    _check_ip_rate_limit(client_ip)

    # ── Fetch DB user ─────────────────────────────────────────────────────────
    db_user = None

    # ── Authenticated user guards ────────────────────────────────────────────────
    if user:
        user_id = user.get("sub") or user.get("id") or user.get("user_id") or ""
        # Fetch real tier from DB — Supabase JWTs don't carry a tier claim
        db_user_result = await db.execute(select(User).where(User.id == user_id))
        db_user = db_user_result.scalar_one_or_none()
        tier = (db_user.tier if db_user else None) or user.get("tier", "free") or "free"
        admin_emails = [e.strip().lower() for e in os.environ.get("ADMIN_EMAILS", "").split(",") if e.strip()]
        user_email = (db_user.email.lower() if db_user and db_user.email else "")
        is_admin = tier == "admin" or user_email in admin_emails

        if not is_admin:
            # Layer 2: cooldown check BEFORE burst/quota (cheapest check first)
            _check_user_cooldown(user_id)

            # Layer 3: burst circuit breaker
            _check_burst(user_id)

            # Layer 4: result cache — return immediately without hitting Claude API
            cached = _get_cached_signal(user_id, body.ticker.upper().strip())
            if cached:
                return {**cached, "cached": True}

            # Block if user already has an ACTIVE (non-expired) signal for this ticker
            existing = await db.execute(
                select(Signal)
                .where(Signal.user_id == user_id)
                .where(Signal.ticker == body.ticker.upper().strip())
                .where(Signal.status == "ACTIVE")
                .where(Signal.expiry_time > datetime.utcnow())
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

    # ── Demo signals for free tier & visitors (no Claude API cost) ────────────
    tier = "free"
    if user and db_user:
        tier = db_user.tier or "free"
    elif user:
        tier = user.get("tier", "free") or "free"

    # ── Resolve profile ─────────────────────────────────────────────────────
    profile_slug = body.profile
    if profile_slug == "balanced" and user:
        if db_user and hasattr(db_user, "active_profile") and db_user.active_profile:
            profile_slug = db_user.active_profile

    user_id_for_pipeline = (user.get("sub") or user.get("id") or user.get("user_id")) if user else None
    user_tier_for_pipeline = tier if tier else "free"

    # Free tier & visitors: real Python analysis with market data (no AI cost)
    # Paid tiers: full AI-powered multi-agent pipeline
    is_free = tier not in _PAID_TIERS
    state = await run_pipeline(
        ticker=ticker,
        asset_class=body.asset_class,
        timeframe=body.timeframe,
        profile=profile_slug,
        user_id=user_id_for_pipeline,
        user_tier=user_tier_for_pipeline,
        force_fallback=is_free,
    )

    final = state.get("final_signal", {})
    if not final:
        raise HTTPException(status_code=503, detail="Pipeline failed to generate signal")

    direction = final.get("direction", "LONG")
    if direction not in ("LONG", "SHORT"):
        direction = "LONG"

    # Fetch live spot price so the signal always uses the current market price,
    # not whatever stale close fetch_market_data may have returned.
    live_spot = await _get_spot_price(ticker)
    if live_spot and live_spot > 0:
        old_entry = final.get("entry_price") or live_spot
        if old_entry and old_entry > 0 and abs(old_entry - live_spot) / old_entry > 0.0001:
            ratio = live_spot / old_entry
            for lvl_key in ("stop_loss", "take_profit_1", "take_profit_2", "take_profit_3",
                            "research_target", "invalidation_level"):
                if final.get(lvl_key):
                    final[lvl_key] = round(final[lvl_key] * ratio, 6)
            tf_levels = final.get("timeframe_levels") or {}
            for tf_key in ("scalp", "swing"):
                tf = tf_levels.get(tf_key)
                if not tf:
                    continue
                for k in ("entry", "stop_loss", "take_profit_1", "take_profit_2", "take_profit_3"):
                    if tf.get(k):
                        tf[k] = round(tf[k] * ratio, 6)
        final["entry_price"] = live_spot
        final["current_price"] = live_spot

    # Reject weak signals: probability must lean >= 55% in either direction
    prob = final.get("probability_score")
    if prob is not None:
        directional_strength = abs(prob - 50)
        if directional_strength < 5:
            final["conviction_tier"] = "NO_EDGE"
            final["status"] = "FILTERED"
            final["risk_gate_reasons"] = [
                f"Probability {prob:.1f}% is within 5 points of neutral — "
                f"no directional edge to trade"
            ]

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
        # A NO_EDGE result set final["status"] = "FILTERED" above, but the row was
        # always written as ACTIVE — so nothing was ever actually filtered and
        # every no-edge signal still landed in the scored track record.
        status=final.get("status", "ACTIVE"),
        expiry_time=datetime.utcnow() + timedelta(hours=_window_to_hours(final.get("analytical_window"))),
        # Probability model fields
        probability_score=final.get("probability_score"),
        bullish_pct=final.get("bullish_pct"),
        bearish_pct=final.get("bearish_pct"),
        research_target=final.get("research_target"),
        invalidation_level=final.get("invalidation_level"),
        risk_reward_ratio=final.get("risk_reward_ratio"),
        analytical_window=final.get("analytical_window"),
        bull_case=final.get("bull_case"),
        bear_case=final.get("bear_case"),
        conviction_tier=final.get("conviction_tier"),
        signal_mode=final.get("signal_mode", "AI"),
    )

    # Save to DB — non-blocking: return signal even if DB write fails.
    #
    # REJECTIONS ARE NOT PERSISTED. A NO_EDGE result or a risk-gate block is the
    # pipeline declining to produce a signal, not a signal with a bad outcome.
    # Writing them filled Signal History with a row every time the scanner swept
    # a symbol — the scanner runs about once a minute, so the history refilled
    # within a minute of any RESET and the button looked broken. The response
    # still carries the status and its reasons, so the UI can explain the
    # rejection; there is simply no row to accumulate.
    _persist = signal.status == "ACTIVE"
    signal_id = None
    if _persist:
        try:
            db.add(signal)
            await db.commit()
            await db.refresh(signal)
            signal_id = str(signal.id)
        except Exception:
            pass  # DB unavailable — analysis result is still returned

    result = _signal_to_dict(signal, state, current_price=live_spot if live_spot and live_spot > 0 else None) if signal_id else {
        "signal_id": None,
        "ticker": ticker,
        "asset_class": body.asset_class,
        "timeframe": body.timeframe,
        "direction": direction,
        "entry_price": final.get("entry_price", 0),
        "current_price": live_spot if live_spot and live_spot > 0 else final.get("entry_price", 0),
        "stop_loss": final.get("stop_loss", 0),
        "take_profit_1": final.get("take_profit_1", 0),
        "take_profit_2": final.get("take_profit_2", 0),
        "take_profit_3": final.get("take_profit_3", 0),
        "confidence_score": final.get("confidence_score", 0),
        "agent_votes": agent_votes,
        "reasoning_chain": state.get("reasoning_chain", []),
        "strategy_sources": final.get("strategy_sources", []),
        "timeframe_levels": final.get("timeframe_levels", {}),
        # Must mirror the real status. This branch is taken whenever nothing was
        # persisted — which is now the normal path for a REJECTED signal — and a
        # hardcoded ACTIVE told the UI a NO_EDGE result was tradeable, putting it
        # straight back into the feed.
        "status": final.get("status", "ACTIVE"),
        "status_reasons": final.get("risk_gate_reasons") or None,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "expiry_time": (datetime.utcnow() + timedelta(hours=24)).isoformat() + "Z",
        "pipeline_latency_ms": state.get("pipeline_latency_ms"),
        "agent_detail": _build_agent_detail(state),
        # Probability model fields
        "probability_score": final.get("probability_score"),
        "bullish_pct": final.get("bullish_pct"),
        "bearish_pct": final.get("bearish_pct"),
        "research_target": final.get("research_target"),
        "invalidation_level": final.get("invalidation_level"),
        "risk_reward_ratio": final.get("risk_reward_ratio"),
        "analytical_window": final.get("analytical_window"),
        "bull_case": final.get("bull_case"),
        "bear_case": final.get("bear_case"),
        "conviction_tier": final.get("conviction_tier"),
        "signal_mode": final.get("signal_mode", "AI"),
    }

    # Store in cache so repeat requests for the same ticker are instant
    if user:
        _cache_signal(user.get("sub", ""), ticker, result)

    # ── Memory Layer: track interaction + extract memories (fire-and-forget) ──
    if user and signal_id:
        import asyncio
        from app.services.interactions import track_event as _track
        from app.services.memory import memory_manager as _mm

        _uid = user.get("sub") or user.get("id") or user.get("user_id") or ""

        async def _track_generate():
            try:
                from app.db.database import AsyncSessionLocal
                async with AsyncSessionLocal() as sess:
                    await _track(
                        db=sess, user_id=_uid, event_type="SIGNAL_GENERATE",
                        ticker=ticker, signal_id=signal_id,
                        payload={"probability_score": final.get("probability_score"),
                                 "direction": direction, "conviction_tier": final.get("conviction_tier"),
                                 "timeframe": body.timeframe, "profile": profile_slug},
                    )
            except Exception:
                pass
        asyncio.create_task(_track_generate())

        # Skip memory extraction when Anthropic API is unavailable
        from app.providers.router import model_router
        _anth = model_router._providers.get("anthropic")
        if not (_anth and _anth.is_fallback_mode):
            asyncio.create_task(_mm.extract_memories_from_session(
                user_id=_uid,
                session_data={
                    "instrument": ticker, "asset_class": body.asset_class,
                    "timeframe": body.timeframe, "direction": direction,
                    "probability_score": final.get("probability_score"),
                    "conviction_tier": final.get("conviction_tier"),
                    "strategy_sources": final.get("strategy_sources", []),
                    "bull_case": final.get("bull_case", "")[:200],
                    "bear_case": final.get("bear_case", "")[:200],
                    "session_timestamp": datetime.now(timezone.utc).isoformat(),
                    "profile": profile_slug,
                },
            ))

    return result


@router.get("/journal")
async def journal_signals(
    limit: int = 50,
    offset: int = 0,
    ticker: str | None = None,
    outcome: str | None = None,
    asset_class: str | None = None,
    min_confidence: float | None = None,
    max_confidence: float | None = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Full signal history with filters — for authenticated journal page."""
    uid = user.get("sub") or user.get("id") or user.get("user_id")
    query = select(Signal).order_by(desc(Signal.created_at))
    if uid:
        query = query.where(Signal.user_id == uid)

    if ticker:
        query = query.where(Signal.ticker == ticker.upper().strip())
    if outcome:
        query = query.where(Signal.outcome == outcome.upper())
    if asset_class:
        query = query.where(Signal.asset_class == asset_class)
    if min_confidence is not None:
        query = query.where(Signal.confidence_score >= min_confidence)
    if max_confidence is not None:
        query = query.where(Signal.confidence_score <= max_confidence)

    query = query.offset(offset).limit(min(limit, 200))
    result = await db.execute(query)
    signals = result.scalars().all()
    return [_signal_to_dict(s) for s in signals]


@router.get("/{signal_id}")
async def get_signal(
    signal_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    uid = user.get("sub") or user.get("id") or user.get("user_id")
    result = await db.execute(
        select(Signal).where(Signal.id == signal_id, Signal.user_id == uid)
    )
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    cp = None
    if signal.status == "ACTIVE":
        cp = await _get_spot_price(signal.ticker)
    return _signal_to_dict(signal, current_price=cp if isinstance(cp, (int, float)) and cp > 0 else None)


@router.get("")
async def list_signals(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    uid = user.get("sub") or user.get("id") or user.get("user_id")
    query = select(Signal).order_by(desc(Signal.created_at)).limit(min(limit, 100))
    if uid:
        query = query.where(Signal.user_id == uid)
    result = await db.execute(query)
    signals = result.scalars().all()

    # Batch-fetch current prices for active signals so the frontend shows live entry
    active_tickers = list({s.ticker for s in signals if s.status == "ACTIVE"})
    price_map: dict[str, float] = {}
    if active_tickers:
        tasks = [_get_spot_price(t) for t in active_tickers]
        prices = await asyncio.gather(*tasks, return_exceptions=True)
        for ticker, price in zip(active_tickers, prices):
            if isinstance(price, (int, float)) and price > 0:
                price_map[ticker] = price

    # Resolve open signals against the actual price path. The scheduler does this
    # every 15 min for everyone; this keeps the list fresh on load. It replaces a
    # spot-price snapshot check that could only see where price happened to be at
    # render time — which missed every target touched intraday and counted any
    # momentary dip through the (much nearer) stop as a loss.
    try:
        await resolve_open_signals(db, signals=signals)
    except Exception:
        await db.rollback()

    return [_signal_to_dict(s, current_price=price_map.get(s.ticker)) for s in signals]


class OutcomeRequest(BaseModel):
    outcome: str  # "WIN", "LOSS", or "EXPIRED"
    exit_price: float | None = None
    pnl_pct: float | None = None


@router.patch("/{signal_id}/outcome")
async def set_signal_outcome(
    signal_id: str,
    body: OutcomeRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if body.outcome not in ("WIN", "LOSS", "EXPIRED"):
        raise HTTPException(status_code=400, detail="outcome must be WIN, LOSS, or EXPIRED")

    owner_id = user.get("sub") or user.get("id") or user.get("user_id") or ""
    _u = (await db.execute(select(User).where(User.id == owner_id))).scalar_one_or_none()
    is_admin = (_u.tier if _u else "free") == "admin"

    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    if not is_admin:
        if signal.user_id and signal.user_id != owner_id:
            raise HTTPException(status_code=403, detail="Not your signal")
        if not signal.user_id:
            raise HTTPException(status_code=403, detail="System signals can only be resolved by admins")

    signal.status = body.outcome
    signal.outcome = body.outcome
    if body.exit_price is not None:
        signal.exit_price = body.exit_price
    if body.pnl_pct is not None:
        signal.pnl_pct = body.pnl_pct
    signal.resolved_at = datetime.utcnow()
    await db.commit()
    await db.refresh(signal)

    # ── Memory Layer: store outcome + generate agent corrections ──────────
    import asyncio
    from app.services.memory import memory_manager as _mm
    from app.services.interactions import track_event as _track
    from app.models.memory import AgentCorrection

    _uid = owner_id or ""
    if _uid:
        # Use a fresh session for the background task — request session closes after response
        async def _track_outcome():
            try:
                from app.db.database import AsyncSessionLocal
                async with AsyncSessionLocal() as sess:
                    await _track(
                        db=sess, user_id=_uid, event_type="OUTCOME_MARK",
                        ticker=signal.ticker, signal_id=signal_id,
                        payload={"outcome": body.outcome, "pnl_pct": body.pnl_pct},
                    )
            except Exception:
                pass
        asyncio.create_task(_track_outcome())

    # Store outcome as a memory for the user
    pnl_str = f" ({body.pnl_pct:+.1f}%)" if body.pnl_pct else ""
    memory_text = (
        f"Signal on {signal.ticker} ({signal.direction}, {signal.timeframe}): "
        f"{body.outcome}{pnl_str}. "
        f"Probability was {signal.probability_score or signal.confidence_score or '?'}%. "
        f"Conviction: {getattr(signal, 'conviction_tier', 'N/A')}."
    )
    importance = "HIGH" if body.outcome == "LOSS" else "MEDIUM"
    _mm.store_memory(
        user_id=_uid or "system",
        memory=memory_text,
        memory_type="PERFORMANCE",
        importance=importance,
    )

    # Generate agent corrections (async — uses Haiku for lesson generation)
    # Skip when Anthropic API is unavailable (circuit breaker open)
    async def _store_corrections():
        try:
            from app.providers.router import model_router
            _anth = model_router._providers.get("anthropic")
            if _anth and _anth.is_fallback_mode:
                return  # no point calling LLM — credits exhausted

            signal_data = {
                "signal_id": signal_id,
                "ticker": signal.ticker,
                "timeframe": signal.timeframe,
                "direction": signal.direction,
                "outcome": body.outcome,
                "pnl_pct": body.pnl_pct,
                "agent_votes": signal.agent_votes or {},
            }
            corrections = await _mm.generate_agent_corrections(signal_data)
            if corrections:
                from app.db.database import AsyncSessionLocal
                async with AsyncSessionLocal() as sess:
                    for c in corrections:
                        sess.add(AgentCorrection(**c))
                    await sess.commit()
        except Exception:
            pass  # memory is enhancement, not core

    asyncio.create_task(_store_corrections())

    return _signal_to_dict(signal)


def _signal_to_dict(signal: Signal, state: dict | None = None, current_price: float | None = None) -> dict:
    d = {
        "signal_id": str(signal.id),
        "ticker": signal.ticker,
        "asset_class": signal.asset_class,
        "timeframe": signal.timeframe,
        "direction": signal.direction,
        "entry_price": signal.entry_price,
        "current_price": current_price,
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
        "outcome": getattr(signal, "outcome", None),
        "exit_price": getattr(signal, "exit_price", None),
        "resolved_at": (signal.resolved_at.isoformat() + "Z") if getattr(signal, "resolved_at", None) else None,
        "pnl_pct": getattr(signal, "pnl_pct", None),
        # Probability model fields
        "probability_score": getattr(signal, "probability_score", None),
        "bullish_pct": getattr(signal, "bullish_pct", None),
        "bearish_pct": getattr(signal, "bearish_pct", None),
        "research_target": getattr(signal, "research_target", None),
        "invalidation_level": getattr(signal, "invalidation_level", None),
        "risk_reward_ratio": getattr(signal, "risk_reward_ratio", None),
        "analytical_window": getattr(signal, "analytical_window", None),
        "bull_case": getattr(signal, "bull_case", None),
        "bear_case": getattr(signal, "bear_case", None),
        "conviction_tier": getattr(signal, "conviction_tier", None),
        "timestamp": (signal.created_at.isoformat() + "Z") if signal.created_at else None,
        "expiry_time": (signal.expiry_time.isoformat() + "Z") if signal.expiry_time else None,
        "signal_mode": getattr(signal, "signal_mode", None) or "AI",
    }
    if state:
        d["pipeline_latency_ms"] = state.get("pipeline_latency_ms")
        d["agent_detail"] = _build_agent_detail(state)
        # Pipeline state overrides DB default when available
        _final = state.get("final_signal", {})
        d["signal_mode"] = _final.get("signal_mode", d["signal_mode"])
        # Why a signal is not tradeable. Without this the UI could only see that
        # status != ACTIVE and had nothing to show, so it dropped the card and
        # the signal appeared to vanish a moment after being generated.
        reasons = _final.get("risk_gate_reasons") or []
        gate = state.get("risk_gate_result") or {}
        if not reasons and gate.get("triggered_rules"):
            reasons = [t.get("reason") for t in gate["triggered_rules"] if t.get("reason")]
        if reasons:
            d["status_reasons"] = reasons
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


@router.delete("/reset")
async def reset_signals(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    # Deletes only the caller's own rows, so this needs no admin gate — clearing
    # your own track record before a fresh test run is ordinary use. It was
    # gated on ADMIN_EMAILS, which meant the RESET button silently did nothing
    # for everyone else.
    user_id = user.get("sub") or user.get("id") or user.get("user_id") or ""
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    result = await db.execute(delete(Signal).where(Signal.user_id == user_id))
    await db.commit()
    return {"deleted": result.rowcount}
