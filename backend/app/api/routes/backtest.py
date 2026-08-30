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
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.jwt import get_current_user
from app.services.backtest_engine import (
    STRATEGIES as _ENGINE_STRATEGIES,
    fetch_ohlcv,
    run_strategy_backtest,
)

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])

STRATEGIES = {
    name: {"ref": spec["ref"], "description": spec["description"]}
    for name, spec in _ENGINE_STRATEGIES.items()
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

_REST_RANGE = {"5m": "1mo", "15m": "1mo", "1h": "2y", "4h": "2y", "1d": "5y", "1w": "5y"}
_REST_INTERVAL = {"5m": "5m", "15m": "15m", "1h": "1h", "4h": "1h", "1d": "1d", "1w": "1wk"}


def _fetch_real(symbol: str, timeframe: str) -> list:
    """Real bars from the Yahoo chart REST API.

    Previously went through yfinance, which fails on hosts that cannot verify
    Yahoo's certificate chain — and the caller silently swapped in generated
    candles when it did, so the failure was invisible. This endpoint is the one
    the signal resolver already relies on.
    """
    rows = fetch_ohlcv(symbol, _REST_INTERVAL.get(timeframe, "1d"),
                       _REST_RANGE.get(timeframe, "2y"))
    if timeframe == "4h" and rows:
        # Yahoo has no native 4h bar; fold hourly bars into 4-hour buckets.
        folded, bucket = [], None
        for r in rows:
            key = r["time"] - (r["time"] % 14400)
            if bucket is None or bucket["time"] != key:
                if bucket:
                    folded.append(bucket)
                bucket = {**r, "time": key}
            else:
                bucket["high"] = max(bucket["high"], r["high"])
                bucket["low"] = min(bucket["low"], r["low"])
                bucket["close"] = r["close"]
                bucket["volume"] += r["volume"]
        if bucket:
            folded.append(bucket)
        rows = folded
    return rows


def _build_ohlcv(symbol: str, timeframe: str, years: int) -> list:
    """Return real bars only.

    This used to pad thin history with generated candles — unlabelled, drawn on
    the chart next to real ones (those generators are now deleted). Yahoo only
    retains ~60d of 5m/15m data; the honest answer to "show me 2 years of 5m bars"
    is fewer bars, not fabricated ones.
    """
    rows = _fetch_real(symbol, timeframe)
    seen, out = set(), []
    for r in sorted(rows, key=lambda x: x["time"]):
        if r["time"] not in seen:
            seen.add(r["time"])
            out.append(r)
    return out


@router.get("/ohlcv")
async def get_ohlcv(
    symbol:    str = Query("EURUSD"),
    timeframe: str = Query("1d"),
    years:     int = Query(2, ge=1, le=5),
    _user: dict = Depends(get_current_user),
):
    tf = timeframe.lower()
    if tf not in _YF_LIMITS:
        raise HTTPException(400, f"Unsupported timeframe. Use: {list(_YF_LIMITS.keys())}")
    loop = asyncio.get_event_loop()
    rows = await loop.run_in_executor(_pool, _build_ohlcv, symbol, tf, years)
    if not rows:
        raise HTTPException(422, f"No market data available for {symbol.upper()} at {tf}")
    return {
        "symbol": symbol.upper(), "timeframe": tf, "years": years,
        "bars": len(rows), "data": rows,
        "synthetic": False,
        "coverage_days": round((rows[-1]["time"] - rows[0]["time"]) / 86400, 1),
        "retention_note": _YF_LIMITS.get(tf),
    }


@router.get("/{strategy}")
async def run_backtest(
    strategy: str,
    ticker: str = Query(default="SPY"),
    period: str = Query(default="1Y", pattern="^(1Y|2Y|3Y|5Y)$"),
    _user: dict = Depends(get_current_user),
):
    strategy = strategy.lower().replace("-", "_")
    if strategy not in STRATEGIES:
        raise HTTPException(
            status_code=404,
            detail=f"Strategy '{strategy}' not found. Available: {list(STRATEGIES.keys())}",
        )
    try:
        return run_strategy_backtest(strategy, ticker.upper(), period)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"backtest failed: {exc}")


@router.get("")
async def list_strategies(_user: dict = Depends(get_current_user)):
    return {
        "strategies": [
            {"name": k, "ref": v["ref"], "description": v["description"]}
            for k, v in STRATEGIES.items()
        ]
    }
