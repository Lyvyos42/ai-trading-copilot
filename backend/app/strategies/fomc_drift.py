"""Pre-FOMC announcement drift: long into a scheduled rate decision.

REFERENCE
Lucca & Moench (2015), "The Pre-FOMC Announcement Drift", Journal of Finance.
Their result is the ~24 hours BEFORE a scheduled announcement, sampled
1980-2011.

PRE-REGISTERED - PREREG_2026-09-07_fomc_drift.md

    W1   14:00 ET on day t-1  ->  the announcement instant on day t
    W2   10:00 ET on day t    ->  the announcement instant on day t
    release times: 14:15 ET before 2013-01-01, 14:00 ET from 2013-01-01
    long only, matched non-FOMC control at the identical time of day
    gates: OOS |t| >= 2.96, retention >= 0.70, most-recent-third |t| >= 2.0,
           non-overnight leg standing alone at |t| >= 2.0

STATUS: THE STUDY IS BLOCKED, NOT CONCLUDED. Two things stop it, one of them
mine.

BLOCKER 1 - THE EVENT FILE IS SYSTEMATICALLY INCOMPLETE AFTER 2020

fomc_dates.csv carries a clean eight meetings a year from 1993 to 2019, and
then four to seven a year from 2020. The missing ones are not random:

    era          rows falling in a projection month (Mar/Jun/Sep/Dec)
    1993-2020    102 of 223    46%     (the true share is about 50%)
    2021-2026      2 of  25     8%

March and June are absent entirely from 2021 onward. Those are the meetings
that carry the Summary of Economic Projections and the press conference - the
highest-information events of the cycle, and precisely where a
pre-announcement drift should be largest. What survives in the file is the
low-information subset.

That is the worst possible bias for this particular question, and it lands
exactly on the 2018-2026 window the modern-third gate was written to test. The
gate cannot be evaluated until the file is completed.

BLOCKER 2 - DAILY BARS CANNOT RESOLVE A 14:00 BOUNDARY, WHICH I SHOULD HAVE
SAID WHEN I PROPOSED THE SPECIFICATION

The spec names SPY 1993-2026 as a primary universe on 248 events. SPY is
available here only as daily bars, and a daily bar cannot see 14:00. Neither
W1 nor W2 is computable on it. What IS computable is the OVERNIGHT LEG of W1 -
close on t-1 to open on t - which is a strict subset that ends well before the
announcement and is therefore clean, just partial.

IWM M30 resolves both windows exactly, and covers 2011 onward, which leaves 69
usable W1 events in the complete portion of the event file.

WHAT THE RUNNABLE PORTION SHOWS

IWM M30, 2011-2019, windows resolved exactly:

    window                       n   mean     t     null    Welch
    W1  14:00 t-1 -> 14:00 t    69  +3.5bp  +0.33  +3.3bp   +0.02
    W2  10:00 t   -> 14:00 t    54  -5.8bp  -0.76  +0.0bp   -0.74

Nothing. The exactly-specified windows are indistinguishable from an ordinary
day at the same hours, and the pure-intraday subset is negative.

SPY daily, 1993-2019, overnight leg only, 216 events:

    +10.7bp against a +3.1bp control      t +2.63    Welch +1.84

and by era:

    1993-2001   n=72   +2.3bp   t +0.62   Welch -0.62
    2002-2010   n=72  +17.6bp   t +1.77   Welch +1.75
    2011-2019   n=72   +9.4bp   t +1.60   Welch +1.24

    80/20 split: in-sample t 2.07 -> out-of-sample t 1.95, retention 1.87

Nothing clears 2.96 on any measure. The overnight leg is concentrated in
2002-2010 and weaker on either side of it, which is the decay shape again -
though on 72 events per era none of these differences is itself significant.

READ THIS CAREFULLY BEFORE CONCLUDING ANYTHING

The one leg that shows anything is the leg the specification did NOT ask for,
measured on the instrument that could not run the specification. The two
windows that were pre-registered, on the instrument that can resolve them,
show nothing at all - on 69 events, which is too few to be evidence of absence
either.

This is not a refutation and it is not a result. It is a study whose primary
universe was unrunnable and whose modern era is unavailable. Completing the
event file and adding an intraday SPY series would make it answerable; until
then the honest status is blocked.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, time as dtime
from pathlib import Path
from typing import Optional, Sequence

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, Direction, SignalResult,
)
from app.strategies.session_windows import EXCHANGE_TZ, to_et

FOMC_FILE = Path(__file__).resolve().parents[1] / "data" / "fomc_dates.csv"

# The statement moved from 14:15 to 14:00 on this date. Using one time across
# the whole sample puts 15 minutes of POST-announcement move inside the
# pre-announcement window for every event before it.
RELEASE_TIME_CHANGE = date(2013, 1, 1)


def load_fomc_dates(path: Optional[Path] = None) -> dict[date, dtime]:
    """Announcement date -> release time, Eastern."""
    p = Path(path) if path else FOMC_FILE
    out: dict[date, dtime] = {}
    if not p.exists():
        return out
    with p.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                d = datetime.strptime(row["date"], "%Y-%m-%d").date()
                hh, mm = row.get("release_time_et", "").split(":")
                out[d] = dtime(int(hh), int(mm))
            except (KeyError, ValueError):
                continue
    return out


def release_time(d: date, table: Optional[dict[date, dtime]] = None) -> dtime:
    """Release time for a date, from the table, falling back to the rule."""
    if table and d in table:
        return table[d]
    return dtime(14, 0) if d >= RELEASE_TIME_CHANGE else dtime(14, 15)


def projection_month_share(dates: Sequence[date]) -> float:
    """Share of events in a March/June/September/December meeting.

    A complete schedule sits near 0.5. A much lower figure means the
    high-information meetings have gone missing, which is the failure mode
    found in the delivered file after 2020.
    """
    if not dates:
        return 0.0
    return sum(1 for d in dates if d.month in (3, 6, 9, 12)) / len(dates)


class FOMCDriftStrategy(BaseStrategy):
    """Long into a scheduled FOMC announcement."""

    name = "fomc_drift"
    requires = (DataNeed.OHLC, DataNeed.SESSION_TIMES)
    intervals = ("30m", "M30", "15m", "M15")
    validated_on = ()

    def __init__(self, window: str = "W1", require_validation: bool = True,
                 fomc_path: Optional[Path] = None):
        super().__init__(window=window, require_validation=require_validation)
        self.window = window
        self.require_validation = require_validation
        self._table = load_fomc_dates(fomc_path)

    def min_bars(self) -> int:
        return 30

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        if self.require_validation:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "FOMC_STUDY_BLOCKED: the event file is missing every "
                "projection-month meeting from 2021 (8% of rows fall in "
                "Mar/Jun/Sep/Dec against a true 50%), so the modern-third gate "
                "cannot run; and SPY exists here only as daily bars, which "
                "cannot resolve a 14:00 boundary. On the runnable portion - IWM "
                "M30 2011-2019, 69 events - W1 returns t +0.33 and W2 t -0.76.")

        if not self._table:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "no FOMC date table loaded; see app/data/fomc_dates.csv")

        today = to_et(bars.time[-1]).date()
        rel = self._table.get(today)
        if rel is None:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason="not a scheduled FOMC announcement day",
                evidence={"session": today.isoformat()})

        now = to_et(bars.time[-1]).time()
        if now >= rel:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=f"announcement at {rel.strftime('%H:%M')} ET has passed",
                evidence={"release_time_et": rel.strftime("%H:%M")})

        return SignalResult(
            strategy=self.name, symbol=bars.symbol, direction=Direction.LONG,
            conviction=0.5,
            entry=bars.close[-1],
            # No stop. The position is closed at a scheduled INSTANT, and a
            # price level between here and there would not be what closes it.
            stop=None, target=None,
            reason=(f"holding into the {rel.strftime('%H:%M')} ET announcement "
                    f"on {today.isoformat()} ({self.window})"),
            evidence={"session": today.isoformat(),
                      "release_time_et": rel.strftime("%H:%M"),
                      "window": self.window},
        )
