"""
Backtest routes:
  GET /api/v1/backtest/ohlcv          — OHLCV candlestick data for the chart
  GET /api/v1/backtest/{strategy}     — strategy simulation
  GET /api/v1/backtest               — list strategies
"""
import asyncio
import random
import math
from concurrent.futures import ThreadPoolExecutor
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


# ── OHLCV helpers ─────────────────────────────────────────────────────────────
_pool = ThreadPoolExecutor(max_workers=2)

_YF_LIMITS = {"5m":"60d","15m":"60d","1h":"730d","4h":"730d","1d":"5y","1w":"5y"}
_YF_INTERVALS = {"5m":"5m","15m":"15m","1h":"60m","4h":"60m","1d":"1d","1w":"1wk"}
_BARS_PER_DAY = {"5m":288,"15m":96}
_FOREX = {"EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","USDCHF","NZDUSD",
          "EURGBP","EURJPY","GBPJPY","XAUUSD","XAGUSD","USOIL","UKOIL","NATGAS"}

_SYMBOL_MAP = {
    "XAUUSD":"GC=F","XAGUSD":"SI=F",
    "EURUSD":"EURUSD=X","GBPUSD":"GBPUSD=X","USDJPY":"USDJPY=X",
    "AUDUSD":"AUDUSD=X","USDCAD":"USDCAD=X","USDCHF":"USDCHF=X",
    "NZDUSD":"NZDUSD=X","EURGBP":"EURGBP=X","EURJPY":"EURJPY=X","GBPJPY":"GBPJPY=X",
    "BTCUSD":"BTC-USD","ETHUSD":"ETH-USD",
    "USOIL":"CL=F","UKOIL":"BZ=F","NATGAS":"NG=F",
    "SPX500":"^GSPC","NAS100":"^NDX","GER40":"^GDAXI","UK100":"^FTSE","JPN225":"^N225",
}

