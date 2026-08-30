"""
Signal resolver — path-based outcome resolution against historical OHLC bars.

Replaces the old spot-snapshot check, which only ever saw the price at the
instant a page happened to be loaded. That biased every result toward LOSS:
the invalidation level sits closer to entry than the research target, so a
single sample is far more likely to be beyond the stop than beyond the target,
and a target touched intraday was never recorded at all.

Here we walk every bar between the signal's creation and its expiry and resolve
on the first barrier the price path actually crossed.
"""
import asyncio
import json as _json
import urllib.parse as _urlpar
import urllib.request as _urlreq
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select

from app.data.market_data import resolve_ticker, _REST_ALIAS
from app.models.signal import Signal

log = structlog.get_logger()

_LONG_WORDS = {"LONG", "BULLISH", "BUY"}


def window_to_hours(window: str | None) -> int:
    """Convert an analytical_window string like '3-7 DAY' to expiry hours."""
    import re
    if not window:
        return 24
    w = window.upper()
    nums = [int(x) for x in re.findall(r"\d+", w)]
    max_num = max(nums) if nums else 1
    if "MIN" in w:
        return max(1, max_num // 60 + 1)
    if "HOUR" in w:
        return max(1, max_num * 2)
    if "DAY" in w:
        return max_num * 24
    return 24


def is_long(direction: str | None) -> bool:
    return (direction or "").upper() in _LONG_WORDS


def _pick_interval(start: datetime, now: datetime) -> str:
    """Choose the finest Yahoo interval whose retention still covers `start`.

    Yahoo retention: 1m ~7d, 5m ~60d, 30m/1h ~730d, 1d unlimited.
    """
    age_days = (now - start).total_seconds() / 86400
    if age_days <= 6:
        return "5m"
    if age_days <= 55:
        return "30m"
    if age_days <= 700:
        return "1h"
    return "1d"


def _fetch_bars_sync(symbol: str, start: datetime, end: datetime, interval: str) -> list[tuple[datetime, float, float, float]]:
    """Fetch (timestamp, high, low, close) bars from the Yahoo chart REST API."""
    safe = _urlpar.quote(symbol, safe="=^.")
    p1 = int(start.replace(tzinfo=timezone.utc).timestamp())
    p2 = int(end.replace(tzinfo=timezone.utc).timestamp())
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{safe}"
           f"?interval={interval}&period1={p1}&period2={p2}")
    req = _urlreq.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with _urlreq.urlopen(req, timeout=10) as r:
        payload = _json.loads(r.read())
    result = (payload.get("chart") or {}).get("result") or []
    if not result:
        return []
    res = result[0]
    stamps = res.get("timestamp") or []
    quote = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    highs, lows, closes = quote.get("high") or [], quote.get("low") or [], quote.get("close") or []

    bars: list[tuple[datetime, float, float, float]] = []
    for i, ts in enumerate(stamps):
        try:
            h, lo, c = highs[i], lows[i], closes[i]
        except IndexError:
            continue
        if h is None or lo is None or c is None:
            continue
        bars.append((datetime.utcfromtimestamp(ts), float(h), float(lo), float(c)))
    return bars


async def fetch_bars(ticker: str, start: datetime, end: datetime, interval: str) -> list[tuple[datetime, float, float, float]]:
    """Async wrapper around the Yahoo bar fetch, with a REST-alias retry."""
    symbol = resolve_ticker(ticker)
    for sym in (symbol, _REST_ALIAS.get(symbol)):
        if not sym:
            continue
        try:
            bars = await asyncio.to_thread(_fetch_bars_sync, sym, start, end, interval)
        except Exception as exc:
            log.warning("resolver_bars_failed", ticker=ticker, symbol=sym, error=str(exc))
            continue
        if bars:
            return bars
    return []


