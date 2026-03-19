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


# Maps TradingView-style display symbols to Yahoo Finance tickers.
# Used so users see familiar names (XAUUSD, EURUSD) while we fetch correct data.
_TICKER_ALIAS: dict[str, str] = {
    # Spot Metals → nearest futures (free proxy, price diff < 0.1%)
    "XAUUSD": "GC=F",   "XAGUSD": "SI=F",   "XPTUSD": "PL=F",   "XPDUSD": "PA=F",
    # Energy CFDs → futures
    "USOIL":  "CL=F",   "UKOIL":  "BZ=F",   "NATGAS": "NG=F",
    "RBOB":   "RB=F",   "HEATOIL":"HO=F",
    # Grains / Softs display names
    "CORN":   "ZC=F",   "WHEAT":  "ZW=F",   "SOYBEAN":"ZS=F",
    "COFFEE": "KC=F",   "SUGAR":  "SB=F",   "COTTON": "CT=F",   "COCOA":  "CC=F",
    # FX — strip =X for display, add it back for yfinance
    "EURUSD": "EURUSD=X","GBPUSD": "GBPUSD=X","USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X","USDCAD": "USDCAD=X","USDCHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X","EURGBP": "EURGBP=X","EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X","EURCHF": "EURCHF=X","EURAUD": "EURAUD=X",
    "EURCAD": "EURCAD=X","EURNZD": "EURNZD=X","GBPAUD": "GBPAUD=X",
    "GBPCAD": "GBPCAD=X","GBPCHF": "GBPCHF=X","GBPNZD": "GBPNZD=X",
    "AUDJPY": "AUDJPY=X","AUDCAD": "AUDCAD=X","AUDCHF": "AUDCHF=X",
    "AUDNZD": "AUDNZD=X","CADJPY": "CADJPY=X","CADCHF": "CADCHF=X",
    "CHFJPY": "CHFJPY=X","NZDJPY": "NZDJPY=X","NZDCAD": "NZDCAD=X",
    "NZDCHF": "NZDCHF=X","USDTRY": "USDTRY=X","USDZAR": "USDZAR=X",
    "USDMXN": "USDMXN=X","USDSEK": "USDSEK=X","USDNOK": "USDNOK=X",
    "USDDKK": "USDDKK=X","USDSGD": "USDSGD=X","USDHKD": "USDHKD=X",
    "USDCNH": "USDCNH=X","USDINR": "USDINR=X","USDBRL": "USDBRL=X",
    "USDPLN": "USDPLN=X","USDHUF": "USDHUF=X","USDCZK": "USDCZK=X",
    "USDTHB": "USDTHB=X","USDKRW": "USDKRW=X",
    # Index CFDs → Yahoo index tickers
    "US500":  "^GSPC",  "SPX":    "^GSPC",
    "US100":  "^NDX",   "NDX":    "^NDX",
    "US30":   "^DJI",   "DJIA":   "^DJI",
    "US2000": "^RUT",
    "UK100":  "^FTSE",
    "GER40":  "^GDAXI", "DAX":    "^GDAXI",
    "FRA40":  "^FCHI",  "CAC40":  "^FCHI",
    "JPN225": "^N225",  "NKY":    "^N225",
    "HK50":   "^HSI",
    "AUS200": "^AXJO",
    "ESP35":  "^IBEX",
    "ITA40":  "FTSEMIB.MI",
    "CHN50":  "000300.SS",
    "STOXX50":"^STOXX50E",
}


def resolve_ticker(display_symbol: str) -> str:
    """Convert a TradingView-style display symbol to a yfinance-compatible ticker."""
    upper = display_symbol.upper().strip()
    return _TICKER_ALIAS.get(upper, upper)


async def fetch_market_data(ticker: str, asset_class: str = "stocks") -> dict:
    """Main entry point. Resolves TV-style display symbols to yfinance tickers, then fetches."""
    yf_ticker = resolve_ticker(ticker)
    try:
        data = await _fetch_yfinance(yf_ticker, asset_class)
        data["ticker"] = ticker  # keep display symbol in response
        return data
    except Exception:
        return _mock_market_data(ticker, asset_class)


