"""Donchian breakout failure: fade a swept channel extreme that closes back in.

REFERENCES
Donchian (1970) for the channel; Raschke & Connors (1996) "Turtle Soup";
Crabel (1990).

PRE-REGISTERED - PREREG_2026-09-07_donchian_breakout_failure.md

    setup    bar high >= upper band + 0.10 * ATR(14) but close back below it
             (mirrored for the low)
    entry    open of the next M30 bar
    stop     the sweep bar's extreme +/- 0.25 * ATR(14)
    exits    variant 1 channel midpoint, variant 2 1.5R or a 24-bar time stop
    bands    N = 20 and N = 48, from the PRIOR N bars
    hurdles  chronological 80/20, out-of-sample |t| >= 2.96, retention >= 0.70,
             plus two compulsory tests below

THE BANDS EXCLUDE THE CURRENT BAR
An upper band computed over a window that includes the bar being tested cannot
be exceeded by it - the setup would never fire, or would fire only on floating
point noise. The channel is the prior N bars and nothing else.

RESULT ACROSS THE UNIVERSE, net of spread and a 2.2%-of-R tick jump

    symbol    N  exit         n   win%   net expR     PF       t
    sp500    20  midpoint  1218   28.8     -0.878   0.30  -17.17
    sp500    48  midpoint   929   26.6     -0.635   0.47   -9.07
    nasdaq   20  midpoint  1262   33.9     -0.193   0.73   -4.50
    nasdaq   48  midpoint   963   27.3     -0.087   0.89   -1.23
    spy      20  midpoint   184   42.4     +0.354   1.62   +2.40
    spy      20  1.5R       184   44.6     +0.087   1.15   +0.96
    spy      48  midpoint   133   30.8     +0.293   1.42   +1.41

THE CFD RESULTS ARE A COST STORY, NOT A STRATEGY STORY

    symbol   median risk unit   median cost   gross expR   net expR
    sp500       6.28 points        0.701R       +0.021      -0.878
    nasdaq     29.67 points        0.098R       -0.071      -0.193
    spy         1.46 points        0.029R       +0.384      +0.354

sp500's risk unit is 6.28 index points against a 2.0-point cash-session
spread and 5.0 overnight, so the cost is 70% of R inside the session and
103% outside it. Its GROSS expectancy is +0.021R - nothing to erode. Split by
session: entries in RTH cost 0.30R, entries outside cost 1.03R.

That is a general result about half-hour mean reversion on these CFDs, not a
fact about Donchian: the risk unit that a 0.25-ATR stop produces on M30 bars
is simply too small relative to the quoted spread. Any strategy of this shape
will meet the same wall on sp500.

nasdaq is negative GROSS (-0.071R), so it fails on its own terms.

Only SPY, with a penny spread and a real exchange tape, shows an edge.

THE COMPULSORY TESTS, ON SPY

  1. DIRECTIONAL SYMMETRY - marginal
        LONG    n= 83  win 50.6%  +0.456R  t +2.34
        SHORT   n=101  win 35.6%  +0.270R  t +1.26
     Shorts are positive, so the letter of the condition is met, but at t 1.26
     they are not a demonstration of anything. Longs carry roughly twice the
     statistic. Some of what looks like auction failure is the market going up.

  2. COHORT OVERLAP WITH overnight_drift - FAILED
        Cohort 1, entering 15:00-16:00 ET   n=19  +0.572R  t +1.62
        Cohort 2, pure intraday             n=64  +0.421R  t +1.83
     Cohort 2 was required to reach t >= 2.0 independently. It does not. The
     intraday cohort is not shown to stand on its own.

  3. PRE-REGISTERED SPLIT - FAILED on significance, PASSED on retention
        in-sample Sharpe 1.70 -> out-of-sample 1.69
        out-of-sample t 1.07 against 2.96
        retention 0.99

     Retention of 0.99 is the best of any candidate tested here: the
     out-of-sample Sharpe is the in-sample one. What defeats it is sample
     size - 184 trades over two years leaves 37 out of sample, and 37 trades
     cannot produce t 2.96 at any plausible effect size.

VERDICT: gated, and the closest of the refused candidates.

Nothing here says the effect is absent. It says the only instrument that can
carry it has two years of data, and on those two years the out-of-sample
window is too short to clear the bar while the shape of the result -
retention 0.99 - is what a real edge looks like. A deeper SPY export, or the
same test on another penny-spread ETF with a real tape, is the way to settle
it. The CFDs cannot, at any sample size, because the spread eats the risk
unit.
"""
from __future__ import annotations