def _fetch_real(symbol: str, timeframe: str) -> list:
    try:
        import yfinance as yf
    except ImportError:
        return []
    yf_sym   = _SYMBOL_MAP.get(symbol.upper(), symbol)
    interval = _YF_INTERVALS.get(timeframe, "1d")
    period   = _YF_LIMITS.get(timeframe, "5y")
    try:
        df = yf.download(yf_sym, period=period, interval=interval, progress=False, auto_adjust=True)
        if df is None or df.empty:
            return []
        if hasattr(df.columns, "get_level_values"):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()
        for col in ("Datetime","Date"):
            if col in df.columns:
                df = df.rename(columns={col:"dt"})
                break
        if timeframe == "4h":
            df = df.set_index("dt").resample("4h").agg(
                {"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}
            ).dropna().reset_index().rename(columns={"dt":"dt"})
        rows = []
        for _, r in df.iterrows():
            try:
                ts = int(r["dt"].timestamp()) if hasattr(r["dt"],"timestamp") else int(r["dt"])
                rows.append({"time":ts,"open":round(float(r["Open"]),6),"high":round(float(r["High"]),6),
                             "low":round(float(r["Low"]),6),"close":round(float(r["Close"]),6),
                             "volume":int(float(r["Volume"]) if not math.isnan(float(r["Volume"])) else 0)})
            except Exception:
                continue
        return rows
    except Exception:
        return []

def _synthetic_daily(symbol: str, days: int = 730) -> list:
    import yfinance as yf
    _SEED = {"EURUSD":1.085,"GBPUSD":1.295,"USDJPY":148.5,"XAUUSD":3100,
             "BTCUSD":83000,"ETHUSD":2000,"USOIL":68.0,"SPX500":5700,"NAS100":20100}
    price = _SEED.get(symbol.upper(), 100.0)
    try:
        tk = yf.Ticker(_SYMBOL_MAP.get(symbol.upper(), symbol))
        h  = tk.history(period="5d", interval="1d")
        if not h.empty:
            price = float(h["Close"].iloc[-1])
    except Exception:
        pass
    rng  = random.Random(sum(ord(c) for c in symbol))
    vol  = 0.012
    rows = []
    from datetime import date, timedelta
    day  = date.today() - timedelta(days=days)
    cur  = price / (1 + rng.gauss(0, vol)) ** days
    for _ in range(days):
        day += timedelta(days=1)
        if day.weekday() >= 5 and symbol.upper() not in _FOREX:
            continue
        ret   = rng.gauss(0.0001, vol)
        close = max(cur * (1 + ret), cur * 0.001)
        high  = close * (1 + abs(rng.gauss(0, vol * 0.6)))
        low   = close * (1 - abs(rng.gauss(0, vol * 0.6)))
        ts    = int((day - date(1970,1,1)).total_seconds() if hasattr(date(1970,1,1),"total_seconds") else (day - date(1970,1,1)).days * 86400)
        rows.append({"time":ts,"open":round(cur,6),"high":round(max(cur,high,close),6),
                     "low":round(min(cur,low,close),6),"close":round(close,6),
                     "volume":rng.randint(100_000,50_000_000)})
        cur = close
    return rows

def _expand_to_intraday(daily: list, bars_per_day: int, symbol: str) -> list:
    rng = random.Random(sum(ord(c) for c in symbol) + bars_per_day)
    rows = []
    bar_s = 86400 // bars_per_day
    for day in daily:
        o,h,l,c = day["open"],day["high"],day["low"],day["close"]
        ts  = day["time"]
        vol = (h - l) / bars_per_day if h > l else abs(c) * 0.0002
        prices = [o]
        for i in range(1, bars_per_day):
            drift = (c - prices[-1]) / (bars_per_day - i)
            prices.append(max(l, min(h, prices[-1] + drift + rng.gauss(0, vol * 0.5))))
        for i in range(bars_per_day):
            po = prices[i-1] if i > 0 else o
            pc = prices[i]
            rows.append({"time":ts + i * bar_s,"open":round(po,6),"high":round(min(h,max(po,pc)*(1+abs(rng.gauss(0,0.0003)))),6),
                         "low":round(max(l,min(po,pc)*(1-abs(rng.gauss(0,0.0003)))),6),"close":round(pc,6),
                         "volume":int((day["volume"]/bars_per_day)*rng.uniform(0.4,1.8))})
    return rows

def _build_ohlcv(symbol: str, timeframe: str, years: int) -> list:
    rows = _fetch_real(symbol, timeframe)
    if timeframe in ("5m","15m"):
        bpd    = _BARS_PER_DAY[timeframe]
        daily  = _synthetic_daily(symbol, days=years*365)
        if rows:
            cutoff = rows[0]["time"] - 86400
            daily  = [d for d in daily if d["time"] < cutoff]
        rows = _expand_to_intraday(daily, bpd, symbol) + rows
    elif not rows:
        daily = _synthetic_daily(symbol, days=years*365)
        if timeframe == "1w":
            weekly, wo, wh, wl, wc, wv, wts = [], None, 0, 1e18, 0, 0, 0
            for d in daily:
                if wo is None:
                    wo,wh,wl,wts = d["open"],d["high"],d["low"],d["time"]
                wh = max(wh,d["high"]); wl = min(wl,d["low"]); wc = d["close"]; wv += d["volume"]
                if d["time"] >= wts + 5*86400:
                    weekly.append({"time":wts,"open":wo,"high":wh,"low":wl,"close":wc,"volume":wv})
                    wo = None; wh = 0; wl = 1e18; wv = 0
            rows = weekly
        else:
            rows = daily
    seen,out = set(),[]
    for r in sorted(rows, key=lambda x: x["time"]):
        if r["time"] not in seen:
            seen.add(r["time"]); out.append(r)
    return out


@router.get("/ohlcv")
async def get_ohlcv(
    symbol:    str = Query("EURUSD"),
    timeframe: str = Query("1d"),
    years:     int = Query(2, ge=1, le=5),
):
    tf = timeframe.lower()
    if tf not in _YF_LIMITS:
        raise HTTPException(400, f"Unsupported timeframe. Use: {list(_YF_LIMITS.keys())}")
    loop = asyncio.get_event_loop()
    rows = await loop.run_in_executor(_pool, _build_ohlcv, symbol, tf, years)
    return {"symbol":symbol.upper(),"timeframe":tf,"years":years,"bars":len(rows),"data":rows}


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
