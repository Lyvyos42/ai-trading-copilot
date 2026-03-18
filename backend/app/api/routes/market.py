"""
Market data routes — OHLCV candles + symbol search.
No authentication required (public endpoints).
"""
from fastapi import APIRouter, Query
from app.data.market_data import fetch_market_data
import asyncio, random
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/market", tags=["market"])

# ── Symbol catalogue ──────────────────────────────────────────────────────────
SYMBOLS = {
    "stocks": [
        {"symbol":"AAPL","name":"Apple Inc.","exchange":"NASDAQ"},
        {"symbol":"MSFT","name":"Microsoft Corp.","exchange":"NASDAQ"},
        {"symbol":"NVDA","name":"NVIDIA Corp.","exchange":"NASDAQ"},
        {"symbol":"GOOGL","name":"Alphabet Inc.","exchange":"NASDAQ"},
        {"symbol":"AMZN","name":"Amazon.com Inc.","exchange":"NASDAQ"},
        {"symbol":"META","name":"Meta Platforms","exchange":"NASDAQ"},
        {"symbol":"TSLA","name":"Tesla Inc.","exchange":"NASDAQ"},
        {"symbol":"SPY","name":"S&P 500 ETF","exchange":"NYSE"},
        {"symbol":"QQQ","name":"Nasdaq 100 ETF","exchange":"NASDAQ"},
        {"symbol":"AMD","name":"Advanced Micro Devices","exchange":"NASDAQ"},
        {"symbol":"INTC","name":"Intel Corp.","exchange":"NASDAQ"},
        {"symbol":"NFLX","name":"Netflix Inc.","exchange":"NASDAQ"},
        {"symbol":"DIS","name":"Walt Disney Co.","exchange":"NYSE"},
        {"symbol":"JPM","name":"JPMorgan Chase","exchange":"NYSE"},
        {"symbol":"GS","name":"Goldman Sachs","exchange":"NYSE"},
        {"symbol":"BAC","name":"Bank of America","exchange":"NYSE"},
        {"symbol":"V","name":"Visa Inc.","exchange":"NYSE"},
        {"symbol":"MA","name":"Mastercard","exchange":"NYSE"},
        {"symbol":"JNJ","name":"Johnson & Johnson","exchange":"NYSE"},
        {"symbol":"WMT","name":"Walmart Inc.","exchange":"NYSE"},
        {"symbol":"XOM","name":"Exxon Mobil","exchange":"NYSE"},
        {"symbol":"CVX","name":"Chevron Corp.","exchange":"NYSE"},
        {"symbol":"UNH","name":"UnitedHealth Group","exchange":"NYSE"},
        {"symbol":"PG","name":"Procter & Gamble","exchange":"NYSE"},
        {"symbol":"HD","name":"Home Depot","exchange":"NYSE"},
        {"symbol":"KO","name":"Coca-Cola Co.","exchange":"NYSE"},
        {"symbol":"PEP","name":"PepsiCo Inc.","exchange":"NASDAQ"},
        {"symbol":"ABBV","name":"AbbVie Inc.","exchange":"NYSE"},
        {"symbol":"MRK","name":"Merck & Co.","exchange":"NYSE"},
        {"symbol":"LLY","name":"Eli Lilly","exchange":"NYSE"},
        {"symbol":"COST","name":"Costco Wholesale","exchange":"NASDAQ"},
        {"symbol":"MCD","name":"McDonald's Corp.","exchange":"NYSE"},
        {"symbol":"SBUX","name":"Starbucks Corp.","exchange":"NASDAQ"},
        {"symbol":"NKE","name":"Nike Inc.","exchange":"NYSE"},
        {"symbol":"BA","name":"Boeing Co.","exchange":"NYSE"},
        {"symbol":"CAT","name":"Caterpillar Inc.","exchange":"NYSE"},
        {"symbol":"GE","name":"GE Aerospace","exchange":"NYSE"},
        {"symbol":"IBM","name":"IBM Corp.","exchange":"NYSE"},
        {"symbol":"ORCL","name":"Oracle Corp.","exchange":"NYSE"},
        {"symbol":"CRM","name":"Salesforce Inc.","exchange":"NYSE"},
        {"symbol":"ADBE","name":"Adobe Inc.","exchange":"NASDAQ"},
        {"symbol":"PYPL","name":"PayPal Holdings","exchange":"NASDAQ"},
        {"symbol":"UBER","name":"Uber Technologies","exchange":"NYSE"},
        {"symbol":"LYFT","name":"Lyft Inc.","exchange":"NASDAQ"},
        {"symbol":"SNAP","name":"Snap Inc.","exchange":"NYSE"},
        {"symbol":"TWTR","name":"X Corp (Twitter)","exchange":"NYSE"},
        {"symbol":"RIVN","name":"Rivian Automotive","exchange":"NASDAQ"},
        {"symbol":"PLTR","name":"Palantir Technologies","exchange":"NYSE"},
        {"symbol":"SOFI","name":"SoFi Technologies","exchange":"NASDAQ"},
    ],
    "forex": [
        {"symbol":"EURUSD=X","name":"EUR/USD","exchange":"FX"},
        {"symbol":"GBPUSD=X","name":"GBP/USD","exchange":"FX"},
        {"symbol":"USDJPY=X","name":"USD/JPY","exchange":"FX"},
        {"symbol":"AUDUSD=X","name":"AUD/USD","exchange":"FX"},
        {"symbol":"USDCAD=X","name":"USD/CAD","exchange":"FX"},
        {"symbol":"USDCHF=X","name":"USD/CHF","exchange":"FX"},
        {"symbol":"NZDUSD=X","name":"NZD/USD","exchange":"FX"},
        {"symbol":"EURGBP=X","name":"EUR/GBP","exchange":"FX"},
        {"symbol":"EURJPY=X","name":"EUR/JPY","exchange":"FX"},
        {"symbol":"GBPJPY=X","name":"GBP/JPY","exchange":"FX"},
        {"symbol":"USDMXN=X","name":"USD/MXN","exchange":"FX"},
        {"symbol":"USDZAR=X","name":"USD/ZAR","exchange":"FX"},
    ],
    "crypto": [
        {"symbol":"BTC-USD","name":"Bitcoin","exchange":"CRYPTO"},
        {"symbol":"ETH-USD","name":"Ethereum","exchange":"CRYPTO"},
        {"symbol":"SOL-USD","name":"Solana","exchange":"CRYPTO"},
        {"symbol":"BNB-USD","name":"BNB","exchange":"CRYPTO"},
        {"symbol":"XRP-USD","name":"XRP","exchange":"CRYPTO"},
        {"symbol":"ADA-USD","name":"Cardano","exchange":"CRYPTO"},
        {"symbol":"DOGE-USD","name":"Dogecoin","exchange":"CRYPTO"},
        {"symbol":"AVAX-USD","name":"Avalanche","exchange":"CRYPTO"},
        {"symbol":"MATIC-USD","name":"Polygon","exchange":"CRYPTO"},
        {"symbol":"DOT-USD","name":"Polkadot","exchange":"CRYPTO"},
        {"symbol":"LINK-USD","name":"Chainlink","exchange":"CRYPTO"},
        {"symbol":"UNI-USD","name":"Uniswap","exchange":"CRYPTO"},
    ],
    "indices": [
        {"symbol":"^GSPC","name":"S&P 500","exchange":"INDEX"},
        {"symbol":"^IXIC","name":"NASDAQ Composite","exchange":"INDEX"},
        {"symbol":"^DJI","name":"Dow Jones","exchange":"INDEX"},
        {"symbol":"^RUT","name":"Russell 2000","exchange":"INDEX"},
        {"symbol":"^FTSE","name":"FTSE 100","exchange":"INDEX"},
        {"symbol":"^GDAXI","name":"DAX 40","exchange":"INDEX"},
        {"symbol":"^N225","name":"Nikkei 225","exchange":"INDEX"},
        {"symbol":"^HSI","name":"Hang Seng","exchange":"INDEX"},
    ],
    "commodities": [
        {"symbol":"GC=F","name":"Gold Futures","exchange":"COMEX"},
        {"symbol":"SI=F","name":"Silver Futures","exchange":"COMEX"},
        {"symbol":"CL=F","name":"Crude Oil WTI","exchange":"NYMEX"},
        {"symbol":"BZ=F","name":"Brent Crude","exchange":"ICE"},
        {"symbol":"NG=F","name":"Natural Gas","exchange":"NYMEX"},
        {"symbol":"HG=F","name":"Copper","exchange":"COMEX"},
        {"symbol":"ZW=F","name":"Wheat","exchange":"CBOT"},
        {"symbol":"ZC=F","name":"Corn","exchange":"CBOT"},
    ],
}

