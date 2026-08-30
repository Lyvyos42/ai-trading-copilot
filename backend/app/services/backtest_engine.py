"""
Backtest engine — real strategy simulation over real historical bars.

This replaces a `_simulate_backtest` that generated its numbers with
`random.Random(seed)`: annual return drawn from uniform(0.04, 0.28), Sharpe from
uniform(0.8, 2.4), win rate from uniform(0.45, 0.68). Those figures were shown on
the product's backtest page and had never touched a price series.

Everything here comes from Yahoo daily bars. Entries are computed from data up to
and including the signal bar and resolved on bars strictly after it, so there is
no lookahead. A bar that straddles both barriers is scored a LOSS, matching
app/services/signal_resolver.py.
"""
import json as _json
import math
import os
import statistics
import urllib.parse as _urlpar
import urllib.request as _urlreq
from datetime import datetime, timedelta, timezone

import structlog

log = structlog.get_logger()

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bars_cache")
CACHE_TTL_SECONDS = 86400

RISK_PER_TRADE = 0.01  # 1% of equity risked per trade, for the equity curve
TRADING_DAYS = 252

_SYMBOL_MAP = {
    "XAUUSD": "GC=F", "XAGUSD": "SI=F",
    "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X", "USDCAD": "USDCAD=X", "USDCHF": "USDCHF=X",
    "NZDUSD": "NZDUSD=X", "EURGBP": "EURGBP=X", "EURJPY": "EURJPY=X",
    "GBPJPY": "GBPJPY=X", "BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD",
    "USOIL": "CL=F", "UKOIL": "BZ=F", "NATGAS": "NG=F",
    "SPX500": "^GSPC", "NAS100": "^NDX", "GER40": "^GDAXI",
    "UK100": "^FTSE", "JPN225": "^N225",
}

PERIOD_YEARS = {"1Y": 1, "2Y": 2, "3Y": 3, "5Y": 5}


# ── Data ──────────────────────────────────────────────────────────────────────

def fetch_ohlcv(ticker: str, interval: str = "1d", range_: str = "2y") -> list[dict]:
    """OHLCV bars at any Yahoo-supported interval, via the chart REST API.

    Used for charting. The yfinance library fails on some hosts with SSL
    verification errors; this endpoint is the same one the resolver uses and has
    proven reliable across equities, FX and metals.
    """
    symbol = _SYMBOL_MAP.get(ticker.upper(), ticker)
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/"
           f"{_urlpar.quote(symbol, safe='=^.-')}?interval={interval}&range={range_}")
    req = _urlreq.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with _urlreq.urlopen(req, timeout=20) as r:
            payload = _json.loads(r.read())
    except Exception as exc:
        log.warning("ohlcv_fetch_failed", ticker=ticker, interval=interval, error=str(exc))
        return []

    res = (payload.get("chart") or {}).get("result") or []
    if not res:
        return []
    node = res[0]
    stamps = node.get("timestamp") or []
    q = ((node.get("indicators") or {}).get("quote") or [{}])[0]
    opens, highs = q.get("open") or [], q.get("high") or []
    lows, closes, vols = q.get("low") or [], q.get("close") or [], q.get("volume") or []

    rows = []
    for i, ts in enumerate(stamps):
        try:
            h, lo, c = highs[i], lows[i], closes[i]
        except IndexError:
            continue
        if h is None or lo is None or c is None:
            continue
        rows.append({
            "time": int(ts),
            "open": round(float(opens[i] if i < len(opens) and opens[i] else c), 6),
            "high": round(float(h), 6), "low": round(float(lo), 6),
            "close": round(float(c), 6),
            "volume": int(vols[i]) if i < len(vols) and vols[i] else 0,
        })
    return rows


def fetch_daily(ticker: str, years: int) -> list[dict]:
    """Daily OHLCV bars from the Yahoo chart API, cached on disk for a day."""
    symbol = _SYMBOL_MAP.get(ticker.upper(), ticker)
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache = os.path.join(CACHE_DIR, f"{symbol.replace('/', '_')}_{years}y.json")
    if os.path.exists(cache) and (datetime.now().timestamp() - os.path.getmtime(cache)) < CACHE_TTL_SECONDS:
        try:
            with open(cache) as fh:
                return _json.load(fh)
        except Exception:
            pass

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365 * years + 90)  # extra history warms up indicators
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{_urlpar.quote(symbol, safe='=^.-')}"
           f"?interval=1d&period1={int(start.timestamp())}&period2={int(end.timestamp())}")
    req = _urlreq.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with _urlreq.urlopen(req, timeout=20) as r:
        payload = _json.loads(r.read())

    res = (payload.get("chart") or {}).get("result") or []
    if not res:
        return []
    node = res[0]
    stamps = node.get("timestamp") or []
    q = ((node.get("indicators") or {}).get("quote") or [{}])[0]
    opens, highs = q.get("open") or [], q.get("high") or []
    lows, closes, vols = q.get("low") or [], q.get("close") or [], q.get("volume") or []

    bars = []
    for i, ts in enumerate(stamps):
        try:
            h, lo, c = highs[i], lows[i], closes[i]
        except IndexError:
            continue
        if h is None or lo is None or c is None:
            continue
        bars.append({
            "ts": ts, "open": (opens[i] if i < len(opens) and opens[i] else c),
            "high": h, "low": lo, "close": c,
            "volume": (vols[i] if i < len(vols) and vols[i] else 0),
        })

    try:
        with open(cache, "w") as fh:
            _json.dump(bars, fh)
    except Exception:
        pass
    return bars


