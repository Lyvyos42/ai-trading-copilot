"""
Session Mode Pipeline — LangGraph-style async pipeline for intraday trading.

Flow:
  Timer → 5 parallel analysts → SessionTrader (Opus) → Coach → Risk Gate → Output
"""
import asyncio
import time
import structlog
from datetime import datetime, timezone

from app.pipeline.session_state import SessionState
from app.pipeline.session_risk_gate import run_session_risk_gate
from app.agents.session.timer import SessionTimer
from app.agents.session.technical import SessionTechnical
from app.agents.session.sentiment import SessionSentiment
from app.agents.session.order_flow import SessionOrderFlow
from app.agents.session.correlation import SessionCorrelation
from app.agents.session.risk import SessionRisk
from app.agents.session.trader import SessionTrader
from app.agents.session.coach import SessionCoach

log = structlog.get_logger()

# Singletons
_timer = SessionTimer()
_technical = SessionTechnical()
_sentiment = SessionSentiment()
_order_flow = SessionOrderFlow()
_correlation = SessionCorrelation()
_risk = SessionRisk()
_trader = SessionTrader()
_coach = SessionCoach()


async def _safe(coro, name: str, state: SessionState) -> tuple[str, dict]:
    """Run an agent coroutine safely, catching exceptions."""
    try:
        result = await coro
        return name, result
    except Exception as e:
        log.error("session_agent_error", agent=name, error=str(e))
        return name, {"error": str(e), "direction": "NEUTRAL", "confidence": 0}


async def run_session_pipeline(
    ticker: str,
    market_data: dict,
    news_context: dict | None = None,
    session_state: dict | None = None,
    profile: str = "balanced",
) -> dict:
    """
    Run the full session analysis pipeline.

    Args:
        ticker: Symbol to analyze
        market_data: Current OHLCV + indicators
        news_context: Live headlines (optional)
        session_state: Existing session state (P&L, trades, etc.)
        profile: Strategy profile slug

    Returns:
        Complete session analysis result dict
    """
    t0 = time.time()
    ss = session_state or {}

    state: SessionState = {
        "ticker": ticker,
        "asset_class": market_data.get("asset_class", "equity"),
        "strategy_profile": profile,
        "market_data": market_data,
        "news_context": news_context or {},
        # Carry forward session state
        "session_id": ss.get("session_id", ""),
        "session_start_time": ss.get("session_start_time", datetime.now(timezone.utc).isoformat()),
        "session_pnl": ss.get("session_pnl", 0),
        "session_pnl_pct": ss.get("session_pnl_pct", 0),
        "session_high_water": ss.get("session_high_water", 0),
        "session_drawdown_pct": ss.get("session_drawdown_pct", 0),
        "session_trade_count": ss.get("session_trade_count", 0),
        "session_trades": ss.get("session_trades", []),
        "analysis_count_this_session": ss.get("analysis_count_this_session", 0) + 1,
        "reasoning_chain": [],
        "errors": [],
    }

    # ── Stage 1: Timer (pure Python, instant) ───────────────────────────
    timer_result = await _timer.analyze(state)
    state["timer_analysis"] = timer_result
    state["reasoning_chain"].append(
        f"[Timer] Kill zone: {timer_result.get('kill_zone', 'NONE')}, "
        f"Phase: {timer_result.get('market_phase', 'UNKNOWN')}"
    )

    # ── Stage 2: 5 parallel session analysts ─────────────────────────────
    results = await asyncio.gather(
        _safe(_technical.analyze(state), "session_technical", state),
        _safe(_sentiment.analyze(state), "session_sentiment", state),
        _safe(_order_flow.analyze(state), "session_order_flow", state),
        _safe(_correlation.analyze(state), "session_correlation", state),
        _safe(_risk.analyze(state), "session_risk", state),
    )

    for key, result in results:
        state[key] = result
        direction = result.get("direction", "NEUTRAL")
        confidence = result.get("confidence", 0)
        state["reasoning_chain"].append(f"[{key}] {direction} ({confidence}%)")

    # ── Stage 3: Session Trader synthesis (Opus) ─────────────────────────
    trader_result = await _trader.analyze(state)
    state["session_trader_signal"] = trader_result
    state["reasoning_chain"].append(
        f"[SessionTrader] {trader_result.get('direction', 'NEUTRAL')} "
        f"({trader_result.get('confidence', 0)}%) — "
        f"{trader_result.get('trade_type', 'NO_TRADE')}"
    )

    # ── Stage 4: Coach overlay (non-blocking) ────────────────────────────
    coach_result = await _coach.analyze(state)
    state["coach_feedback"] = coach_result
    if coach_result.get("tilt_detected"):
        state["reasoning_chain"].append(
            f"[Coach] TILT: {coach_result.get('tilt_type')} "
            f"(severity {coach_result.get('tilt_severity')}/10)"
        )

    # ── Stage 5: Session Risk Gate (14 rules, pure Python) ───────────────
    gate_result = run_session_risk_gate(state)
    state["session_risk_gate_result"] = gate_result
    if not gate_result["passed"]:
        state["reasoning_chain"].append(
            f"[RiskGate] BLOCKED — {', '.join(r['name'] for r in gate_result['triggered_rules'][:3])}"
        )

    # ── Build final output ───────────────────────────────────────────────
    elapsed_ms = int((time.time() - t0) * 1000)

    signal = trader_result.copy()
    signal.update({
        "ticker": ticker,
        "mode": "SESSION",
        "strategy_profile": profile,
        "kill_zone": timer_result.get("kill_zone", "NONE"),
        "kill_zone_active": timer_result.get("kill_zone_active", False),
        "kill_zone_minutes_remaining": timer_result.get("kill_zone_minutes_remaining", 0),
        "market_phase": timer_result.get("market_phase", "UNKNOWN"),
        "risk_gate_passed": gate_result["passed"],
        "risk_gate_mode": gate_result["mode"],
        "risk_gate_rules": gate_result["triggered_rules"],
        "coach": coach_result,
        "session_risk": state.get("session_risk", {}),
        "agent_votes": _build_agent_votes(state),
        "reasoning_chain": state["reasoning_chain"],
        "pipeline_latency_ms": elapsed_ms,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # Override direction if blocked
    if not gate_result["passed"]:
        signal["direction"] = "NEUTRAL"
        signal["trade_type"] = "NO_TRADE"
        signal["urgency"] = "NO_TRADE"

    return signal


def _build_agent_votes(state: SessionState) -> list[dict]:
    """Extract direction + confidence from each session agent for frontend display."""
    votes = []
    for key, label in [
        ("session_technical", "Technical"),
        ("session_sentiment", "Sentiment"),
        ("session_order_flow", "OrderFlow"),
        ("session_correlation", "Correlation"),
        ("session_risk", "Risk"),
    ]:
        data = state.get(key, {})
        votes.append({
            "agent": label,
            "direction": data.get("direction", "NEUTRAL"),
            "confidence": data.get("confidence", 0),
        })
    return votes