def resolve_against_bars(signal: Signal, bars: list, now: datetime) -> dict | None:
    """Walk the price path and return the resolution for `signal`, or None if still open.

    Returns a dict of column updates. A bar that straddles both barriers is
    scored as a LOSS — we cannot see intra-bar ordering, so we assume the stop
    came first rather than flatter the track record.
    """
    entry = signal.entry_price or 0.0
    tp = signal.take_profit_1 or 0.0
    sl = signal.stop_loss or 0.0
    expired = bool(signal.expiry_time and now > signal.expiry_time)

    # A signal with no usable levels can never be scored either way.
    if entry <= 0 or tp <= 0 or sl <= 0 or tp == sl:
        if expired:
            return {"status": "VOID", "outcome": "VOID", "resolved_at": signal.expiry_time or now}
        return None

    long_side = is_long(signal.direction)
    sign = 1 if long_side else -1
    mfe = signal.max_favorable_excursion or 0.0
    mae = signal.max_adverse_excursion or 0.0

    hit = None
    for ts, high, low, close in bars:
        best = ((high if long_side else low) - entry) / entry * 100 * sign
        worst = ((low if long_side else high) - entry) / entry * 100 * sign
        mfe = max(mfe, best)
        mae = min(mae, worst)

        if long_side:
            touched_sl, touched_tp = low <= sl, high >= tp
        else:
            touched_sl, touched_tp = high >= sl, low <= tp

        if touched_sl:
            hit = ("LOSS", sl, ts)
            break
        if touched_tp:
            hit = ("WIN", tp, ts)
            break

    updates = {
        "max_favorable_excursion": round(mfe, 4),
        "max_adverse_excursion": round(mae, 4),
    }

    if hit:
        outcome, exit_price, ts = hit
        updates.update({
            "status": outcome,
            "outcome": outcome,
            "exit_price": round(exit_price, 8),
            "resolved_at": ts,
            "pnl_pct": round((exit_price - entry) / entry * 100 * sign, 4),
        })
        return updates

    if expired:
        last_close = bars[-1][3] if bars else None
        updates.update({
            "status": "EXPIRED",
            "outcome": "EXPIRED",
            "resolved_at": signal.expiry_time,
            "exit_price": round(last_close, 8) if last_close else None,
            "pnl_pct": round((last_close - entry) / entry * 100 * sign, 4) if last_close else None,
        })
        return updates

    return updates if bars else None


async def resolve_signal(signal: Signal, now: datetime) -> dict | None:
    """Fetch the price path for one signal and resolve it."""
    start = signal.created_at
    if not start:
        return None
    end = min(signal.expiry_time or now, now)
    if end <= start:
        end = start + timedelta(hours=1)

    interval = _pick_interval(start, now)
    bars = await fetch_bars(signal.ticker, start, end, interval)
    # Daily bars are always available — fall back when the fine interval is empty.
    if not bars and interval != "1d":
        bars = await fetch_bars(signal.ticker, start, end, "1d")
    # Only count bars that opened at or after the signal existed.
    bars = [b for b in bars if b[0] >= start]
    return resolve_against_bars(signal, bars, now)


async def resolve_open_signals(
    session,
    user_id: str | None = None,
    limit: int = 200,
    signals: list[Signal] | None = None,
) -> dict:
    """Resolve ACTIVE signals against their price path.

    Pass `signals` to resolve a specific set (e.g. exactly the rows a request is
    about to return); otherwise the oldest open signals are swept, which is what
    the scheduled job wants so the backlog drains.
    """
    now = datetime.utcnow()
    if signals is None:
        query = select(Signal).where(Signal.status == "ACTIVE").order_by(Signal.created_at)
        if user_id:
            query = query.where(Signal.user_id == user_id)
        result = await session.execute(query.limit(limit))
        signals = result.scalars().all()
    else:
        signals = [s for s in signals if s.status == "ACTIVE"]
    if not signals:
        return {"checked": 0, "resolved": 0, "still_active": 0, "counts": {}}

    resolutions = await asyncio.gather(
        *(resolve_signal(s, now) for s in signals), return_exceptions=True
    )

    counts: dict[str, int] = {}
    resolved = 0
    for signal, updates in zip(signals, resolutions):
        if isinstance(updates, Exception) or not updates:
            continue
        for field, value in updates.items():
            setattr(signal, field, value)
        outcome = updates.get("outcome")
        if outcome:
            resolved += 1
            counts[outcome] = counts.get(outcome, 0) + 1

    await session.commit()
    log.info("signals_resolved", checked=len(signals), resolved=resolved, counts=counts)
    return {
        "checked": len(signals),
        "resolved": resolved,
        "still_active": len(signals) - resolved,
        "counts": counts,
    }