# ── Indicators ────────────────────────────────────────────────────────────────

def atr(highs, lows, closes, period: int = 14) -> float:
    if len(closes) < period + 1:
        return 0.0
    trs = [
        max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        for i in range(len(closes) - period, len(closes))
    ]
    return sum(trs) / len(trs) if trs else 0.0


def ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    k = 2.0 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1.0 - k))
    return out


def zscore(closes: list[float], period: int = 20) -> float:
    window = closes[-period:]
    if len(window) < period:
        return 0.0
    sd = statistics.pstdev(window)
    return (closes[-1] - statistics.mean(window)) / sd if sd else 0.0


# ── Entry rules ───────────────────────────────────────────────────────────────
# Each returns "LONG", "SHORT" or None from data up to and including index i.

def _entry_confluence(closes, highs, lows, vols, i) -> str | None:
    """The screener the product actually runs, via the live scoring function."""
    from app.services.auto_scanner import _score_setup, CONFLUENCE_THRESHOLD, AUTO_SCAN_LONG_ONLY
    avg_vol = statistics.mean(vols[i - 20:i]) if i >= 20 and any(vols[i - 20:i]) else 0
    score, direction, _ = _score_setup({
        "closes": closes[: i + 1], "highs": highs[: i + 1], "lows": lows[: i + 1],
        "volume": vols[i], "volume_ratio": (vols[i] / avg_vol) if avg_vol else 1.0,
    })
    if score < CONFLUENCE_THRESHOLD or direction not in ("LONG", "SHORT"):
        return None
    if AUTO_SCAN_LONG_ONLY and direction != "LONG":
        return None
    return direction


def _entry_ema_crossover(closes, highs, lows, vols, i) -> str | None:
    if i < 30:
        return None
    fast, slow = ema(closes[: i + 1], 9), ema(closes[: i + 1], 21)
    if fast[-2] <= slow[-2] and fast[-1] > slow[-1]:
        return "LONG"
    if fast[-2] >= slow[-2] and fast[-1] < slow[-1]:
        return "SHORT"
    return None


def _entry_mean_reversion(closes, highs, lows, vols, i) -> str | None:
    if i < 25:
        return None
    z = zscore(closes[: i + 1])
    if z <= -2.0:
        return "LONG"
    if z >= 2.0:
        return "SHORT"
    return None


def _entry_price_momentum(closes, highs, lows, vols, i) -> str | None:
    if i < 130:
        return None
    ret = (closes[i] - closes[i - 126]) / closes[i - 126]
    if i % 21:  # rebalance monthly rather than every bar
        return None
    if ret > 0.10:
        return "LONG"
    if ret < -0.10:
        return "SHORT"
    return None


STRATEGIES: dict[str, dict] = {
    "confluence_screener": {
        "ref": "3.20", "entry": _entry_confluence,
        "description": "RSI + EMA + MACD + volume confluence — the live auto-scanner rule",
        "tp_atr": 3.5, "sl_atr": 1.0, "hold": 10,
    },
    "ema_crossover": {
        "ref": "3.11-3.13", "entry": _entry_ema_crossover,
        "description": "EMA(9)/EMA(21) crossover",
        "tp_atr": 3.0, "sl_atr": 1.5, "hold": 15,
    },
    "mean_reversion": {
        "ref": "3.9", "entry": _entry_mean_reversion,
        "description": "20-day Z-score reversion beyond +/-2 sigma",
        "tp_atr": 2.0, "sl_atr": 1.5, "hold": 10,
    },
    "price_momentum": {
        "ref": "3.1", "entry": _entry_price_momentum,
        "description": "6-month price momentum, monthly rebalance",
        "tp_atr": 4.0, "sl_atr": 2.0, "hold": 20,
    },
}


# ── Simulation ────────────────────────────────────────────────────────────────

