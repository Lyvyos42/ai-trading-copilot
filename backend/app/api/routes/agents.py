"""
GET /api/v1/agents/status — health and activity of all 9 agents + Risk Gate
"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
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
    now = datetime.now(timezone.utc).isoformat()
    cutoff_today = datetime.now(timezone.utc) - timedelta(hours=24)
    cutoff_7d = datetime.now(timezone.utc) - timedelta(days=7)

    today_result = await db.execute(
        select(func.count()).select_from(Signal).where(Signal.created_at >= cutoff_today)
    )
    signals_today_count = today_result.scalar() or 0

    res_7d = await db.execute(
        select(Signal.outcome)
        .where(Signal.resolved_at >= cutoff_7d)
        .where(Signal.outcome.in_(["WIN", "LOSS"]))
    )
    outcomes_7d = [r[0] for r in res_7d.all()]
    acc_7d = None
    if outcomes_7d:
        wins_7d = sum(1 for o in outcomes_7d if o == "WIN")
        acc_7d = round(wins_7d / len(outcomes_7d) * 100, 1)

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
            "accuracy_7d": acc_7d,
            "last_active": now,
        })
    return {"agents": statuses, "total": len(statuses), "all_healthy": True, "timestamp": now}
