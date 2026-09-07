"""Two separate strategies that the literature is often asked to share.

They are built as distinct classes because they are distinct claims, and only
one of them has a paper behind it.

INTRADAY MOMENTUM (Gao, Han, Li & Zhou 2018, "Market Intraday Momentum")
    A RETURN-PREDICTS-RETURN result. The first half hour's return predicts the
    LAST half hour's return. It says nothing about ranges or breakouts. The
    trade is: at 15:30, take the sign of the first half hour; exit at 16:00.

OPENING RANGE BREAKOUT
    A different strategy: the 09:30-10:00 high and low form a range, entry is
    on a break of it, the stop is the range midpoint, and the position is
    flattened on time. Gao et al. is NOT evidence for this. It is a common
    intraday pattern with a large practitioner literature and no comparable
    peer-reviewed support, and attaching the paper's citation to it would
    misrepresent both.

WHAT THE INTRADAY MOMENTUM EFFECT LOOKS LIKE NOW

Measured on 2 years of Yahoo 1h bars, where the 15:30 bar IS the final half
hour, 497 sessions each:

    SPY   corr(first hour, last half hour) = +0.089   t = +1.98
          trading its sign: n=494  win 48.8%  mean +0.2bp  t = +0.20  total +0.98%
    QQQ   corr = +0.077   t = +1.73
          trading its sign: n=496  win 47.8%  mean +1.0bp  t = +0.78  total +4.75%

The correlation is positive - the paper's direction - and marginal. The
TRADEABLE version has no edge at all: t of 0.20 and 0.78, win rates under
50%, and those are gross of the spread paid in the closing half hour, which
for a half-hour hold is most of the expected move.

The two results are consistent: a positive correlation with a near-zero sign
trade means the relationship lives in MAGNITUDE, not direction. Large first
hours go with large last half hours, without reliably agreeing on which way.

The paper's sample was 1993-2013. This is 2024-2026 on a one-hour proxy of a
half-hour effect. Both differences matter, and neither rescues it: a strategy
this weak on the only data available to test it is not one to deploy on the
strength of a citation. It is implemented so it can be re-tested properly on
the multi-year M30 exports Antigravity can produce from MT5, at the exact
09:30-10:00 and 15:30-16:00 windows the paper uses.

Until that test passes, IntradayMomentumStrategy defaults to
`require_validation=True` and abstains, rather than shipping a signal whose
own measurement says it does not work.
"""
from __future__ import annotations

from typing import Optional

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, Direction, SignalResult,
)
from app.strategies.session_windows import (
    CLOSING_WINDOW_START, FLATTEN_BY, OPENING_RANGE_END, RTH_CLOSE, RTH_OPEN,
    et_epoch, is_half_day, last_complete_session, session_date, to_et,
    window_indices,
)


class IntradayMomentumStrategy(BaseStrategy):
    """Sign of the opening window predicts the closing window."""

    name = "intraday_momentum"
    requires = (DataNeed.OHLC, DataNeed.SESSION_TIMES)
    validated_on = ()   # deliberately empty - see the module docstring

    def __init__(self, require_gap_alignment: bool = False,
                 require_validation: bool = True,
                 min_open_move_bp: float = 0.0):
        super().__init__(require_gap_alignment=require_gap_alignment,
                         require_validation=require_validation,
                         min_open_move_bp=min_open_move_bp)
        self.require_gap_alignment = require_gap_alignment
        self.require_validation = require_validation
        self.min_open_move_bp = min_open_move_bp

    def min_bars(self) -> int:
        return 8

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        if self.require_validation:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "INTRADAY_MOMENTUM_NOT_VALIDATED: measured t=0.20 (SPY) and "
                "0.78 (QQQ) over 497 sessions of 1h proxy bars, win rate "
                "under 50%, gross of spread. Re-test on true 09:30-10:00 and "
                "15:30-16:00 windows from a multi-year M30 export, then set "
                "require_validation=False.")

        day = last_complete_session(bars.time)
        if day is None:
            return SignalResult.abstain(self.name, bars.symbol, "no bars")
        if is_half_day(bars.time, day):
            return SignalResult.abstain(
                self.name, bars.symbol,
                "HALF_SESSION: no 15:30-16:00 window on an early close")

        opening = window_indices(bars.time, day, RTH_OPEN, OPENING_RANGE_END)
        if not opening:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "no bars in the 09:30-10:00 window for this session")

        first_open = bars.open[opening[0]]
        first_close = bars.close[opening[-1]]
        if first_open <= 0:
            return SignalResult.abstain(self.name, bars.symbol, "bad opening price")
        r_open = first_close / first_open - 1.0

        if abs(r_open) * 1e4 < self.min_open_move_bp:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=(f"opening window moved {abs(r_open)*1e4:.1f}bp, under the "
                        f"{self.min_open_move_bp:.0f}bp floor"),
                evidence={"opening_return": r_open})

        direction = Direction.LONG if r_open > 0 else Direction.SHORT

        evidence = {"opening_return": r_open,
                    "opening_bars": len(opening),
                    "session": day.isoformat()}

        if self.require_gap_alignment:
            gap = self._overnight_gap(bars, day)
            evidence["overnight_gap"] = gap
            if gap is None:
                return SignalResult.abstain(
                    self.name, bars.symbol,
                    "gap alignment requested but no prior session close is in "
                    "the series")
            if (gap > 0) != (r_open > 0):
                return SignalResult(
                    strategy=self.name, symbol=bars.symbol,
                    direction=Direction.FLAT,
                    reason=(f"overnight gap {gap*1e4:+.1f}bp disagrees with the "
                            f"opening window {r_open*1e4:+.1f}bp"),
                    evidence=evidence)

        return SignalResult(
            strategy=self.name, symbol=bars.symbol, direction=direction,
            conviction=min(0.8, 0.35 + abs(r_open) * 60.0),
            entry=None,     # entry is at 15:30 on the market, not at a level
            stop=None,      # a 30-minute hold to the close carries no stop
            target=None,
            time_exit_utc=et_epoch(day, RTH_CLOSE),
            reason=(f"opening window {r_open*1e4:+.1f}bp; enter at 15:30, "
                    f"exit at 16:00"),
            evidence=evidence,
        )

    @staticmethod
    def _overnight_gap(bars: BarSeries, day) -> Optional[float]:
        prior = [i for i, t in enumerate(bars.time) if session_date(t) < day]
        if not prior:
            return None
        today = window_indices(bars.time, day, RTH_OPEN, OPENING_RANGE_END)
        if not today:
            return None
        prev_close = bars.close[prior[-1]]
        if prev_close <= 0:
            return None
        return bars.open[today[0]] / prev_close - 1.0


