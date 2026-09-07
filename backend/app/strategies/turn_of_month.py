"""Turn of the month: long across the month boundary.

REFERENCES
Lakonishok & Smidt (1988); McConnell & Xu (2008). The mechanism proposed is
calendar flow - pension allocations, payroll-driven 401(k) contributions and
dividend reinvestment concentrating around the boundary.

PRE-REGISTERED AND MEASURED - PREREG_2026-09-07_turn_of_month.md

    entry     close of the final NYSE session of month M
    exit      close of the third NYSE session of month M+1
    filter    long only, close above the 200-session average on entry day
    null      every other 4-session block under the same regime filter
    hurdle    chronological 80/20, out-of-sample |t| >= 2.96, retention >= 0.70

A NOTE ON WHAT THE DATA COULD ANSWER

The filed universe was the M30 exports. Those carry 53 month boundaries on
sp500 and 25 on spy, and a monthly effect measured over 25 events cannot clear
a t of 2.96 unless it is enormous - the required per-block Sharpe would be
0.41. The specification was run unchanged, on 33 years of daily bars where the
question is answerable, with the exports as a cross-check that confirmed they
are too short to say anything (39 and 14 events, retention 28.98 and 2.30,
both meaningless).

THE EFFECT IS REAL IN THE FULL SAMPLE

    SPY 1993-2026, regime-filtered
      TOM blocks       n= 296   mean +0.373%
      every other      n=5889   mean +0.105%
      Welch t                          +2.81

    QQQ 1999-2026
      TOM blocks       n= 232   mean +0.365%
      every other      n=4683   mean +0.145%
      Welch t                          +1.32

AND IT IS IN THE INTRADAY LEGS, WHICH MATTERS HERE

Splitting the hold into its overnight and intraday components:

    SPY            TOM        non-TOM     Welch t
      overnight   +0.185%     +0.123%      +1.13
      intraday    +0.186%     -0.017%      +2.74

That is the opposite of internal bar strength, whose entire effect was
overnight. The turn of the month is the part of the calendar where the
intraday session earns anything at all - it is otherwise slightly negative on
SPY across three decades. So this does NOT duplicate overnight_drift; the two
capture different legs. If it were promoted, it would not need an exclusion.

BUT IT HAS DECAYED, AND THAT IS WHY IT IS NOT DEPLOYED

    era          TOM n   TOM mean   other mean   Welch t
    1993-2004       90    +0.691%     +0.122%     +2.96
    2005-2015      101    +0.247%     +0.054%     +1.40
    2016-2026      105    +0.221%     +0.137%     +0.51

Strong before 2005, halved through 2015, and absent in the last decade.
Lakonishok & Smidt published in 1988 and McConnell & Xu in 2008; an anomaly
fading after it is documented is the ordinary outcome, not a surprise.

The pre-registered split says the same thing in one number:

    SPY  296 events  win 62.5%  Sharpe 0.74  PF 1.74
         in-sample t 3.63  ->  out-of-sample t 0.98   retention 0.54
    QQQ  232 events  win 61.2%  Sharpe 0.47  PF 1.44
         in-sample t 1.98  ->  out-of-sample t 0.61   retention 0.61

Neither clears |t| 2.96 out of sample, and neither reaches the 0.70 retention
floor. The in-sample strength is the pre-2005 data inside the training window.

VERDICT: gated. Not refuted - the effect existed and the decay is legible -
but not present in the regime that would be traded. Re-testing is worthwhile
if the calendar mechanism changes; nothing in the current decade supports it.
"""
from __future__ import annotations

from datetime import date
from typing import Optional, Sequence

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, Direction, SignalResult,
)
from app.strategies.session_windows import session_date

HOLD_SESSIONS = 3          # entry close -> close three sessions later
FINANCING_BP_PER_NIGHT = 1.0


