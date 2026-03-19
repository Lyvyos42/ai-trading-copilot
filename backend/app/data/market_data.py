"""
Market data provider — fetches from Yahoo Finance via yfinance (free, no API key),
and falls back to realistic deterministic mock data when offline or ticker not found.
"""
import asyncio
import random
from datetime import datetime, timedelta
from app.config import settings


def _price_decimals(price: float) -> int:
    """Return appropriate decimal places based on price magnitude."""
    if price < 0.001:  return 6   # tiny crypto
    if price < 0.1:   return 5
    if price < 10:    return 4    # FX pairs (EURUSD=X ~1.08), small crypto
    if price < 100:   return 3
    return 2                      # stocks, futures, indices


def _compute_atr(highs: list, lows: list, closes: list, period: int = 14) -> float:
    """Average True Range — measures volatility for ATR-based stop placement."""
    if len(closes) < 2:
        return closes[-1] * 0.01
    trs = []
    for i in range(1, len(closes)):
        h, l, pc = highs[i], lows[i], closes[i - 1]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    recent = trs[-period:]
    return sum(recent) / len(recent) if recent else closes[-1] * 0.01


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
        # Futures front-month contracts only have ~3 months of data before rolling.
        # Use a shorter period for futures/FX tickers to avoid empty history.
        is_futures_or_fx = ticker.endswith("=F") or ticker.endswith("=X")
        period = "3mo" if is_futures_or_fx else "1y"
        hist = tk.history(period=period, interval="1d", auto_adjust=True)
        if hist.empty:
            raise ValueError(f"No data returned for {ticker}")

        info = {}
        try:
            info = tk.info or {}
        except Exception:
            pass

        # Determine decimal precision from price magnitude
        sample_price = float(hist["Close"].iloc[-1])
        dec = _price_decimals(sample_price)

        closes  = [round(float(p), dec) for p in hist["Close"].tolist()]
        highs   = [round(float(p), dec) for p in hist["High"].tolist()]
        lows    = [round(float(p), dec) for p in hist["Low"].tolist()]
        volumes = [int(v) for v in hist["Volume"].tolist()]

        current_close = closes[-1]
        prev_close    = closes[-2] if len(closes) >= 2 else current_close

        price_change_pct = round((current_close - prev_close) / prev_close * 100, 2) if prev_close else 0.0

        avg_vol_30 = sum(volumes[-30:]) / 30 if len(volumes) >= 30 else (volumes[-1] or 1)
        volume_ratio = round(volumes[-1] / avg_vol_30, 2) if avg_vol_30 else 1.0

        # ATR (14-period, True Range)
        atr = _compute_atr(highs, lows, closes)

        return {
            "ticker": ticker,
            "asset_class": "stocks",
            "close": current_close,
            "open":  round(float(hist["Open"].iloc[-1]), dec),
            "high":  highs[-1],
            "low":   lows[-1],
            "volume": volumes[-1],
            "closes": closes,
            "highs":  highs,
            "lows":   lows,
            "price_change_pct": price_change_pct,
            "volume_ratio": volume_ratio,
            "atr": round(atr, dec),
            "price_decimals": dec,
            # Fundamentals — present in info dict for most US equities
            "pe_ratio":        info.get("trailingPE") or info.get("forwardPE"),
            "pb_ratio":        info.get("priceToBook"),
            "eps_growth":      info.get("earningsGrowth"),
            "revenue_growth":  info.get("revenueGrowth"),
            "dividend_yield":  info.get("dividendYield"),
            "earnings_surprise": None,  # not available via yfinance
        }

    return await asyncio.to_thread(_sync_fetch)


