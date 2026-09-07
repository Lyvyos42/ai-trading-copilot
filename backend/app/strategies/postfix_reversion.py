"""postfix_reversion: does the London 16:00 WMR fix-hour move reverse daily?

MOTIVATION
The month-end study found a post-fix inversion on all six USD pairs (t -3.77 to
-5.36). The fix happens every day, so if dealer inventory built to service it is
unwound afterwards, the effect should appear on ~4,137 sessions rather than 167.
That is 24.8x the sample, on data already staged, needing no conditioning
variable - a reversal does not require SPY.

PRE-REGISTERED
    universe   EURUSD, GBPUSD, AUDUSD, NZDUSD, USDCAD, USDCHF H1, 2010-2026
    signal     r15, the 15:00-16:00 London bar return (into the fix)
    trade      at the 16:00 London open take the OPPOSITE side of r15, exit at
               the 17:00 London close
    costs      non-zero-median spread + $3/lot, measured per pair, in bp
    power      filed a priori: post-fix sigma ~12 bp, so n=4,100 detects a
               0.50 bp mean at t 2.0 against a toll of 0.64-1.87 bp. COST, not
               power, is the binding constraint - the first time in this
               programme that was true, which is why the candidate was run.

THE CONTROL WAS THE EXPERIMENT AND IT REFUTED THE CANDIDATE

Bid-ask bounce induces negative autocorrelation between ANY two adjacent bars:
r(h) ends at the printed price where r(h+1) begins, so noise in that shared
price pushes one up and the other down. A negative beta at the fix hour is
therefore not evidence of anything by itself. The pre-registered test was
whether the fix hour is more negative than the SAME PAIR's other 23 hourly
betas.

    pair        n    beta(fix)      t   median other   5th pct   rank   G2
    eurusd   4136     -0.0437   -3.85       -0.0042   -0.0653   4/23  FAIL
    gbpusd   4137     -0.0101   -0.86       -0.0138   -0.1489  15/23  FAIL
    audusd   4137     -0.0491   -4.38       -0.0012   -0.1027   4/23  FAIL
    nzdusd   4138     -0.0523   -4.55       -0.0180   -0.0850   5/23  FAIL
    usdcad   4137     -0.0149   -1.33       -0.0227   -0.1037  15/23  FAIL
    usdchf   4137     -0.0922   -8.34       -0.0309   -0.1508   4/23  FAIL

Gate 1 passes on four pairs - the fix-hour beta IS negative and significant.
Gate 2 fails on all six. The fix hour is never below the 5th percentile of its
own pair's hourly betas, and ranks as low as 15th of 23. It is an ordinary
hour, not a special one.

GBPUSD - the pair the entire month-end result was built on - has the WEAKEST
fix-hour reversion of the six: beta -0.0101 at t -0.86, ranked 15th of 23.

THE TRADE LOSES ON EVERY PAIR

    pair      toll   gross      net       t    OOS    2010-15   2016-26
    eurusd    0.85  +0.450   -0.398   -2.27  -0.658    -0.166    -0.512
    gbpusd    0.93  +0.183   -0.749   -3.84  -0.754    -0.948    -0.650
    audusd    1.40  +0.460   -0.945   -4.35  -1.511    -0.787    -1.022
    nzdusd    1.87  +0.463   -1.404   -6.35  -2.314    -0.803    -1.700
    usdcad    0.64  +0.437   -0.205   -1.10  -0.590    -0.235    -0.190
    usdchf    1.29  +0.818   -0.476   -2.49  -0.756    -0.592    -0.419

Gross expectancy is +0.18 to +0.82 bp against a toll of 0.64 to 1.87 bp. The
reversion is real but smaller than the spread on all six, out of sample and in
both eras. Gates 3, 4 and 5 fail six times each.

WHAT THE HOURLY PROFILE SHOWS, WHICH IS WORTH KEEPING

    mean beta, thin hours (20:00-07:00 London):   -0.0334
    mean beta, active hours (08:00-19:00):        -0.0159

    strongest reversions across the six pairs:
      usdchf 09->10  -0.2612 (t -43.36)    gbpusd 01->02  -0.1685 (t -13.40)
      audusd 22->23  -0.1905 (t -10.64)    gbpusd 22->23  -0.1513 (t -11.32)

Reversion concentrates in the thin-liquidity hours - late Asia, post-New-York -
which is the bid-ask bounce signature the control was written to detect. The
London afternoon, the fix included, is among the quietest. Anyone measuring
short-horizon mean reversion in FX without an hour-of-day control will find a
large effect that is entirely a spread artefact.

The usdchf 09->10 cell at t -43.36 is a further outlier that deserves its own
data-quality check before anyone treats it as a signal.

THIS DOES NOT OVERTURN THE MONTH-END RESULT
The month-end finding regressed the post-fix hour on the SPY MONTH return -
a reversal conditional on the flow driver. This regresses it on the fix-hour
move itself, unconditionally. They are different quantities. What is refuted is
that the fix hour has a generic daily reversion; the conditional month-end
reversal is untouched by this test.

VERDICT: refuted. The mechanism does not generalise from 167 month-ends to
4,137 daily sessions, and the reversion that does exist is a spread artefact
concentrated in illiquid hours.
"""
from __future__ import annotations

from app.strategies.base import BarSeries, BaseStrategy, DataNeed, SignalResult


class PostFixReversionStrategy(BaseStrategy):
    """Fade the London 16:00 fix-hour move. Refuted."""

    name = "postfix_reversion"
    requires = (DataNeed.OHLC, DataNeed.SESSION_TIMES)
    intervals = ("1h", "H1", "60m")
    validated_on = ()

    def min_bars(self) -> int:
        return 4

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        return SignalResult.abstain(
            self.name, bars.symbol,
            "POSTFIX_REVERSION_REFUTED: 24,825 sessions across six USD pairs, "
            "2010-2026. The fix-hour beta is negative and significant on four "
            "pairs, but on ALL SIX it sits inside the ordinary distribution of "
            "that pair's other 23 hourly betas - ranking 4th to 15th of 23 and "
            "never below the 5th percentile. Bid-ask bounce makes every "
            "adjacent hour-pair revert; the fix hour is not special, and "
            "GBPUSD - the pair the month-end result was built on - has the "
            "WEAKEST fix-hour reversion of the six (beta -0.0101, t -0.86, "
            "rank 15/23). The trade loses on every pair: gross +0.18 to +0.82 "
            "bp against a toll of 0.64 to 1.87 bp, negative out of sample and "
            "in both eras. Reversion concentrates in thin-liquidity hours "
            "(mean beta -0.0334 for 20:00-07:00 London against -0.0159 for "
            "08:00-19:00), which is the spread artefact the control was "
            "written to catch. Does NOT overturn the month-end finding, which "
            "regressed the post-fix hour on the SPY month return - a different "
            "and conditional quantity.")
