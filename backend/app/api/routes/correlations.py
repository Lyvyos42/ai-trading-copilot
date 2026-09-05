"""
Correlation Matrix — rolling correlation heatmap data.
GET /api/v1/correlations/matrix
GET /api/v1/correlations/pair
"""
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from fastapi import APIRouter, Depends, Query

from app.auth.jwt import get_current_user

router = APIRouter(prefix="/api/v1/correlations", tags=["correlations"])

_pool = ThreadPoolExecutor(max_workers=2)

# Default watchlist
_DEFAULT_TICKERS = ["SPY", "QQQ", "IWM", "TLT", "GLD", "BTC-USD", "EURUSD=X"]

_SYMBOL_MAP = {
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "XAUUSD": "GC=F", "XAGUSD": "SI=F",
    "USOIL": "CL=F", "VIX": "^VIX",
}

# Simple cache: {cache_key: (expires_at, data)}
_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 3600  # 1 hour


def _resolve_symbol(ticker: str) -> str:
    return _SYMBOL_MAP.get(ticker.upper(), ticker)


def _compute_matrix(tickers: list[str], period_days: int) -> dict:
    try:
        import yfinance as yf
        import pandas as pd
    except ImportError:
        return _unavailable_matrix(tickers, "price library not installed")

    symbols = [_resolve_symbol(t) for t in tickers]
    try:
        data = yf.download(
            symbols, period=f"{period_days}d", interval="1d",
            auto_adjust=True, progress=False, threads=True,
        )
        if data.empty:
            return _unavailable_matrix(tickers, "the price feed returned no data")

        # Extract close prices
        if isinstance(data.columns, pd.MultiIndex):
            closes = data["Close"]
        else:
            closes = data[["Close"]]
            closes.columns = symbols

        # Compute returns and correlation
        returns = closes.pct_change().dropna()
        if len(returns) < 10:
            return _unavailable_matrix(
                tickers, f"only {len(returns)} overlapping days of returns - too few to correlate")

        corr = returns.corr()

        # Build matrix with original ticker labels
        matrix = []
        for i, sym in enumerate(symbols):
            row = []
            for j, sym2 in enumerate(symbols):
                val = corr.iloc[i, j]
                row.append(round(float(val), 3) if not (val != val) else 0.0)
            matrix.append(row)

        return {
            "tickers": tickers,
            "matrix": matrix,
            "period_days": period_days,
            "data_points": len(returns),
        }
    except Exception as exc:
        return _unavailable_matrix(tickers, f"price fetch failed ({type(exc).__name__})")


def _unavailable_matrix(tickers: list[str], reason: str) -> dict:
    """No correlation data. Says so, rather than inventing a matrix.

    This replaced _synthetic_matrix, which built the whole grid from
    random.uniform inside hand-drawn bands - 0.75-0.95 for equity pairs,
    -0.5 to -0.1 for equity against safe havens, -0.3 to 0.5 for everything
    else - seeded on 42 so it looked stable between refreshes. It was
    returned through the normal response shape with data_points: 0, and the
    correlation map rendered it identically to a measured one.

    A correlation map exists to show which positions actually move together.
    Plausible-looking numbers are worse than none, because a diversification
    decision made against them feels informed.
    """
    n = len(tickers)
    matrix = [[1.0 if i == j else None for j in range(n)] for i in range(n)]
    return {
        "tickers": tickers,
        "matrix": matrix,
        "period_days": 90,
        "data_points": 0,
        "error": "no_data",
        "detail": f"Correlations unavailable: {reason}. No values are estimated.",
    }


def _compute_pair(t1: str, t2: str, period_days: int) -> dict:
    try:
        import yfinance as yf
    except ImportError:
        return {"t1": t1, "t2": t2, "series": [], "correlation": 0}

    s1, s2 = _resolve_symbol(t1), _resolve_symbol(t2)
    try:
        data = yf.download(
            [s1, s2], period=f"{period_days}d", interval="1d",
            auto_adjust=True, progress=False, threads=True,
        )
        if data.empty:
            return {"t1": t1, "t2": t2, "series": [], "correlation": 0}

        import pandas as pd
        if isinstance(data.columns, pd.MultiIndex):
            closes = data["Close"]
        else:
            closes = data[["Close"]]

        closes = closes.dropna()
        if len(closes) < 5:
            return {"t1": t1, "t2": t2, "series": [], "correlation": 0}

        # Rebase to 100
        base1 = float(closes.iloc[0, 0])
        base2 = float(closes.iloc[0, 1])
        series = []
        for idx, row in closes.iterrows():
            series.append({
                "date": idx.strftime("%Y-%m-%d"),
                "v1": round(float(row.iloc[0]) / base1 * 100, 2),
                "v2": round(float(row.iloc[1]) / base2 * 100, 2),
            })

        corr_val = float(closes.pct_change().dropna().corr().iloc[0, 1])
        return {
            "t1": t1, "t2": t2,
            "series": series,
            "correlation": round(corr_val, 3),
        }
    except Exception:
        return {"t1": t1, "t2": t2, "series": [], "correlation": 0}


@router.get("/matrix")
async def get_correlation_matrix(
    tickers: str = Query(None, description="Comma-separated tickers"),
    period: int = Query(90, ge=30, le=365, description="Lookback period in days"),
    _user: dict = Depends(get_current_user),
):
    ticker_list = [t.strip() for t in tickers.split(",")] if tickers else _DEFAULT_TICKERS

    cache_key = f"{','.join(ticker_list)}:{period}"
    cached = _cache.get(cache_key)
    if cached and time.time() < cached[0]:
        return cached[1]

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_pool, _compute_matrix, ticker_list, period)

    _cache[cache_key] = (time.time() + _CACHE_TTL, result)
    return result


@router.get("/pair")
async def get_correlation_pair(
    t1: str = Query(..., description="First ticker"),
    t2: str = Query(..., description="Second ticker"),
    period: int = Query(90, ge=30, le=365),
    _user: dict = Depends(get_current_user),
):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_pool, _compute_pair, t1, t2, period)
    return result