# Realistic approximate prices for well-known tickers (updated Mar 2026).
# Used when yfinance is unavailable so the mock is plausible, not random.
_KNOWN_PRICES: dict[str, float] = {
    # US Large-Cap Stocks
    "AAPL": 225.0, "MSFT": 415.0, "NVDA": 875.0, "GOOGL": 175.0, "AMZN": 200.0,
    "META": 600.0, "TSLA": 195.0, "JPM": 240.0, "V": 290.0, "MA": 490.0,
    "BRK.B": 460.0, "XOM": 115.0, "CVX": 155.0, "WMT": 95.0, "HD": 380.0,
    "GS": 580.0, "BAC": 44.0, "MS": 130.0, "NFLX": 980.0, "AMD": 125.0,
    "INTC": 22.0, "PYPL": 75.0, "COST": 920.0, "SBUX": 95.0, "TGT": 135.0,
    # ETFs
    "SPY": 560.0, "QQQ": 475.0, "IWM": 215.0, "GLD": 265.0, "TLT": 93.0,
    "XLK": 225.0, "XLE": 88.0, "DIA": 425.0, "IEF": 96.0, "HYG": 77.0, "LQD": 108.0,
    # Crypto (USD)
    "BTC-USD": 83000.0, "ETH-USD": 2000.0, "SOL-USD": 130.0,
    "XRP-USD": 2.5, "DOGE-USD": 0.18, "BNB-USD": 590.0,
    # FX (price of 1 unit of base currency in USD)
    "EURUSD=X": 1.085, "GBPUSD=X": 1.295, "USDJPY=X": 148.5,
    "AUDUSD=X": 0.635, "USDCAD=X": 1.355, "USDCHF=X": 0.895,
    # Commodities Futures (USD per unit, standard contract price)
    "GC=F": 3050.0,   # Gold $/troy oz
    "SI=F": 34.5,     # Silver $/troy oz
    "CL=F": 68.0,     # WTI Crude $/bbl
    "BZ=F": 72.0,     # Brent Crude $/bbl
    "NG=F": 4.2,      # Natural Gas $/MMBtu
    "HG=F": 4.55,     # Copper $/lb
    "ZC=F": 480.0,    # Corn ¢/bushel (quoted in cents)
    "ZW=F": 555.0,    # Wheat ¢/bushel
    # Fixed Income
    "ZN=F": 108.5, "ZB=F": 117.0,
    # Equity Index Futures
    "ES=F": 5700.0, "NQ=F": 20100.0, "RTY=F": 2175.0, "YM=F": 42800.0,
}

# Asset-class price ranges for unknown tickers
_CLASS_PRICE_RANGE: dict[str, tuple[float, float]] = {
    "stocks":       (15.0,   600.0),
    "etfs":         (30.0,   600.0),
    "crypto":       (0.05, 80000.0),
    "fx":           (0.60,     2.0),
    "commodities":  (2.0,   3500.0),
    "fixed_income": (70.0,   130.0),
    "futures":      (20.0,  6000.0),
}


def _mock_market_data(ticker: str, asset_class: str) -> dict:
    """Deterministic realistic mock data for demo / offline mode."""
    rng = random.Random(sum(ord(c) for c in ticker))

    # Use known price if available, otherwise derive from asset class range.
    # For known tickers we PIN the current price so the signal prices are realistic.
    known = ticker in _KNOWN_PRICES
    if known:
        current_price = _KNOWN_PRICES[ticker]
    else:
        lo, hi = _CLASS_PRICE_RANGE.get(asset_class, (15.0, 600.0))
        current_price = rng.uniform(lo, hi)

    # Simulate 260 bars of history ending at current_price.
    # Generate 259 steps backward (mean-reverting) then pin the last bar.
    num_bars = 260
    decimals = _price_decimals(current_price)

    # Build history: walk backward from current so it ends at the right price
    history = [current_price]
    for _ in range(num_bars - 1):
        change = rng.gauss(0.0001, 0.012)
        history.append(round(history[-1] / (1 + change), decimals))
    history.reverse()  # oldest → newest, last bar = current_price

    closes = history
    highs  = [round(c + c * rng.uniform(0.003, 0.018), decimals) for c in closes]
    lows   = [round(c - c * rng.uniform(0.003, 0.018), decimals) for c in closes]

    current_close = closes[-1]
    prev_close    = closes[-2]
    price_change_pct = round((current_close - prev_close) / prev_close * 100, 2)

    return {
        "ticker": ticker,
        "asset_class": asset_class,
        "close": round(current_close, decimals),
        "open":  round(closes[-2] * (1 + rng.uniform(-0.005, 0.005)), decimals),
        "high":  highs[-1],
        "low":   lows[-1],
        "volume": rng.randint(500_000, 50_000_000),
        "closes": closes,
        "highs":  highs,
        "lows":   lows,
        "price_change_pct": price_change_pct,
        "volume_ratio": round(rng.uniform(0.5, 3.0), 2),
        "atr": round(current_price * 0.012, decimals),  # ~1.2% ATR for mock
        "price_decimals": decimals,
        "pe_ratio":        round(rng.uniform(8, 45), 1),
        "pb_ratio":        round(rng.uniform(0.8, 8.0), 2),
        "eps_growth":      round(rng.uniform(-15, 40), 1),
        "revenue_growth":  round(rng.uniform(-5, 30), 1),
        "dividend_yield":  round(rng.uniform(0, 4.5), 2),
        "earnings_surprise": round(rng.uniform(-10, 15), 1),
    }
