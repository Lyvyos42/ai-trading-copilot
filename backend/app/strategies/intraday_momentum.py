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
    misrepresent both. It is, however, the one of the two that measures well -
    see OpeningRangeBreakoutStrategy.

WHAT THE INTRADAY MOMENTUM EFFECT LOOKS LIKE NOW

First measured on a 1h proxy, then settled on TRUE 30-minute windows from
4+ years of MT5 M30 exports - the exact 09:30-10:00 and 15:30-16:00 bars the
paper is about. Correlation between the two:

    sp500   1058 sessions  2022-04 .. 2026-09   corr -0.0404   t -1.31
    nasdaq  1025 sessions  2022-02 .. 2026-09   corr -0.0267   t -0.85
    us30    1060 sessions  2022-04 .. 2026-09   corr -0.0531   t -1.73
    spy      486 sessions  2024-09 .. 2026-09   corr +0.0520   t +1.15

The sign has FLIPPED on all three series with a thousand sessions behind
them. Not weakened - reversed. Only SPY, on the shortest sample, is still
positive, and it is not significant either.

The tradeable version, taking the sign of the opening window at 15:30 and
exiting at 16:00:

    sp500   sign only     n=1035  win 48.8%  mean -0.54bp  t -0.69  total  -5.56%
            + gap agrees  n= 503  win 50.5%  mean +0.30bp  t +0.25  total  +1.51%
    nasdaq  sign only     n=1013  win 47.0%  mean -0.95bp  t -1.01  total  -9.67%
            + gap agrees  n= 504  win 46.4%  mean -0.80bp  t -0.60  total  -4.03%
    us30    sign only     n=1030  win 49.4%  mean -0.81bp  t -1.20  total  -8.34%
            + gap agrees  n= 507  win 49.5%  mean +0.15bp  t +0.15  total  +0.75%
    spy     sign only     n= 485  win 49.7%  mean -0.09bp  t -0.09  total  -0.42%
            + gap agrees  n= 238  win 49.6%  mean -0.12bp  t -0.09  total  -0.29%

Every t between -1.20 and +0.25 against a Bonferroni threshold of 2.96 at the
16 hypotheses tried. Win rates below 50% on seven of eight. Totals negative on
five of eight. And all of it gross of the spread paid in the closing half
hour, which on a thirty-minute hold is most of the expected move.

This is no longer "unproven on the available proxy". It was tested on exactly
the data the paper specifies, over 3629 sessions across four instruments, and
the effect is absent - with the correlation pointing the other way on the
three longest series. The paper's sample was 1993-2013; whatever was there has
not survived into 2022-2026, which is the ordinary fate of a published
anomaly once it is published.

`require_validation` therefore defaults to True and this abstains. It is kept
rather than deleted because the measurement is worth preserving next to the
citation, and because a future sample could say something different. It should
not be switched on without one.
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
                "INTRADAY_MOMENTUM_REFUTED: tested on true 09:30-10:00 vs "
                "15:30-16:00 M30 windows, 3629 sessions across sp500, nasdaq, "
                "us30 and spy, 2022-2026. Correlation is NEGATIVE on all three "
                "long series (-0.040, -0.027, -0.053); the sign trade returns t "
                "between -1.20 and +0.25 against a 2.96 threshold. The effect "
                "is not present in this sample.")

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

    MEASURED ON 4+ YEARS OF M30, IN R-MULTIPLES (risk = entry to midpoint):

        symbol   filter        n    win%   expR    PF     t
        sp500    gap aligned  460   38.9  +0.560  1.94  +4.89
        sp500    no filter    926   36.8  +0.500  1.81  +6.08
        nasdaq   gap aligned  460   42.2  +0.445  1.81  +4.45
        nasdaq   no filter    934   39.2  +0.368  1.64  +5.27
        us30     gap aligned  483   35.4  +0.192  1.31  +2.13
        us30     no filter    947   35.6  +0.241  1.40  +3.52
        spy      gap aligned  214   37.9  +0.394  1.65  +2.70
        spy      no filter    447   36.5  +0.348  1.56  +3.42

    THE GAP FILTER DOES NOT EARN ITS PLACE, which is the opposite of what was
    expected. It halves the sample on every instrument and lowers the t-statistic
    on every one; on us30 it lowers expectancy outright (+0.192 against +0.241).
    The rationale - that a break with the gap is continuation and against it is
    a fade - is reasonable and simply is not what the data shows. It therefore
    defaults to OFF, and is kept as a parameter so the claim can be re-tested
    rather than argued about.

    OUT OF SAMPLE IS WHERE IT GETS HONEST. Chronological 80/20, no filter,
    1% of the account risked per trade:

        symbol   IS Sharpe  OOS Sharpe  OOS t  retention  maxDD   MC p99 DD
        sp500      3.02        2.37     2.23     0.79    -13.4%    -29.9%
        nasdaq     2.77        1.18     1.11     0.43    -14.5%    -30.7%
        us30       1.80        1.10     1.03     0.61    -20.4%    -39.3%
        spy        2.30        2.95     1.87     1.28    -17.1%    -29.6%

    NONE clears the 2.96 Bonferroni threshold out of sample. sp500 comes
    closest at 2.23 - nominally significant uncorrected, not after correcting
    for the sixteen hypotheses actually tried. nasdaq keeps 43% of its
    in-sample Sharpe, which is the signature of a fit rather than an edge.

    So: a real effect, strong in sample, surviving only partly out of it, and
    not proven at the bar this project uses. `require_validation` defaults to
    True. sp500 and spy are the two worth forward-testing first, on retention.

    SLIPPAGE IS NOT IN ANY OF THESE NUMBERS. The bar that stops a trade travels
    a median 0.45R BEYOND the stop before it closes. How much of that a live
    fill would actually eat is not resolvable at 30-minute granularity - the
    stop may fill at the level and the bar continue afterwards - but the
    expectancy above is gross of whatever it is, and 0.45R against a +0.50R
    edge is the difference between a business and nothing. Winners, by
    contrast, go a median 0.13-0.19R against the entry before working, so the
    midpoint stop is not being clipped by ordinary noise.
    """

    name = "opening_range_breakout"
    requires = (DataNeed.OHLC, DataNeed.SESSION_TIMES)
    validated_on = ()

    def __init__(self, require_gap_alignment: bool = False,
                 min_range_bp: float = 5.0,
                 require_validation: bool = True,
                 flatten_at=FLATTEN_BY):
        super().__init__(require_gap_alignment=require_gap_alignment,
                         min_range_bp=min_range_bp,
                         require_validation=require_validation)
        self.require_gap_alignment = require_gap_alignment
        self.min_range_bp = min_range_bp
        self.require_validation = require_validation
        self.flatten_at = flatten_at

    def min_bars(self) -> int:
        return 4

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        if self.require_validation:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "ORB_OOS_BELOW_THRESHOLD: in-sample t 5.66 (sp500) and 5.19 "
                "(nasdaq) over 4+ years of M30, but out-of-sample t is 2.23 / "
                "1.11 against a 2.96 threshold at 16 hypotheses. A real effect "
                "that is not proven at this bar. Forward-test sp500 and spy "
                "first (Sharpe retention 0.79 and 1.28), then set "
                "require_validation=False per instrument.")

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