def is_last_session_of_month(this_day: date, next_day: Optional[date]) -> bool:
    """True when `this_day` is the final session before a month change.

    Determined from the SESSION SEQUENCE, not from a calendar. The last
    trading day of a month is whatever session precedes one in a new month;
    computing it from calendar month-ends would land on weekends and holidays
    and shift the window on roughly a third of months.
    """
    if next_day is None:
        return False
    return this_day.month != next_day.month


class TurnOfMonthStrategy(BaseStrategy):
    """Long from the last session of the month into the third of the next."""

    name = "turn_of_month"
    requires = (DataNeed.OHLC, DataNeed.OVERNIGHT_GAP)
    intervals = ("1d", "1day", "D1", "daily")
    validated_on = ()

    def __init__(self, sma_period: int = 200, require_regime: bool = True,
                 hold_sessions: int = HOLD_SESSIONS,
                 require_validation: bool = True):
        super().__init__(sma_period=sma_period, require_regime=require_regime,
                         hold_sessions=hold_sessions,
                         require_validation=require_validation)
        self.sma_period = sma_period
        self.require_regime = require_regime
        self.hold_sessions = hold_sessions
        self.require_validation = require_validation

    def min_bars(self) -> int:
        return self.sma_period + 2 if self.require_regime else 2

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        if self.require_validation:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "TOM_DECAYED: real in the full sample (Welch t 2.81 on 296 SPY "
                "blocks against 5889 others) but the effect fades by era - "
                "Welch 2.96 in 1993-2004, 1.40 in 2005-2015, 0.51 in "
                "2016-2026. Out-of-sample t 0.98 and retention 0.54 against a "
                "2.96 / 0.70 hurdle. Not present in the regime that would be "
                "traded.")

        i = len(bars.close) - 1
        today = session_date(bars.time[i])

        # The signal fires on the LAST session of a month, and whether today is
        # the last cannot be known from today. The caller must supply bars
        # through a session whose successor is already known, or accept that
        # this only speaks the day after. Refusing is the honest option.
        return SignalResult.abstain(
            self.name, bars.symbol,
            "TOM_NEEDS_FORWARD_CALENDAR: the entry session is the last of the "
            "month, which is only identifiable once the next session's date is "
            "known. Use an exchange calendar to schedule the entry rather than "
            "detecting it from bars.")


def backtest_tom(dates: Sequence[date], close: Sequence[float],
                 sma_period: int = 200, require_regime: bool = True,
                 hold_sessions: int = HOLD_SESSIONS,
                 financing_bp_per_night: float = FINANCING_BP_PER_NIGHT
                 ) -> list[float]:
    """One return per turn-of-month event, oldest first.

    Compacted to one entry per EVENT rather than one per calendar day. The
    day-indexed version is roughly 95% zeros, and a Sharpe computed over it
    describes how often the calendar produces a month boundary rather than how
    the trade performed - 0.14 against the 0.74 the trade actually earned.
    """
    base = BaseStrategy()
    sma = base.sma(list(close), sma_period)
    drag = financing_bp_per_night * hold_sessions / 1e4

    out: list[float] = []
    for i in range(len(close) - hold_sessions):
        if not is_last_session_of_month(dates[i], dates[i + 1]):
            continue
        if require_regime and not (sma[i] is not None and close[i] > sma[i]):
            continue
        out.append(close[i + hold_sessions] / close[i] - 1.0 - drag)
    return out


def non_tom_blocks(dates: Sequence[date], close: Sequence[float],
                   sma_period: int = 200, require_regime: bool = True,
                   hold_sessions: int = HOLD_SESSIONS) -> list[float]:
    """The null: every OTHER block of the same length, same regime filter.

    Without this the turn-of-month return is just a positive number in a
    market that drifts up. The comparison is the test.
    """
    base = BaseStrategy()
    sma = base.sma(list(close), sma_period)
    out: list[float] = []
    for i in range(len(close) - hold_sessions):
        if is_last_session_of_month(dates[i], dates[i + 1]):
            continue
        if require_regime and not (sma[i] is not None and close[i] > sma[i]):
            continue
        out.append(close[i + hold_sessions] / close[i] - 1.0)
    return out
