"""Session windows for intraday strategies, DST-aware.

WHY NOT "EST"

Every specification for these strategies writes times as EST - 09:30 EST,
15:50 EST, 16:00 EST. EST is a fixed offset that applies for roughly four
months of the year; the exchange runs on Eastern TIME, which is EDT from
March to November. Hardcoding -05:00 puts every window an hour out for two
thirds of the calendar, which for a strategy defined by a thirty-minute
window means it trades the wrong thirty minutes most of the year and still
looks like it is working.

ZoneInfo("America/New_York") handles it. This is the same conclusion
ief/core/amt.py reached in Institutional Edge Futures, for the same reason.
"""
from __future__ import annotations

from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Optional, Sequence
from zoneinfo import ZoneInfo

EXCHANGE_TZ = ZoneInfo("America/New_York")

RTH_OPEN = dtime(9, 30)
OPENING_RANGE_END = dtime(10, 0)
CLOSING_WINDOW_START = dtime(15, 30)
RTH_CLOSE = dtime(16, 0)
# The cash session closes at 16:00. A time-based flatten at 15:50 exists so
# the exit is not competing with the closing auction for liquidity.
FLATTEN_BY = dtime(15, 50)

# Half sessions close at 13:00 ET. A strategy whose exit is 15:50 has no
# 15:50 to exit at on these days, and one whose signal window is 15:30-16:00
# has no window at all. Both must skip rather than improvise.
HALF_DAY_CLOSE = dtime(13, 0)


def to_et(ts_epoch) -> datetime:
    """Epoch seconds, or anything datetime-like, to exchange-local time.

    BarSeries.time is documented as epoch seconds, but a caller building one
    from a Parquet frame hands over pandas.Timestamp objects without noticing -
    the column looks numeric and the constructor takes any sequence. That
    raised TypeError deep inside datetime.fromtimestamp, several frames from
    the mistake. Coercing here is cheaper than the traceback, and a Timestamp
    already carries its own instant, so there is nothing to guess.

    Naive datetimes are assumed UTC. That assumption is stated rather than
    silently applied because it is wrong for a naive broker timestamp, and the
    right fix for those is ief-style localisation at the loader - see
    app/research/mt5_data.py - not a guess here.
    """
    if isinstance(ts_epoch, datetime):
        dt = ts_epoch
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(EXCHANGE_TZ)
    if hasattr(ts_epoch, "to_pydatetime"):        # pandas.Timestamp
        return to_et(ts_epoch.to_pydatetime())
    if hasattr(ts_epoch, "timestamp") and callable(ts_epoch.timestamp):
        return datetime.fromtimestamp(ts_epoch.timestamp(), tz=timezone.utc).astimezone(EXCHANGE_TZ)
    return datetime.fromtimestamp(float(ts_epoch), tz=timezone.utc).astimezone(EXCHANGE_TZ)


def et_epoch(day: date, t: dtime) -> int:
    """Epoch seconds for a wall-clock Eastern time on a given date."""
    return int(datetime.combine(day, t, tzinfo=EXCHANGE_TZ).timestamp())


def session_date(ts_epoch: int) -> date:
    return to_et(ts_epoch).date()


def is_half_day(bar_times: Sequence[int], day: date) -> bool:
    """True when the last bar of `day` starts before 13:00 ET.

    Detected from the bars rather than from a holiday table, because a table
    goes stale and the bars do not. It means the same thing either way: there
    was no afternoon session to trade.
    """
    todays = [t for t in bar_times if session_date(t) == day]
    if not todays:
        return True
    return to_et(max(todays)).time() < CLOSING_WINDOW_START


def window_indices(bar_times: Sequence[int], day: date,
                   start: dtime, end: dtime) -> list[int]:
    """Indices of bars whose START falls in [start, end) on `day`, Eastern.

    A bar is attributed to the window its open belongs to. Attributing by
    close would put the 09:30-10:00 bar into the 10:00 window and shift every
    opening range by one bar.
    """
    out = []
    for i, t in enumerate(bar_times):
        et = to_et(t)
        if et.date() != day:
            continue
        if start <= et.time() < end:
            out.append(i)
    return out


def last_complete_session(bar_times: Sequence[int]) -> Optional[date]:
    if not bar_times:
        return None
    return session_date(bar_times[-1])
