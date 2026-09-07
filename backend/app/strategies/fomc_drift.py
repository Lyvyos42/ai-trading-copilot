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

RESULT, on the repaired schedule: FAILS TWO OF THREE GATES, AND THE WAY IT
FAILS IS THE MOST INTERESTING FINDING IN THE PROGRAMME.

Both earlier blockers are resolved. The event file now carries eight scheduled
meetings a year across all 33 years with a 46.9% projection-month share, and
IWM M30 resolves both windows exactly. The two unscheduled 2020 cuts are
excluded: an emergency action has no anticipation window, which is the whole
mechanism, and neither had a 14:00 or 14:15 release.

    IWM 2011-2026, 99 events with all required bars present
      W1  14:00 t-1 -> release    +18.9bp   win 52.5%   t +1.88   Welch +1.43
      W2  10:00 t   -> release     +4.1bp   win 46.5%   t +0.58   Welch +0.66

    sp500 2022-2026, 34 events - independent cross-check
      W1  +20.6bp   win 64.7%   t +1.86   Welch +1.55
      W2   +1.2bp   win 41.2%   t +0.30   Welch -0.07

W1 reproduces at nearly the same magnitude on a second instrument and a
different sample. W2, the intraday subset, is nothing on both - which is the
correct outcome, since the intraday window is not the paper's claim.

GATE 1, MODERN THIRD - PASSED, AND IT IS THE ONLY CANDIDATE TO DO SO

    2011-2014   n=23    -8.0bp   t -0.37   Welch -0.60
    2015-2017   n=18    +3.9bp   t +0.29   Welch +0.03
    2018-2026   n=58   +34.2bp   t +2.46   Welch +2.12

The modern era is the STRONGEST, not the weakest. Every other candidate here
ran the other way - turn-of-the-month went 2.96 to 0.51, Donchian went 3.69 to
-0.68. This one has no decay to find. Lucca & Moench published in 2015 and the
effect is larger after 2018 than before it.

GATE 2, OVERLAP - FAILED, AND THIS IS WHERE IT GETS USEFUL

    14:00 t-1 -> cash close t-1      -6.2bp   t -1.21
    overnight, cash close -> 09:30  +21.1bp   t +3.22   Welch +2.45
    09:30 t -> release               +4.8bp   t +0.69
    non-overnight portion (A + C)    -2.2bp   t -0.26   <- required >= 2.00

The whole of W1 is its overnight leg. The two intraday portions contribute
nothing and the earlier one is negative. So "pre-FOMC drift", measured here, is
an overnight hold - which overnight_drift already makes every night.

Except it does not make THIS one. Splitting the FOMC overnight leg by regime:

    above the 200-day average   n=85   +9.5bp  vs +4.6bp control   Welch +0.85
    BELOW the 200-day average   n=29  +42.5bp  vs +2.9bp control   Welch +2.32

The effect lives BELOW the 200-day average, in the conditions overnight_drift's
regime gate exists to refuse. Inside that gate, an FOMC night is worth +5.8bp
against +4.1bp for an ordinary one - Welch +0.36, nothing.

That is consistent with the mechanism rather than a coincidence: Lucca & Moench
report the drift is larger when uncertainty is high, and a market under its
200-day average is the definition of the uncertain regime. The two strategies
want OPPOSITE regimes. They do not overlap; they are disjoint, which is the
reverse of what the overlap gate was written to detect.

GATE 3, PRE-REGISTERED SPLIT - FAILED on significance, PASSED on retention

    in-sample Sharpe 0.48 -> out-of-sample 0.84
    out-of-sample t 1.32 against 2.96      retention 1.75

VERDICT: gated as a standalone strategy - two of three gates failed.

What it is NOT is refuted. Every measurement points the same way and none of
them reaches the bar: W1 reproduces across two instruments at +19 and +21bp,
the modern third clears its own gate at t 2.46, and the mechanism's own
prediction - stronger under uncertainty - is visible at Welch +2.32. What
defeats it is 99 events, of which 29 sit in the regime that carries the
effect. Eight events a year cannot be hurried.

The interesting deployment is not a strategy of its own. It is a COUNTER-REGIME
companion to overnight_drift: hold the night before a scheduled announcement
specifically when price is below its 200-day average, which is precisely when
overnight_drift is flat. On 29 observations that is a hypothesis, not a
position. A deeper intraday series - SPY M30 back to 1993 would give about 248
events and perhaps 70 in the low regime - is what would settle it, and unlike
the decayed candidates there is a reason to expect the answer to still be
there when the data arrives.
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
                "FOMC_DRIFT_UNDERPOWERED: W1 reproduces on two instruments "
                "(+18.9bp t 1.88 on IWM, +20.6bp t 1.86 on sp500) and the "
                "modern third clears its own gate at t 2.46 - the only "
                "candidate here with no decay. But the whole effect is the "
                "overnight leg (t 3.22) and it lives BELOW the 200-day average "
                "(Welch 2.32, n=29), so the non-overnight gate fails at t -0.26 "
                "and out-of-sample t is 1.32 against 2.96. Underpowered, not "
                "refuted.")

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
