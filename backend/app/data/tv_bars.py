"""Timestamped OHLCV bars from TradingView, for the quantitative strategies.

TRADINGVIEW ONLY. NO YAHOO, NO YFINANCE, NO FALLBACK.

A strategy that silently receives a different vendor's bars when TradingView is
down produces a signal on data nobody chose. So there is exactly one source here,
and when it cannot answer the loader raises and the strategy abstains with the
reason. The TradingView historical path is tvDatafeed (the scanner API returns
snapshots, not series). tvDatafeed is not in requirements.txt; until it is
installed on the host, every strategy that needs bars abstains and says why.

FOUR THINGS THAT ARE CONVERTED RATHER THAN TRUSTED

1. TIMESTAMPS. tvDatafeed builds its index with datetime.fromtimestamp(), which is
   NAIVE HOST-LOCAL time. pandas treats a naive Timestamp as UTC, which would shift
   every bar by the host's offset. The epoch is recovered with Python's naive
   datetime.timestamp(), which interprets naive values as local - the inverse of
   how they were made.

2. DAILY BAR DATES. A CME equity future's daily bar OPENS at 18:00 ET the evening
   before the session it belongs to, so its ET date is the previous calendar day.
   Month-end strategies key on session dates, so daily bars are re-stamped at 09:30
   ET of the session they close on (bar open + 12 h, dated in ET). This is correct
   for CME (18:00 ET open), US cash equities (09:30 ET) and FX_IDC (00:00 UTC).

3. VOLUME SEMANTICS by venue. CME/CBOT/COMEX/NYMEX futures and US-listed ETFs carry
   traded volume. OANDA reports tick counts. FX_IDC and cash indices (SP, DJ, TVC)
   carry no traded volume. A VWAP strategy abstains on anything but "traded".

4. FX AND GOLD INTRADAY TAPE. Spot has no traded volume anywhere, so for the
   intraday VWAP read the CME contract's bars are used (6E, 6B, 6A, GC) and shifted
   onto the TradingView spot close at the right-hand edge. Intraday only: the basis
   is roughly constant within a session and not across months.
"""
from __future__ import annotations

import asyncio
import threading
from datetime import datetime, time as dtime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
_TV_SYNC_LOCK = threading.Lock()

# Symbols beyond app.data.market_data._TV_EXCHANGE that the strategies cover.
_EXTRA = {
    "SPY": ("SPY", "AMEX"), "QQQ": ("QQQ", "NASDAQ"),
    "DIA": ("DIA", "AMEX"), "IWM": ("IWM", "AMEX"),
    "MES": ("MES1!", "CME"), "MNQ": ("MNQ1!", "CME"),
    "MYM": ("MYM1!", "CBOT"), "M2K": ("M2K1!", "CME"),
    "GC": ("GC1!", "COMEX"), "MGC": ("MGC1!", "COMEX"),
    "6E": ("6E1!", "CME"), "6B": ("6B1!", "CME"), "6A": ("6A1!", "CME"),
}

# Intraday traded-volume tape for spot instruments that have none.
FUTURES_TAPE = {
    "XAUUSD": ("GC1!", "COMEX"),
    "EURUSD": ("6E1!", "CME"),
    "GBPUSD": ("6B1!", "CME"),
    "AUDUSD": ("6A1!", "CME"),
}

_TRADED_VENUES = {"CME", "CBOT", "COMEX", "NYMEX", "CME_MINI", "AMEX", "NASDAQ", "NYSE", "BINANCE"}
_TICK_VENUES = {"OANDA"}

_INTERVAL_ATTR = {
    "1m": "in_1_minute", "5m": "in_5_minute", "15m": "in_15_minute",
    "30m": "in_30_minute", "1h": "in_1_hour", "4h": "in_4_hour", "1d": "in_daily",
}
DEFAULT_NBARS = {"5m": 800, "15m": 600, "30m": 400, "1h": 600, "4h": 600, "1d": 450}
INTRADAY = {"1m", "5m", "15m", "30m", "1h"}


class TVBarsUnavailable(RuntimeError):
    """TradingView could not serve the bars. There is deliberately no fallback."""


def norm(symbol: str) -> str:
    return (symbol or "").upper().replace("=F", "").replace("=X", "").replace("/", "").strip()


def tv_symbol(symbol: str) -> Optional[tuple[str, str]]:
    s = norm(symbol)
    if s in _EXTRA:
        return _EXTRA[s]
    try:
        from app.data.market_data import _TV_EXCHANGE
    except Exception:
        return None
    return _TV_EXCHANGE.get(s)


def volume_kind(exchange: str) -> str:
    ex = (exchange or "").upper()
    if ex in _TRADED_VENUES:
        return "traded"
    if ex in _TICK_VENUES:
        return "tick_count"
    return "none"


