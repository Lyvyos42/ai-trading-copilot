"""
Session Mode API — start/stop sessions, run session analysis, get session status.
"""
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.api.routes.signals import get_current_user, get_market_data
from app.services.news_context import get_news_context
from app.pipeline.session_graph import run_session_pipeline

router = APIRouter(prefix="/api/v1/session", tags=["session"])

# In-memory session store (per-user active session)
# In production this would be Redis or DB-backed
_active_sessions: dict[str, dict] = {}


class StartSessionRequest(BaseModel):
    ticker: str
    profile: str = "balanced"


class SessionAnalyzeRequest(BaseModel):
    ticker: str | None = None  # defaults to session ticker


# ── POST /start — Start a new session ─────────────────────────────────────
@router.post("/start")
async def start_session(req: StartSessionRequest, request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = str(user.id)

    # Check tier — Session Mode requires Pro or higher
    tier = getattr(user, "tier", "free")
    if tier not in ("pro", "enterprise", "admin"):
        raise HTTPException(status_code=403, detail="Session Mode requires Pro plan or higher")

    # End any existing session
    if user_id in _active_sessions:
        _active_sessions[user_id]["ended_at"] = datetime.now(timezone.utc).isoformat()

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    session = {
        "session_id": session_id,
        "user_id": user_id,
        "ticker": req.ticker.upper(),
        "profile": req.profile,
        "session_start_time": now,
        "session_pnl": 0,
        "session_pnl_pct": 0,
        "session_high_water": 0,
        "session_drawdown_pct": 0,
        "session_trade_count": 0,
        "session_trades": [],
        "analysis_count_this_session": 0,
        "signals": [],
    }
    _active_sessions[user_id] = session

    return {
        "session_id": session_id,
        "ticker": req.ticker.upper(),
        "profile": req.profile,
        "started_at": now,
        "status": "ACTIVE",
    }


# ── POST /analyze — Run session analysis ──────────────────────────────────
@router.post("/analyze")
async def session_analyze(req: SessionAnalyzeRequest, request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = str(user.id)
    session = _active_sessions.get(user_id)
    if not session:
        raise HTTPException(status_code=400, detail="No active session. Call POST /start first.")

    ticker = (req.ticker or session["ticker"]).upper()

    # Get market data
    market_data = await get_market_data(ticker)

    # Get news context
    news_context = await get_news_context(ticker)

    # Run session pipeline
    result = await run_session_pipeline(
        ticker=ticker,
        market_data=market_data,
        news_context=news_context,
        session_state=session,
        profile=session.get("profile", "balanced"),
    )

    # Update session state
    session["analysis_count_this_session"] = session.get("analysis_count_this_session", 0) + 1
    session["signals"].append({
        "timestamp": result.get("timestamp"),
        "direction": result.get("direction"),
        "confidence": result.get("confidence"),
        "risk_gate_passed": result.get("risk_gate_passed"),
    })

    return result


# ── GET /status — Get current session status ──────────────────────────────
@router.get("/status")
async def session_status(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = str(user.id)
    session = _active_sessions.get(user_id)
    if not session:
        return {"active": False}

    return {
        "active": True,
        "session_id": session["session_id"],
        "ticker": session["ticker"],
        "profile": session.get("profile", "balanced"),
        "started_at": session["session_start_time"],
        "analysis_count": session.get("analysis_count_this_session", 0),
        "trade_count": session.get("session_trade_count", 0),
        "pnl": session.get("session_pnl", 0),
        "pnl_pct": session.get("session_pnl_pct", 0),
    }


# ── POST /stop — End the current session ──────────────────────────────────
@router.post("/stop")
async def stop_session(request: Request):
    user = await get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = str(user.id)
    session = _active_sessions.pop(user_id, None)
    if not session:
        return {"status": "NO_SESSION"}

    return {
        "status": "ENDED",
        "session_id": session["session_id"],
        "ticker": session["ticker"],
        "analysis_count": session.get("analysis_count_this_session", 0),
        "trade_count": session.get("session_trade_count", 0),
        "final_pnl": session.get("session_pnl", 0),
        "final_pnl_pct": session.get("session_pnl_pct", 0),
        "ended_at": datetime.now(timezone.utc).isoformat(),
    }
