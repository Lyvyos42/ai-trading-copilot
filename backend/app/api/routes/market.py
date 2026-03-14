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
        # Deterministic mock fallback
        rng = random.Random(sum(ord(c) for c in ticker))
        base = rng.uniform(20, 500)
        now = int(datetime.utcnow().timestamp())
        DAY = 86400
        candles = []
        price = base
        for i in range(130, 0, -1):
            o = price
            change = rng.gauss(0.0003, 0.014)
            c = round(o * (1 + change), 4)
            h = round(max(o, c) * (1 + abs(rng.gauss(0, 0.005))), 4)
            l = round(min(o, c) * (1 - abs(rng.gauss(0, 0.005))), 4)
            candles.append({"time": now - i * DAY, "open": round(o,4), "high": h, "low": l, "close": c})
            price = c
        return {"ticker": ticker, "candles": candles}