class OpeningRangeBreakoutStrategy(BaseStrategy):
    """Break of the 09:30-10:00 range, stop at its midpoint, flatten on time.

    Not the Gao et al. strategy. See the module docstring.

    The gap filter is the one piece with a defensible rationale: a breakout in
    the direction the market already gapped is a continuation of an overnight
    repricing, while one against the gap is a fade of it, and mixing the two
    into a single statistic averages two different trades.
    """

    name = "opening_range_breakout"
    requires = (DataNeed.OHLC, DataNeed.SESSION_TIMES)
    validated_on = ()

    def __init__(self, require_gap_alignment: bool = True,
                 min_range_bp: float = 5.0,
                 flatten_at=FLATTEN_BY):
        super().__init__(require_gap_alignment=require_gap_alignment,
                         min_range_bp=min_range_bp)
        self.require_gap_alignment = require_gap_alignment
        self.min_range_bp = min_range_bp
        self.flatten_at = flatten_at

    def min_bars(self) -> int:
        return 4

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        day = last_complete_session(bars.time)
        if day is None:
            return SignalResult.abstain(self.name, bars.symbol, "no bars")
        if is_half_day(bars.time, day):
            return SignalResult.abstain(
                self.name, bars.symbol,
                "HALF_SESSION: no time to hold to a 15:50 flatten")

        opening = window_indices(bars.time, day, RTH_OPEN, OPENING_RANGE_END)
        if not opening:
            return SignalResult.abstain(
                self.name, bars.symbol, "no 09:30-10:00 bars for this session")

        or_high = max(bars.high[i] for i in opening)
        or_low = min(bars.low[i] for i in opening)
        mid = (or_high + or_low) / 2.0
        if or_high <= or_low or mid <= 0:
            return SignalResult.abstain(self.name, bars.symbol, "degenerate opening range")

        width_bp = (or_high - or_low) / mid * 1e4
        evidence = {"or_high": or_high, "or_low": or_low, "or_mid": mid,
                    "or_width_bp": width_bp, "session": day.isoformat()}

        # A range narrower than the instrument's own noise produces a breakout
        # on every session and is not a breakout of anything.
        if width_bp < self.min_range_bp:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=(f"opening range {width_bp:.1f}bp is under the "
                        f"{self.min_range_bp:.0f}bp floor"),
                evidence=evidence)

        after = [i for i, t in enumerate(bars.time)
                 if session_date(t) == day and to_et(t).time() >= OPENING_RANGE_END]
        if not after:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason="opening range set; no bars after 10:00 yet",
                evidence=evidence)

        broke_up = any(bars.high[i] > or_high for i in after)
        broke_dn = any(bars.low[i] < or_low for i in after)

        # Both sides broken means the range failed to contain anything. Which
        # came first is not recoverable from bar data, and guessing it is the
        # same error as scoring an ambiguous bar in the signal resolver.
        if broke_up and broke_dn:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason="both sides of the opening range broke; which came "
                       "first is not visible in bar data",
                evidence=evidence)
        if not (broke_up or broke_dn):
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason="price still inside the opening range", evidence=evidence)

        direction = Direction.LONG if broke_up else Direction.SHORT
        entry = or_high if broke_up else or_low

        if self.require_gap_alignment:
            gap = IntradayMomentumStrategy._overnight_gap(bars, day)
            evidence["overnight_gap"] = gap
            if gap is None:
                return SignalResult.abstain(
                    self.name, bars.symbol,
                    "gap alignment requested but no prior session close in series")
            if (gap > 0) != broke_up:
                return SignalResult(
                    strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                    reason=(f"break is {direction.value} but the session gapped "
                            f"{gap*1e4:+.1f}bp the other way"),
                    evidence=evidence)

        risk = abs(entry - mid)
        target = entry + 2.0 * risk if broke_up else entry - 2.0 * risk

        return SignalResult(
            strategy=self.name, symbol=bars.symbol, direction=direction,
            conviction=min(0.75, 0.4 + width_bp / 200.0),
            entry=entry,
            stop=mid,
            target=target,
            # Both matter: whichever comes first. The stop is a real price
            # level here, unlike the overnight and closing-window strategies.
            time_exit_utc=et_epoch(day, self.flatten_at),
            reason=(f"broke the {width_bp:.1f}bp opening range "
                    f"{'above' if broke_up else 'below'} {entry:.4f}; stop at "
                    f"the midpoint {mid:.4f}, flatten 15:50"),
            evidence=evidence,
        )
