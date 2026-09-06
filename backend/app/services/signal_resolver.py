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
import app.models.user  # noqa: F401 - ensures users table is registered for foreign key resolution

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


def _pick_interval(start: datetime, now: datetime, window_hours: int = 24) -> str:
    """Choose the finest Yahoo interval whose retention still covers `start`.

    Yahoo retention: 1m ~7d, 5m ~60d, 30m/1h ~730d, 1d unlimited.

    Short-horizon signals need the finest bar available, because the bar has
    to be smaller than the distance being measured. A scalper signal places
    its invalidation at 0.5x the 15-minute ATR; measured over five days of
    real bars, a single 5-MINUTE bar's range reaches that distance on 80.2%
    of USDJPY bars and spans BOTH barriers at once on 23.4% of them. Resolved
    on 5m bars, such a signal is decided inside the first or second bar by an
    ordering the bar cannot show - so it was not being measured, it was being
    guessed, and always the same way.
    """
    age_days = (now - start).total_seconds() / 86400
    if window_hours <= 8 and age_days <= 6:
        return "1m"
    if age_days <= 6:
        return "5m"
    if age_days <= 55:
        return "30m"
    if age_days <= 700:
        return "1h"
    return "1d"


# The coarsest bar allowed to resolve a signal of a given horizon.
#
# A bar cannot measure a distance smaller than its own range, and it cannot
# say WHEN inside itself the price got there. Resolving a 30-minute signal on
# a daily bar is not an approximation, it is a different question: the bar
# covers hours the signal did not exist for.
_MAX_INTERVAL_FOR_WINDOW = [
    # (window_hours_at_most, coarsest interval, its length in seconds)
    (2,    "5m",  300),
    (8,    "30m", 1800),
    (48,   "1h",  3600),
    (10**6, "1d", 86400),
]

_INTERVAL_SECONDS_MAP = {"1m": 60, "5m": 300, "30m": 1800, "1h": 3600, "1d": 86400}


def _allowed_intervals(window_hours: int, start: datetime, now: datetime) -> list[str]:
    """Intervals to try, finest first, none coarser than the horizon allows.

    The old fallback was `if not bars: retry with "1d"`, unconditionally. When
    Yahoo has no intraday bars yet - which is the normal state for the first
    minutes after the FX week opens on Sunday - a 5-30 MINUTE signal was being
    resolved against a bar spanning the whole session. Measured at the Sunday
    open on 2026-09-06: USDJPY's daily bar spanned 38 pips and EURJPY's 86,
    against an 11-pip invalidation. Both resolved LOSS on the first look.
    AUDUSD, whose daily bar happened to span only 9 pips, stayed pending -
    which is why the same two symbols failed twice and the third never did.

    Falling back to a coarser bar trades a missing answer for a wrong one.
    Returning nothing leaves the signal ACTIVE, which is what it is.
    """
    coarsest = "1d"
    for max_hours, interval, _secs in _MAX_INTERVAL_FOR_WINDOW:
        if window_hours <= max_hours:
            coarsest = interval
            break
    limit = _INTERVAL_SECONDS_MAP[coarsest]

    preferred = _pick_interval(start, now, window_hours)
    order = ["1m", "5m", "30m", "1h", "1d"]
    if preferred in order:
        order = [preferred] + [i for i in order if i != preferred]

    out, seen = [], set()
    for iv in order:
        if _INTERVAL_SECONDS_MAP[iv] <= limit and iv not in seen:
            # Yahoo retention: 1m ~7d, 5m ~60d. Asking beyond it returns
            # nothing and wastes a request.
            age_days = (now - start).total_seconds() / 86400
            if iv == "1m" and age_days > 6:
                continue
            if iv == "5m" and age_days > 55:
                continue
            out.append(iv)
            seen.add(iv)
    return out or ["1d"]


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

    Returns a dict of column updates.

    A bar that straddles BOTH barriers is scored AMBIGUOUS, not LOSS.

    Scoring it LOSS was the conservative choice and it is the right one for a
    backtest, where a pessimistic assumption keeps you honest about an edge.
    It is the wrong one here, because this number is shown to the user as a
    track record. When the invalidation sits inside a single bar's normal
    range - which is the case for every scalper signal, measured at 80.2% of
    USDJPY 5m bars - EVERY signal is an ambiguous bar, so the rule stops being
    conservative and starts being deterministic: 0% win rate, produced by the
    tie-break rather than by the market. Three signals scanned, two marked
    LOSS within a second, is what that looks like from the outside.

    An outcome that cannot be observed is reported as unobserved. The
    performance page already excludes anything that did not cleanly resolve
    from the win rate.
    """
    entry = signal.entry_price or 0.0
    tp = signal.take_profit_1 or 0.0
    sl = signal.stop_loss or 0.0
    expired = bool(signal.expiry_time and now > signal.expiry_time)

    # A signal generated while its market was shut is not a weak signal, it is
    # not a signal: the entry is a stale print from the last session, the ATR is
    # yesterday's, and the invalidation level cannot be reached because nothing
    # is trading. Generation is now refused up front, but rows created before
    # that guard existed are still sitting in the table pricing off dead quotes.
    # They are voided rather than scored.
    from app.services.market_hours import market_status
    if signal.created_at and not market_status(
            signal.ticker, signal.asset_class, signal.created_at)["open"]:
        return {
            "status": "VOID", "outcome": "VOID",
            "resolved_at": signal.resolved_at or now,
        }

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

        if touched_sl and touched_tp:
            # Both barriers inside one bar. Which came first decided the
            # outcome, and the bar does not record it.
            hit = ("AMBIGUOUS", close, ts)
            break
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
        if outcome == "AMBIGUOUS":
            # No P&L is claimed for an outcome that was not observed.
            updates["pnl_pct"] = None
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

    window_hours = window_to_hours(signal.analytical_window)

    bars: list = []
    used_interval = None
    for interval in _allowed_intervals(window_hours, start, now):
        candidate = await fetch_bars(signal.ticker, start, end, interval)
        # Only count bars that opened at or after the signal existed.
        #
        # This filter is necessary but NOT sufficient on its own: Yahoo stamps
        # the bar still forming at the CURRENT time rather than at the period
        # it covers, so an in-progress daily bar arrives stamped "now" while
        # its high and low describe the whole session. The interval cap above
        # is what actually contains that - one minute of slop on a 1m bar is
        # nothing, a whole day of it is the bug.
        candidate = [b for b in candidate if b[0] >= start]
        if candidate:
            bars, used_interval = candidate, interval
            break

    if not bars:
        # Nothing usable at an honest granularity. The signal stays ACTIVE
        # rather than being scored against a bar that cannot answer.
        log.debug("resolver_no_usable_bars", ticker=signal.ticker,
                  window_hours=window_hours)
        return None

    result = resolve_against_bars(signal, bars, now)
    # Recorded in the log rather than on the row: every key in the returned
    # dict is setattr'd onto the Signal, and a name that is not a column would
    # be silently attached as a plain attribute.
    if result and result.get("outcome"):
        log.info("signal_resolved", ticker=signal.ticker,
                 outcome=result["outcome"], interval=used_interval,
                 bars=len(bars))
    return result


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