from typing import Optional, Sequence

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, Direction, SignalResult,
)

DEFAULT_LOOKBACK = 20
PENETRATION_ATR = 0.10
STOP_ATR = 0.25
TIME_STOP_BARS = 24


class DonchianFailureStrategy(BaseStrategy):
    """Fade a channel extreme that was swept and rejected inside one bar."""

    name = "donchian_fail"
    requires = (DataNeed.OHLC,)
    intervals = ("30m", "M30", "15m", "M15")
    validated_on = ()

    def __init__(self, lookback: int = DEFAULT_LOOKBACK,
                 penetration_atr: float = PENETRATION_ATR,
                 stop_atr: float = STOP_ATR,
                 exit_variant: str = "midpoint",
                 time_stop_bars: int = TIME_STOP_BARS,
                 require_validation: bool = True):
        super().__init__(lookback=lookback, penetration_atr=penetration_atr,
                         stop_atr=stop_atr, exit_variant=exit_variant,
                         time_stop_bars=time_stop_bars,
                         require_validation=require_validation)
        self.lookback = lookback
        self.penetration_atr = penetration_atr
        self.stop_atr = stop_atr
        self.exit_variant = exit_variant
        self.time_stop_bars = time_stop_bars
        self.require_validation = require_validation

    def min_bars(self) -> int:
        return self.lookback + 16

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        if self.require_validation:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "DONCHIAN_FAIL_UNPROVEN: SPY nets +0.354R at t 2.40 with "
                "out-of-sample Sharpe retention 0.99, but out-of-sample t is "
                "1.07 against 2.96 on 37 holdout trades, and the required "
                "intraday cohort reaches only t 1.83 against 2.0. sp500 and "
                "nasdaq fail outright - sp500's cost is 0.70R inside the "
                "session against a gross edge of +0.021R.")

        n = len(bars)
        i = n - 1
        atr = self.atr(bars.high, bars.low, bars.close, 14)[i]
        if atr is None or atr <= 0:
            return SignalResult.abstain(self.name, bars.symbol, "ATR unavailable")

        lo_i = i - self.lookback
        if lo_i < 0:
            return SignalResult.abstain(
                self.name, bars.symbol, f"needs {self.lookback} prior bars")

        # Prior N bars only. Including the current bar makes the band
        # unbreakable by it.
        upper = max(bars.high[lo_i:i])
        lower = min(bars.low[lo_i:i])
        mid = (upper + lower) / 2.0

        hi, lo, cl = bars.high[i], bars.low[i], bars.close[i]
        evidence = {"upper": upper, "lower": lower, "mid": mid, "atr": atr,
                    "lookback": self.lookback}

        swept_high = hi >= upper + self.penetration_atr * atr and cl < upper
        swept_low = lo <= lower - self.penetration_atr * atr and cl > lower

        if not (swept_high or swept_low):
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason="no channel extreme was swept and rejected in this bar",
                evidence=evidence)

        side = -1 if swept_high else 1
        stop = (hi + self.stop_atr * atr) if swept_high else (lo - self.stop_atr * atr)
        # Entry is the NEXT bar's open, which does not exist yet. The level
        # quoted is the current close as a reference; the execution layer fills
        # at the open it actually sees.
        reference = cl
        risk = abs(reference - stop)
        if risk <= 0:
            return SignalResult.abstain(self.name, bars.symbol, "degenerate stop distance")

        target = mid if self.exit_variant == "midpoint" else reference + side * 1.5 * risk

        return SignalResult(
            strategy=self.name, symbol=bars.symbol,
            direction=Direction.SHORT if side < 0 else Direction.LONG,
            conviction=0.5,
            entry=None,          # fills at the next bar's open, not at a level
            stop=stop, target=target,
            horizon_bars=self.time_stop_bars,
            reason=(f"swept the {'upper' if swept_high else 'lower'} "
                    f"{self.lookback}-bar channel by "
                    f"{abs((hi - upper) if swept_high else (lower - lo)) / atr:.2f} ATR "
                    f"and closed back inside; fade toward "
                    f"{'the midpoint' if self.exit_variant == 'midpoint' else '1.5R'}"),
            evidence={**evidence,
                      "penetration_atr": (abs((hi - upper) if swept_high else (lower - lo)) / atr),
                      "reference_close": reference,
                      "exit_variant": self.exit_variant},
        )
