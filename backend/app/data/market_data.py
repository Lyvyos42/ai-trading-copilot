"""
Market data provider — fetches from Yahoo Finance via yfinance (free, no API key),
and falls back to realistic deterministic mock data when offline or ticker not found.
"""
import asyncio
import random
from datetime import datetime, timedelta
from app.config import settings


async def fetch_market_data(ticker: str, asset_class: str = "stocks") -> dict:
    """Main entry point. Returns a unified market data dict for a given ticker."""
    try:
        return await _fetch_yfinance(ticker)
    except Exception:
        return _mock_market_data(ticker, asset_class)


async def _fetch_yfinance(ticker: str) -> dict:
    """Fetch OHLCV + fundamentals from Yahoo Finance (free, no key required)."""
    import yfinance as yf  # lazy import so missing package degrades gracefully

    def _sync_fetch():
        tk = yf.Ticker(ticker)
        hist = tk.history(period="1y", interval="1d", auto_adjust=True)
        if hist.empty:
            raise ValueError(f"No data returned for {ticker}")

        info = {}
        try:
            info = tk.info or {}
        except Exception:
            pass

        closes = [round(float(p), 2) for p in hist["Close"].tolist()]
        highs  = [round(float(p), 2) for p in hist["High"].tolist()]
        lows   = [round(float(p), 2) for p in hist["Low"].tolist()]
        volumes = [int(v) for v in hist["Volume"].tolist()]

        current_close = closes[-1]
        prev_close    = closes[-2] if len(closes) >= 2 else current_close

        price_change_pct = round((current_close - prev_close) / prev_close * 100, 2) if prev_close else 0.0

        avg_vol_30 = sum(volumes[-30:]) / 30 if len(volumes) >= 30 else (volumes[-1] or 1)
        volume_ratio = round(volumes[-1] / avg_vol_30, 2) if avg_vol_30 else 1.0

        return {
            "ticker": ticker,
            "asset_class": "stocks",
            "close": current_close,
            "open":  round(float(hist["Open"].iloc[-1]), 2),
            "high":  highs[-1],
            "low":   lows[-1],
            "volume": volumes[-1],
            "closes": closes,
            "highs":  highs,
            "lows":   lows,
            "price_change_pct": price_change_pct,
            "volume_ratio": volume_ratio,
            # Fundamentals — present in info dict for most US equities
            "pe_ratio":        info.get("trailingPE") or info.get("forwardPE"),
            "pb_ratio":        info.get("priceToBook"),
            "eps_growth":      info.get("earningsGrowth"),
            "revenue_growth":  info.get("revenueGrowth"),
            "dividend_yield":  info.get("dividendYield"),
            "earnings_surprise": None,  # not available via yfinance
        }

    return await asyncio.to_thread(_sync_fetch)


def _mock_market_data(ticker: str, asset_class: str) -> dict:
    """Deterministic realistic mock data for demo / offline mode."""
    rng = random.Random(sum(ord(c) for c in ticker))
    base_price = rng.uniform(20, 800)
    num_bars = 260

    closes = [base_price]
    highs  = []
    lows   = []
    for _ in range(num_bars - 1):
        change = rng.gauss(0.0003, 0.015)
        new_close = closes[-1] * (1 + change)
        closes.append(round(new_close, 2))
    for c in closes:
        daily_range = c * rng.uniform(0.005, 0.025)
        highs.append(round(c + daily_range, 2))
        lows.append(round(c - daily_range, 2))

    current_close = closes[-1]
    prev_close    = closes[-2]
    price_change_pct = round((current_close - prev_close) / prev_close * 100, 2)

    return {
        "ticker": ticker,
        "asset_class": asset_class,
        "close": round(current_close, 2),
        "open":  round(closes[-2] * (1 + rng.uniform(-0.005, 0.005)), 2),
        "high":  highs[-1],
        "low":   lows[-1],
        "volume": rng.randint(500_000, 50_000_000),
        "closes": closes,
        "highs":  highs,
        "lows":   lows,
        "price_change_pct": price_change_pct,
        "volume_ratio": round(rng.uniform(0.5, 3.0), 2),
        "pe_ratio":        round(rng.uniform(8, 45), 1),
        "pb_ratio":        round(rng.uniform(0.8, 8.0), 2),
        "eps_growth":      round(rng.uniform(-15, 40), 1),
        "revenue_growth":  round(rng.uniform(-5, 30), 1),
        "dividend_yield":  round(rng.uniform(0, 4.5), 2),
        "earnings_surprise": round(rng.uniform(-10, 15), 1),
    }
