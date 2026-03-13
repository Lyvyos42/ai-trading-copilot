"""
GET /api/v1/backtest/{strategy} — run historical backtest simulation for a strategy
"""
import random
import math
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])

STRATEGIES = {
    "price_momentum": {"ref": "3.1", "description": "Cross-sectional 12-1 month momentum"},
    "earnings_momentum": {"ref": "3.2", "description": "Earnings surprise and EPS revision"},
    "value": {"ref": "3.3", "description": "P/E, P/B, dividend yield ranking"},
    "pairs_trading": {"ref": "3.8", "description": "Cointegrated pair spread mean-reversion"},
    "mean_reversion": {"ref": "3.9", "description": "Cluster-demeaned Z-score entry"},
    "ema_crossover": {"ref": "3.11-3.13", "description": "SMA/EMA crossover systems"},
    "stat_arb": {"ref": "3.18", "description": "Markowitz optimization, dollar-neutral"},
    "alpha_combo": {"ref": "3.20", "description": "Weighted combination of multiple alpha signals"},
    "sector_rotation": {"ref": "4.1", "description": "Rotate into top-performing sector ETFs"},
    "carry_fixed_income": {"ref": "5.11", "description": "Yield curve carry optimization"},
    "vix_basis": {"ref": "7.2", "description": "VIX futures contango/backwardation"},
    "vol_risk_premium": {"ref": "7.4", "description": "Sell implied vs realized vol spread"},
    "fx_carry": {"ref": "8.2", "description": "Long high-yield, short low-yield currencies"},
    "fx_momentum": {"ref": "8.4", "description": "Combined FX momentum + carry"},
    "roll_yield": {"ref": "9.1", "description": "Commodities backwardation/contango"},
    "trend_following": {"ref": "10.4", "description": "Multi-asset momentum with risk parity"},
    "crypto_ann": {"ref": "18.2", "description": "Neural network with EMA/EMSD/RSI for crypto"},
    "crypto_sentiment": {"ref": "18.3", "description": "Twitter/Reddit NLP classification"},
    "macro_momentum": {"ref": "19.2", "description": "GDP/CPI/FX state variable ranking"},
    "announcement": {"ref": "19.5", "description": "FOMC/NFP event-day alpha"},
}


def _simulate_backtest(strategy_name: str, ticker: str, period: str) -> dict:
    """Generate deterministic, statistically plausible backtest results."""
    seed = sum(ord(c) for c in strategy_name + ticker + period)
    rng = random.Random(seed)

    # Core performance metrics
    annual_return = rng.uniform(0.04, 0.28)
    sharpe = rng.uniform(0.8, 2.4)
    max_dd = rng.uniform(0.05, 0.25)
    win_rate = rng.uniform(0.45, 0.68)
    total_trades = rng.randint(50, 400)
    avg_hold_days = rng.randint(1, 45)

    # Simulate monthly equity curve
    months = {"1Y": 12, "2Y": 24, "3Y": 36, "5Y": 60}.get(period, 12)
    equity = [100_000.0]
    monthly_ret = (1 + annual_return) ** (1 / 12) - 1
    monthly_vol = annual_return / (sharpe * math.sqrt(12))
    for _ in range(months):
        r = rng.gauss(monthly_ret, monthly_vol)
        equity.append(round(equity[-1] * (1 + r), 2))

    total_return = (equity[-1] - equity[0]) / equity[0]

    # Sample trades
    trades = []
    for i in range(min(total_trades, 20)):
        trade_seed = seed + i
        t_rng = random.Random(trade_seed)
        won = t_rng.random() < win_rate
        ret_pct = t_rng.uniform(1.5, 8) if won else t_rng.uniform(-3, -0.5)
        trades.append({
            "trade_num": i + 1,
            "direction": t_rng.choice(["LONG", "SHORT"]),
            "return_pct": round(ret_pct, 2),
            "hold_days": t_rng.randint(1, avg_hold_days * 2),
            "outcome": "WIN" if won else "LOSS",
        })

    return {
        "strategy": strategy_name,
        "strategy_ref": STRATEGIES.get(strategy_name, {}).get("ref", "N/A"),
        "description": STRATEGIES.get(strategy_name, {}).get("description", "Custom strategy"),
        "ticker": ticker,
        "period": period,
        "total_return_pct": round(total_return * 100, 2),
        "annual_return_pct": round(annual_return * 100, 2),
        "sharpe_ratio": round(sharpe, 3),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "win_rate_pct": round(win_rate * 100, 1),
        "total_trades": total_trades,
        "avg_hold_days": avg_hold_days,
        "calmar_ratio": round(annual_return / max_dd, 2),
        "profit_factor": round(rng.uniform(1.2, 2.8), 2),
        "equity_curve": equity,
        "sample_trades": trades,
        "note": "Simulated backtest for demonstration. Integrate LEAN/QuantConnect for production results.",
    }


@router.get("/{strategy}")
async def run_backtest(
    strategy: str,
    ticker: str = Query(default="SPY"),
    period: str = Query(default="1Y", pattern="^(1Y|2Y|3Y|5Y)$"),
):
    strategy = strategy.lower().replace("-", "_")
    if strategy not in STRATEGIES:
        raise HTTPException(
            status_code=404,
            detail=f"Strategy '{strategy}' not found. Available: {list(STRATEGIES.keys())}",
        )
    return _simulate_backtest(strategy, ticker.upper(), period)


@router.get("")
async def list_strategies():
    return {
        "strategies": [
            {"name": k, "ref": v["ref"], "description": v["description"]}
            for k, v in STRATEGIES.items()
        ]
    }