async def _fetch_yfinance(ticker: str, asset_class: str = "stocks") -> dict:
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
            "asset_class": asset_class,
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
    # ── US Large-Cap Stocks ────────────────────────────────────────────────────
    "AAPL": 225.0,  "MSFT": 415.0,  "NVDA": 115.0,  "GOOGL": 175.0, "AMZN": 200.0,
    "META": 600.0,  "TSLA": 195.0,  "JPM":  240.0,  "V":     290.0, "MA":   490.0,
    "BRK.B":460.0,  "XOM":  115.0,  "CVX":  155.0,  "WMT":    95.0, "HD":   380.0,
    "GS":   580.0,  "BAC":   44.0,  "MS":   130.0,  "NFLX":  980.0, "AMD":  125.0,
    "INTC":  22.0,  "PYPL":  75.0,  "COST": 920.0,  "SBUX":   95.0, "TGT":  135.0,
    "NKE":   93.0,  "DIS":  112.0,  "PG":   161.0,  "KO":     62.0, "PEP":  172.0,
    "JNJ":  158.0,  "UNH":  510.0,  "ABBV": 182.0,  "MRK":   128.0, "LLY":  840.0,
    "PFE":   27.0,  "ABT":  125.0,  "AMGN": 285.0,  "GILD":  105.0, "TMO":  495.0,
    "BA":   188.0,  "CAT":  358.0,  "GE":   162.0,  "HON":   215.0, "LMT":  490.0,
    "RTX":  125.0,  "IBM":  190.0,  "ORCL": 160.0,  "CRM":   295.0, "ADBE": 480.0,
    "NOW":  980.0,  "SNOW": 155.0,  "DDOG": 120.0,  "CRWD":  390.0, "PANW": 185.0,
    "NET":  125.0,  "PLTR":  92.0,  "COIN": 225.0,  "AVGO":  195.0, "QCOM": 155.0,
    "TXN":  195.0,  "MU":   105.0,  "ARM":  125.0,  "SMCI":   55.0, "MSTR": 340.0,
    "C":     68.0,  "WFC":   78.0,  "BLK":  985.0,  "SCHW":   75.0, "AXP":  280.0,
    "HOOD":  42.0,  "SQ":    75.0,  "SHOP": 115.0,  "UBER":   85.0, "RIVN":  11.0,
    "NIO":    4.5,  "BABA":  95.0,  "JD":   35.0,   "PDD":   155.0,
    "SLB":   45.0,  "EOG":  130.0,  "COP":  115.0,
    "T":     22.0,  "VZ":    40.0,  "CMCSA": 40.0,  "MCD":   295.0,
    # ── ETFs ──────────────────────────────────────────────────────────────────
    "SPY":  560.0,  "QQQ":  475.0,  "IWM":  215.0,  "DIA":   425.0, "VTI":  245.0,
    "VOO":  515.0,  "GLD":  265.0,  "IAU":   57.0,  "SLV":    27.0, "TLT":   93.0,
    "IEF":   96.0,  "SHY":   82.0,  "AGG":   95.0,  "BND":    73.0, "HYG":   77.0,
    "LQD":  108.0,  "EMB":   88.0,  "TIPS":  108.0, "VNQ":    85.0, "XLRE":  40.0,
    "XLK":  225.0,  "XLE":   88.0,  "XLF":   49.0,  "XLV":  148.0,  "XLI":  135.0,
    "XLY":  200.0,  "XLP":   77.0,  "XLU":   70.0,  "XLB":   90.0,
    "ARKK":  55.0,  "SOXX": 210.0,  "SMH":  225.0,  "IBB":  135.0,  "XBI":   95.0,
    "GDX":   43.0,  "GDXJ":  40.0,  "USO":   75.0,  "UNG":   17.0,
    "EEM":   42.0,  "VWO":   43.0,  "EFA":   78.0,  "VEA":   52.0,  "VGK":   66.0,
    "EWJ":   70.0,  "EWZ":   28.0,  "FXI":   28.0,  "EWY":   62.0,
    # ── UK Stocks (LSE) ───────────────────────────────────────────────────────
    "AZN.L":11500.0,"HSBA.L":720.0,"BP.L":  430.0,  "SHEL.L":2530.0,"RIO.L":4900.0,
    "GSK.L":1580.0, "ULVR.L":2400.0,"LLOY.L":55.0,  "BARC.L":235.0, "VOD.L":  70.0,
    "BT-A.L":155.0, "DGE.L":2600.0,"AAL.L": 225.0,  "BHP.L":2100.0,
    # ── European Stocks ───────────────────────────────────────────────────────
    "ASML.AS":680.0,"INGA.AS":17.0, "MC.PA":780.0,  "AIR.PA":165.0, "TTE.PA": 60.0,
    "OR.PA":215.0,  "BNP.PA": 68.0, "SAP.DE":225.0, "SIE.DE":190.0, "ALV.DE":310.0,
    "BMW.DE":80.0,  "VOW3.DE":95.0, "MBG.DE":65.0,  "BAYN.DE":25.0, "ADS.DE":230.0,
    "NESN.SW":95.0, "NOVN.SW":95.0, "ROG.SW":250.0,
    # ── Japanese Stocks (TSE) ─────────────────────────────────────────────────
    "7203.T":3200.0,"9984.T":9500.0,"6758.T":2800.0,"9432.T":155.0, "6861.T":65000.0,
    "7974.T":8500.0,"9983.T":48000.0,
    # ── Chinese ADRs ──────────────────────────────────────────────────────────
    "BIDU":  95.0,  "NTES":  105.0, "TCOM":  60.0,
    # ── Crypto (USD) ──────────────────────────────────────────────────────────
    "BTC-USD":83000.0,"ETH-USD":2000.0,"BNB-USD":590.0,"XRP-USD":2.5,
    "SOL-USD":130.0,  "ADA-USD":0.45,"DOGE-USD":0.18, "AVAX-USD":28.0,
    "DOT-USD":5.5,    "LINK-USD":15.0,"MATIC-USD":0.5,"UNI-USD":7.5,
    "ATOM-USD":6.5,   "LTC-USD":95.0,"BCH-USD":440.0,"NEAR-USD":3.8,
    "APT-USD":7.5,    "OP-USD":1.0,  "ARB-USD":0.42, "SUI-USD":2.8,
    "SHIB-USD":0.0000135,"PEPE-USD":0.0000085,"WIF-USD":1.5,
    # ── FX Majors & Crosses (yfinance =X format) ──────────────────────────────
    "EURUSD=X":1.085,"GBPUSD=X":1.295,"USDJPY=X":148.5,"AUDUSD=X":0.635,
    "USDCAD=X":1.355,"USDCHF=X":0.895,"NZDUSD=X":0.583,
    "EURGBP=X":0.855,"EURJPY=X":161.0,"GBPJPY=X":192.0,"EURCHF=X":0.955,
    "EURAUD=X":1.715,"EURCAD=X":1.565,"EURNZD=X":1.860,"GBPAUD=X":2.040,
    "GBPCAD=X":1.830,"GBPCHF=X":1.140,"GBPNZD=X":2.215,"AUDJPY=X":94.5,
    "AUDCAD=X":0.860,"AUDCHF=X":0.568,"AUDNZD=X":1.090,"CADJPY=X":109.5,
    "CADCHF=X":0.661,"CHFJPY=X":165.5,"NZDJPY=X":86.5, "NZDCAD=X":0.788,
    "NZDCHF=X":0.523,
    # FX Exotics
    "USDTRY=X":38.5, "USDZAR=X":18.5, "USDMXN=X":17.8,"USDSEK=X":10.45,
    "USDNOK=X":10.85,"USDDKK=X":6.88,"USDSGD=X":1.335,"USDHKD=X":7.782,
    "USDCNH=X":7.25, "USDINR=X":84.5,"USDBRL=X":5.85, "USDPLN=X":3.98,
    "USDHUF=X":360.0,"USDCZK=X":23.5,"USDTHB=X":33.5, "USDKRW=X":1360.0,
    # FX display aliases (TV-style, resolved to =X by _TICKER_ALIAS)
    "EURUSD":1.085, "GBPUSD":1.295, "USDJPY":148.5, "AUDUSD":0.635,
    "USDCAD":1.355, "USDCHF":0.895, "NZDUSD":0.583, "EURGBP":0.855,
    "EURJPY":161.0, "GBPJPY":192.0, "EURCHF":0.955,
    # ── Spot Metals (TV display names, resolved to futures) ───────────────────
    "XAUUSD":3100.0,"XAGUSD":34.5,  "XPTUSD":990.0, "XPDUSD":950.0,
    # ── Commodities Futures ───────────────────────────────────────────────────
    "GC=F":  3100.0,"SI=F":  34.5,  "HG=F":   4.55, "PL=F":  990.0, "PA=F":  950.0,
    "CL=F":   68.0, "BZ=F":  72.0,  "NG=F":    4.2, "RB=F":   2.15, "HO=F":   2.45,
    "ZC=F":  480.0, "ZW=F":  555.0, "ZS=F":   975.0,"KC=F":  380.0, "CT=F":   82.0,
    "CC=F": 9100.0, "SB=F":  18.5,  "OJ=F":  340.0,
    "LE=F":  185.0, "GF=F":  260.0, "LH=F":   85.0,
    # CFD display names
    "USOIL":  68.0, "UKOIL":  72.0, "NATGAS":  4.2,
    "CORN":  480.0, "WHEAT": 555.0, "SOYBEAN":975.0,
    "COFFEE":380.0, "SUGAR":  18.5, "COTTON":  82.0, "COCOA":9100.0,
    # ── Equity Index Futures & CFDs ───────────────────────────────────────────
    "ES=F": 5700.0, "NQ=F":20100.0, "YM=F":42800.0, "RTY=F":2175.0,
    "ZN=F":  108.5, "ZB=F":  117.0, "ZT=F":   101.5,"VX=F":   19.0,
    # Index display names
    "US500": 5700.0,"US100":20100.0,"US30": 42800.0,"US2000":2175.0,
    "UK100": 8250.0,"GER40":22500.0,"FRA40": 8050.0,
    "JPN225":38500.0,"HK50":19800.0,"AUS200":8100.0,
    "ESP35":12800.0,"ITA40":38000.0,"STOXX50":5300.0,
    # ── Global Indices (Yahoo Finance) ────────────────────────────────────────
    "^GSPC": 5700.0,"^NDX": 20100.0,"^DJI": 42800.0,"^RUT":  2175.0,
    "^FTSE": 8250.0,"^GDAXI":22500.0,"^FCHI":8050.0,"^N225":38500.0,
    "^HSI": 19800.0,"^AXJO": 8100.0,"^KS11":2700.0, "^BVSP":130000.0,
    "^MXX": 52000.0,"^BSESN":74000.0,"^NSEI":22500.0,"^STI": 3750.0,
    "^IBEX":13200.0,"^AEX":  925.0, "^SMI": 12800.0,"^STOXX50E":5300.0,
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
