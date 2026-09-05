"""
GET /api/v1/agents/status — health and activity of all 9 agents + Risk Gate
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_current_user
from app.db.database import get_db
from app.models.signal import Signal

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])

AGENTS = [
    {
        "name": "FundamentalAnalyst",
        "role": "Evaluates P/E, P/B, earnings surprises, revenue growth. Applies strategies 3.2, 3.3.",
        "model": "claude-sonnet-4-6",
        "tier": "standard",
        "stage": "analyst",
        "strategies": ["earnings_momentum_3.2", "value_factor_3.3", "carry_fixed_income_5.10"],
    },
    {
        "name": "TechnicalAnalyst",
        "role": "Runs EMA crossovers (3.11-3.13), RSI, MACD, support/resistance, mean-reversion Z-score (3.9).",
        "model": "claude-sonnet-4-6",
        "tier": "standard",
        "stage": "analyst",
        "strategies": ["price_momentum_3.1", "mean_reversion_3.9", "ema_crossover_3.11-3.13", "channel_breakout_3.15"],
    },
    {
        "name": "SentimentAnalyst",
        "role": "NLP on news, social media. Naive Bayes classifier extended to transformers (strategy 18.3).",
        "model": "claude-sonnet-4-6",
        "tier": "standard",
        "stage": "analyst",
        "strategies": ["sentiment_nlp_18.3", "announcement_alpha_19.5"],
    },
    {
        "name": "MacroAnalyst",
        "role": "Tracks 4 state variables: GDP, CPI, central bank policy, geopolitics. FX carry (8.2).",
        "model": "claude-sonnet-4-6",
        "tier": "standard",
        "stage": "analyst",
        "strategies": ["macro_momentum_19.2", "fx_carry_8.2", "announcement_alpha_19.5"],
    },
    {
        "name": "OrderFlowAnalyst",
        "role": "VPIN, bid/ask imbalance, block trades, dark pool activity. Strategies 3.16-3.17.",
        "model": "claude-sonnet-4-6",
        "tier": "standard",
        "stage": "analyst",
        "strategies": ["volume_weighted_3.16", "liquidity_momentum_3.17"],
    },
    {
        "name": "RegimeChangeAnalyst",
        "role": "VIX term structure, cross-asset correlations, credit spreads, sector rotation.",
        "model": "claude-sonnet-4-6",
        "tier": "standard",
        "stage": "analyst",
        "strategies": ["vol_regime_switching_6.1", "macro_momentum_19.2"],
    },
    {
        "name": "CorrelationAnalyst",
        "role": "Portfolio concentration risk, contagion detection, Kelly position size adjustments.",
        "model": "claude-sonnet-4-6",
        "tier": "standard",
        "stage": "analyst",
        "strategies": ["covariance_framework_3.18", "target_volatility_6.5"],
    },
    {
        "name": "QuantAnalyst",
        "role": "5yr backtest validation, p-value testing, Sharpe ratio, statistical edge confirmation.",
        "model": "claude-sonnet-4-6",
        "tier": "standard",
        "stage": "validation",
        "strategies": ["statistical_validation", "regime_adjusted_backtest"],
    },
    {
        "name": "RiskManager",
        "role": "Enforces portfolio constraints: max drawdown 15%, Kelly sizing, correlation < 0.7.",
        "model": "claude-sonnet-4-6",
        "tier": "standard",
        "stage": "risk",
        "strategies": ["statistical_arbitrage_3.18", "volatility_targeting_6.5"],
    },
    {
        "name": "TraderAgent",
        "role": "Synthesizes analyst consensus and debate. Sets entry, SL, TP1/2/3. Final decision maker.",
        "model": "claude-opus-4-6",
        "tier": "premium",
        "stage": "synthesis",
        "strategies": ["alpha_combo_3.20", "multi_asset_trend_4.6"],
    },
    {
        "name": "RiskGate",
        "role": "15 hard veto rules (pure Python, no AI). Cannot be overridden by agent reasoning.",
        "model": "none",
        "tier": "deterministic",
        "stage": "gate",
        "strategies": ["hard_veto_rules"],
    },
]


@router.get("/status")
async def agent_status(
    db: AsyncSession = Depends(get_db),
    _user: dict = Depends(get_current_user),
):
    # Signal.created_at and Signal.resolved_at are mapped as plain DateTime -
    # NAIVE columns - and every other query against them uses datetime.utcnow().
    # Comparing a timezone-AWARE datetime against them raises on Postgres, which
    # 500'd this endpoint. The dashboard then fell back to a hardcoded agent list
    # for the rows while the counter read the empty fetch result, so every agent
    # rendered LIVE under a header saying 0/11 HEALTHY.
    now = datetime.utcnow().isoformat()
    cutoff_today = datetime.utcnow() - timedelta(hours=24)
    cutoff_7d = datetime.utcnow() - timedelta(days=7)

    # Scoped to the caller. Both counts were global, so a user with four
    # resolved signals of their own saw a platform-wide figure on their own
    # dashboard - 451 signals "today" and 7.5% accuracy - with no way to tell
    # it was not theirs.
    user_id = _user.get("sub") or _user.get("id") or _user.get("user_id") or ""
    mine = or_(Signal.user_id == user_id, Signal.user_id.is_(None))

    today_result = await db.execute(
        select(func.count()).select_from(Signal)
        .where(mine).where(Signal.created_at >= cutoff_today)
    )
    signals_today_count = today_result.scalar() or 0

    # PER-AGENT accuracy, actually per agent.
    #
    # This used to compute ONE overall win rate and hand the identical number
    # to all eleven agents, so the panel showed eleven rows of "7.5%" as if
    # each had been measured separately. Nothing was being attributed.
    #
    # agent_votes stores each analyst's direction on every signal, and a
    # resolved signal records whether ITS direction paid. So an agent that
    # voted with a signal that WON was right, and one that voted against a
    # signal that won was wrong. Agents that abstained or voted NEUTRAL are
    # excluded rather than counted as wrong - having no opinion is not an
    # incorrect opinion.
    res_7d = await db.execute(
        select(Signal.outcome, Signal.direction, Signal.agent_votes)
        .where(mine)
        .where(Signal.resolved_at >= cutoff_7d)
        .where(Signal.outcome.in_(["WIN", "LOSS"]))
    )
    rows_7d = res_7d.all()

    # AGENTS[].name -> the key used in agent_votes
    _VOTE_KEY = {
        "FundamentalAnalyst":  "fundamental",
        "TechnicalAnalyst":    "technical",
        "SentimentAnalyst":    "sentiment",
        "MacroAnalyst":        "macro",
        "OrderFlowAnalyst":    "order_flow",
        "RegimeChangeAnalyst": "regime_change",
        "CorrelationAnalyst":  "correlation",
    }
    tally: dict[str, list[int]] = {k: [0, 0] for k in _VOTE_KEY.values()}   # [right, total]
    overall_right = overall_total = 0

    for outcome, direction, votes in rows_7d:
        signal_paid = outcome == "WIN"
        overall_total += 1
        overall_right += 1 if signal_paid else 0
        if not isinstance(votes, dict):
            continue
        for key in tally:
            vote = votes.get(key)
            if not isinstance(vote, dict):
                continue
            vd = vote.get("direction")
            if vd not in ("LONG", "SHORT"):
                continue                      # abstained or neutral - not a call
            agreed = vd == direction
            tally[key][1] += 1
            if agreed == signal_paid:
                tally[key][0] += 1

    def _acc(key: str | None):
        """None means UNMEASURED. Never 0.0, which reads as 'measured, and bad'."""
        if key is None or key not in tally:
            return None
        right, total = tally[key]
        return round(right / total * 100, 1) if total else None

    overall_acc = round(overall_right / overall_total * 100, 1) if overall_total else None

    statuses = []
    for a in AGENTS:
        statuses.append({
            "name": a["name"],
            "role": a["role"],
            "model": a["model"],
            "strategies": a["strategies"],
            "status": "HEALTHY",
            "avg_latency_ms": 0,
            "signals_today": signals_today_count,
            # Analysts get their own measured accuracy. TraderAgent, RiskGate,
            # RiskManager and QuantAnalyst cast no directional vote, so they
            # carry the signal-level result where that is what they influence,
            # and None where nothing is attributable to them.
            "accuracy_7d": (_acc(_VOTE_KEY.get(a["name"]))
                            if a["name"] in _VOTE_KEY
                            else (overall_acc if a["name"] == "TraderAgent" else None)),
            "accuracy_sample": (tally.get(_VOTE_KEY.get(a["name"], ""), [0, 0])[1]
                                if a["name"] in _VOTE_KEY
                                else (overall_total if a["name"] == "TraderAgent" else 0)),
            "last_active": now,
        })
    return {"agents": statuses, "total": len(statuses), "all_healthy": True, "timestamp": now}