def run_strategy_backtest(strategy: str, ticker: str, period: str = "2Y") -> dict:
    """Simulate one strategy on one symbol and report real performance metrics."""
    spec = STRATEGIES[strategy]
    years = PERIOD_YEARS.get(period.upper(), 2)
    bars = fetch_daily(ticker, years)
    if len(bars) < 150:
        raise ValueError(f"insufficient price history for {ticker}")

    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    vols = [b["volume"] for b in bars]

    tp_atr, sl_atr, hold = spec["tp_atr"], spec["sl_atr"], spec["hold"]
    trades: list[dict] = []
    free_at = 0

    for i in range(60, len(bars) - 1):
        if i < free_at:
            continue
        direction = spec["entry"](closes, highs, lows, vols, i)
        if not direction:
            continue
        a = atr(highs[: i + 1], lows[: i + 1], closes[: i + 1])
        if a <= 0:
            continue

        entry = closes[i]
        long_side = direction == "LONG"
        tp = entry + a * tp_atr if long_side else entry - a * tp_atr
        sl = entry - a * sl_atr if long_side else entry + a * sl_atr
        risk = abs(entry - sl)
        if risk <= 0:
            continue

        outcome, exit_px, held = "EXPIRED", closes[min(i + hold, len(bars) - 1)], hold
        for j in range(i + 1, min(i + 1 + hold, len(bars))):
            hit_sl = lows[j] <= sl if long_side else highs[j] >= sl
            hit_tp = highs[j] >= tp if long_side else lows[j] <= tp
            if hit_sl:
                outcome, exit_px, held = "LOSS", sl, j - i
                break
            if hit_tp:
                outcome, exit_px, held = "WIN", tp, j - i
                break

        r = ((exit_px - entry) if long_side else (entry - exit_px)) / risk
        trades.append({
            "trade_num": len(trades) + 1, "direction": direction,
            "entry": round(entry, 4), "exit": round(exit_px, 4),
            "return_pct": round(r * RISK_PER_TRADE * 100, 2),
            "r_multiple": round(r, 3), "hold_days": held,
            "outcome": "WIN" if r > 0 else "LOSS",
        })
        free_at = i + held + 1

    return _metrics(strategy, ticker, period, years, trades, bars)


def _metrics(strategy: str, ticker: str, period: str, years: int,
             trades: list[dict], bars: list[dict]) -> dict:
    spec = STRATEGIES[strategy]
    base = {
        "strategy": strategy,
        "strategy_ref": spec["ref"],
        "description": spec["description"],
        "ticker": ticker.upper(),
        "period": period,
        "bars_tested": len(bars),
        "data_source": "Yahoo Finance daily bars",
        "note": (f"Real simulation: {len(trades)} trades over {len(bars)} daily bars. "
                 f"Entries use data up to the signal bar only; exits resolve on later bars. "
                 f"Equity assumes {RISK_PER_TRADE:.0%} of capital risked per trade."),
    }
    if not trades:
        base.update({
            "total_return_pct": 0.0, "annual_return_pct": 0.0, "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0, "win_rate_pct": 0.0, "total_trades": 0,
            "avg_hold_days": 0, "calmar_ratio": 0.0, "profit_factor": 0.0,
            "expectancy_r": 0.0, "equity_curve": [100_000.0], "sample_trades": [],
        })
        return base

    equity = [100_000.0]
    for t in trades:
        equity.append(round(equity[-1] * (1 + t["r_multiple"] * RISK_PER_TRADE), 2))

    peak, max_dd = equity[0], 0.0
    for v in equity:
        peak = max(peak, v)
        max_dd = max(max_dd, (peak - v) / peak)

    total_return = (equity[-1] - equity[0]) / equity[0]
    annual_return = (1 + total_return) ** (1 / years) - 1 if total_return > -1 else -1.0

    rets = [t["r_multiple"] * RISK_PER_TRADE for t in trades]
    sd = statistics.pstdev(rets) if len(rets) > 1 else 0.0
    trades_per_year = len(trades) / years
    sharpe = (statistics.mean(rets) / sd * math.sqrt(trades_per_year)) if sd else 0.0

    wins = [t["r_multiple"] for t in trades if t["r_multiple"] > 0]
    losses = [t["r_multiple"] for t in trades if t["r_multiple"] <= 0]
    gross_loss = abs(sum(losses))

    base.update({
        "total_return_pct": round(total_return * 100, 2),
        "annual_return_pct": round(annual_return * 100, 2),
        "sharpe_ratio": round(sharpe, 3),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1),
        "total_trades": len(trades),
        "avg_hold_days": round(statistics.mean([t["hold_days"] for t in trades]), 1),
        "calmar_ratio": round(annual_return / max_dd, 2) if max_dd > 0 else 0.0,
        "profit_factor": round(sum(wins) / gross_loss, 2) if gross_loss else 0.0,
        "expectancy_r": round(statistics.mean([t["r_multiple"] for t in trades]), 3),
        "equity_curve": equity,
        "sample_trades": trades[-20:],
    })
    return base