def epoch_from_tv_index(ts: Any) -> int:
    """Epoch seconds from a tvDatafeed index value (naive host-local datetime)."""
    if hasattr(ts, "to_pydatetime"):
        ts = ts.to_pydatetime()
    if isinstance(ts, datetime):
        return int(ts.timestamp())          # naive -> interpreted as host local
    return int(float(ts))


def restamp_daily(epoch: int) -> int:
    """Daily bar -> 09:30 ET of the session it closes on."""
    d = (datetime.fromtimestamp(epoch, tz=timezone.utc) + timedelta(hours=12)).astimezone(NY).date()
    return int(datetime.combine(d, dtime(9, 30), tzinfo=NY).timestamp())


def _client():
    from app.data.market_data import _get_tv_client
    return _get_tv_client()


def _hist_sync(tv_sym: str, exchange: str, interval: str, n_bars: int) -> list[dict]:
    try:
        from tvDatafeed import Interval
    except ImportError as exc:
        raise TVBarsUnavailable(
            "tvDatafeed is not installed on this host - TradingView cannot serve bar "
            "history, and no other vendor is substituted") from exc
    with _TV_SYNC_LOCK:
        tv = _client()
        if tv is None:
            raise TVBarsUnavailable("TradingView client could not be constructed")
        attr = _INTERVAL_ATTR.get(interval)
        if attr is None:
            raise TVBarsUnavailable(f"interval {interval!r} has no TradingView equivalent")
        try:
            df = tv.get_hist(symbol=tv_sym, exchange=exchange,
                             interval=getattr(Interval, attr), n_bars=n_bars)
        except Exception:
            df = None
        if df is None or len(df) == 0:
            # Reconnect client once if remote websocket dropped
            try:
                from app.data import market_data
                market_data._tv_client = None
                tv = _client()
                if tv is not None:
                    df = tv.get_hist(symbol=tv_sym, exchange=exchange,
                                     interval=getattr(Interval, attr), n_bars=n_bars)
            except Exception:
                pass
        if df is None or len(df) == 0:
            raise TVBarsUnavailable(f"TradingView returned no bars for {exchange}:{tv_sym} {interval}")
        df.columns = [str(c).lower() for c in df.columns]
    out = []
    for ts, row in df.iterrows():
        t = epoch_from_tv_index(ts)
        if interval == "1d":
            t = restamp_daily(t)
        vol = row.get("volume")
        out.append({"time": t, "open": float(row["open"]), "high": float(row["high"]),
                    "low": float(row["low"]), "close": float(row["close"]),
                    "volume": float(vol) if vol == vol and vol is not None else 0.0})
    return out


async def fetch_bars(symbol: str, interval: str, n_bars: Optional[int] = None,
                     want_traded_volume: bool = False) -> dict:
    """{"candles", "volume_kind", "source", "note"} from TradingView, or raise.

    `want_traded_volume` routes FX/gold intraday requests to the CME tape shifted
    onto spot; it is set by the caller for strategies that need traded volume.
    """
    n = n_bars or DEFAULT_NBARS.get(interval, 500)
    s = norm(symbol)

    if want_traded_volume and interval in INTRADAY and s in FUTURES_TAPE:
        fut_sym, fut_ex = FUTURES_TAPE[s]
        spot = tv_symbol(s)
        if spot is None:
            raise TVBarsUnavailable(f"no TradingView spot mapping for {s}")
        fut, ref = await asyncio.gather(
            asyncio.to_thread(_hist_sync, fut_sym, fut_ex, interval, n),
            asyncio.to_thread(_hist_sync, spot[0], spot[1], interval, 5))
        offset = ref[-1]["close"] - fut[-1]["close"]
        if abs(offset) > ref[-1]["close"] * 0.02:
            raise TVBarsUnavailable(
                f"{fut_ex}:{fut_sym} sits {offset:+.5f} from {spot[1]}:{spot[0]}, beyond a "
                f"plausible basis - not shifting")
        for b in fut:
            for k in ("open", "high", "low", "close"):
                b[k] = b[k] + offset
        return {"candles": fut, "volume_kind": "traded",
                "source": f"tradingview:{fut_ex}:{fut_sym} shifted onto {spot[1]}:{spot[0]}",
                "note": f"CME tape shifted by {offset:+.6f} onto TradingView spot"}

    mapped = tv_symbol(s)
    if mapped is None:
        raise TVBarsUnavailable(f"no TradingView symbol mapping for {symbol}")
    candles = await asyncio.to_thread(_hist_sync, mapped[0], mapped[1], interval, n)
    return {"candles": candles, "volume_kind": volume_kind(mapped[1]),
            "source": f"tradingview:{mapped[1]}:{mapped[0]}", "note": ""}