ALL_SYMBOLS = [s for cat in SYMBOLS.values() for s in cat]


@router.get("/symbols")
async def get_symbols(q: str = Query(default="", max_length=50)):
    """Search symbols by query string. Returns all if q is empty."""
    if not q:
        return {"symbols": ALL_SYMBOLS, "total": len(ALL_SYMBOLS)}
    q_lower = q.lower()
    results = [
        s for s in ALL_SYMBOLS
        if q_lower in s["symbol"].lower() or q_lower in s["name"].lower()
    ]
    return {"symbols": results[:30], "total": len(results)}


@router.get("/ohlcv/{ticker}")
async def get_ohlcv(ticker: str):
    """Return OHLCV candle data for the chart."""
    try:
        import yfinance as yf

        def _sync():
            t = yf.Ticker(ticker)
            hist = t.history(period="6mo", interval="1d", auto_adjust=True)
            if hist.empty:
                raise ValueError("empty")
            candles = []
            for ts, row in hist.iterrows():
                candles.append({
                    "time": int(ts.timestamp()),
                    "open":  round(float(row["Open"]), 4),
                    "high":  round(float(row["High"]), 4),
                    "low":   round(float(row["Low"]), 4),
                    "close": round(float(row["Close"]), 4),
                })
            return candles

        candles = await asyncio.to_thread(_sync)
        return {"ticker": ticker, "candles": candles}

    except Exception:
        # Deterministic mock fallback with realistic price ranges per asset type
        _MOCK_BASES = {
            # Crypto
            "BTC-USD": 68000, "ETH-USD": 3400, "SOL-USD": 160, "BNB-USD": 580,
            "XRP-USD": 0.52, "ADA-USD": 0.45, "DOGE-USD": 0.17, "AVAX-USD": 35,
            "MATIC-USD": 0.85, "DOT-USD": 7.5, "LINK-USD": 18, "UNI-USD": 9,
            # Forex
            "EURUSD=X": 1.082, "GBPUSD=X": 1.271, "USDJPY=X": 149.5,
            "AUDUSD=X": 0.651, "USDCAD=X": 1.363, "USDCHF=X": 0.901,
            "NZDUSD=X": 0.598, "EURGBP=X": 0.853, "EURJPY=X": 161.8,
            "GBPJPY=X": 190.2, "USDMXN=X": 17.2, "USDZAR=X": 18.8,
            # Commodities
            "GC=F": 2340, "SI=F": 27.5, "CL=F": 79.5, "BZ=F": 83.2,
            "NG=F": 2.1, "HG=F": 4.15, "ZW=F": 540, "ZC=F": 430,
            # Indices
            "^GSPC": 5180, "^IXIC": 16300, "^DJI": 38900, "^RUT": 2040,
            "^FTSE": 7680, "^GDAXI": 17800, "^N225": 38200, "^HSI": 17400,
            # ETFs
            "SPY": 523, "QQQ": 441, "IWM": 202, "GLD": 218, "TLT": 91,
            "XLK": 208, "XLE": 91, "VIX": 15,
            # US stocks (approximate current levels)
            "AAPL": 182, "MSFT": 415, "NVDA": 875, "GOOGL": 158, "AMZN": 185,
            "META": 520, "TSLA": 175, "SPY": 523, "QQQ": 441, "AMD": 165,
            "INTC": 43, "NFLX": 630, "DIS": 112, "JPM": 198, "GS": 452,
            "BAC": 37, "V": 278, "MA": 468, "JNJ": 158, "WMT": 59,
            "XOM": 118, "CVX": 154, "UNH": 510, "PG": 161, "HD": 380,
            "KO": 60, "PEP": 172, "ABBV": 182, "MRK": 128, "LLY": 770,
            "COST": 755, "MCD": 282, "SBUX": 80, "NKE": 93, "BA": 188,
            "CAT": 358, "GE": 162, "IBM": 190, "ORCL": 120, "CRM": 295,
            "ADBE": 480, "PYPL": 64, "UBER": 71, "PLTR": 24, "RIVN": 11,
        }
        base = _MOCK_BASES.get(ticker, _MOCK_BASES.get(ticker.upper(), 100.0))
        # For forex use tighter volatility, crypto use wider
        is_forex = "=X" in ticker
        is_crypto = "-USD" in ticker and ticker not in ("GLD", "SLV")
        daily_vol = 0.003 if is_forex else (0.028 if is_crypto else 0.014)

        rng = random.Random(sum(ord(c) for c in ticker))
        now = int(datetime.utcnow().timestamp())
        DAY = 86400
        candles = []
        price = base
        for i in range(130, 0, -1):
            o = price
            change = rng.gauss(0.0002, daily_vol)
            c = round(o * (1 + change), 4 if is_forex else 2)
            h = round(max(o, c) * (1 + abs(rng.gauss(0, daily_vol * 0.4))), 4 if is_forex else 2)
            l = round(min(o, c) * (1 - abs(rng.gauss(0, daily_vol * 0.4))), 4 if is_forex else 2)
            candles.append({"time": now - i * DAY, "open": round(o, 4 if is_forex else 2), "high": h, "low": l, "close": c})
            price = c
        return {"ticker": ticker, "candles": candles}
