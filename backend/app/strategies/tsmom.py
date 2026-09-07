"""tsmom: volatility-scaled time-series momentum on H1 gold and USDJPY.

REFERENCE
Moskowitz, Ooi & Pedersen (2012), "Time Series Momentum", JFE. Their result is
monthly, across 58 futures, over 1965-2009. This tests an hourly implementation
on two instruments over 16-17 years, which is a different object and should be
read as such.

PRE-REGISTERED

    primary    XAUUSD H1, 99,000 bars, 2009-10 to 2026-09
    validation USDJPY H1, 99,000 bars, 2010-09 to 2026-09
    signal     sign of the L-bar return, L in [480, 1200, 2400] (20/50/100 days)
    entry      the next bar's open on a FRESH sign change
    exit       a trailing 240-bar (10-day) band, or a momentum sign flip
    costs      symmetric half-spread from the quoted column with zero prints
               floored at the non-zero median, plus $3.00/lot round turn
    gates      OOS |t| >= 2.96, retention >= 0.70, 2021-2026 t >= 2.00,
               directional symmetry, control Welch >= 2.00 AND net >= +0.05R

VOLATILITY SCALING IS NOT APPLIED TWICE. Sizing inversely to 20-day ATR and
reporting per unit of risk are the same operation. Everything is in R, where R
is the initial distance to the trailing band - a quantity that already scales
with volatility. Reporting vol-scaled returns in R as well would double-count.

RESULT - NO CELL PASSES. BEST IS 2 OF 5.

    pair     LB  exit     n    net R      t   win%   control  Welch   hold
    XAUUSD  480  band   200   +0.310  +1.46   31%    +0.003  +1.43   248
    XAUUSD  480  flip   935   +0.045  +1.28   28%    +0.007  +1.04     5
    XAUUSD 1200  band   124   +0.149  +0.84   31%    -0.010  +0.88   230
    XAUUSD 1200  flip   496   +0.051  +1.07   28%    -0.008  +1.23     5
    XAUUSD 2400  band    63   -0.050  -0.34   29%    +0.016  -0.42   285
    XAUUSD 2400  flip   322   -0.044  -1.64   22%    -0.007  -1.30     3
    USDJPY  480  band   206   -0.104  -1.13   29%    -0.008  -1.00   240
    USDJPY  480  flip   979   -0.011  -0.45   27%    -0.005  -0.23     4
    USDJPY 1200  band   135   -0.162  -1.17   24%    -0.058  -0.73   208
    USDJPY 1200  flip   585   -0.038  -1.85   28%    +0.002  -1.85     4
    USDJPY 2400  band    80   +0.748  +1.18   25%    +0.123  +0.97   238
    USDJPY 2400  flip   389   +0.066  +0.82   26%    +0.002  +0.79     5

THE BEST CELL CLEARS THE BETA CHARGE OUTRIGHT, WHICH IS RARE HERE

    XAUUSD 480 band, n=200, +0.310R
      G1  out-of-sample t +1.05 (n=40) against 2.96      FAIL
          retention +2.07                                PASS
      G2  2021-2026 t +1.12 (n=71, +0.518R)              FAIL
      G3  symmetry: long +0.194R, SHORT +0.431R          PASS
      G4  control Welch +1.43, net +0.310R               FAIL

Gold ran +322% across this sample and the SHORT leg outperforms the long one,
+0.431R against +0.194R. That is the cleanest beta acquittal in the programme:
whatever this is, it is not the gold bull market in costume. A stationary block
bootstrap gives P(mean <= 0) = 0.042 - significant standing alone, nowhere near
the 12-cell Bonferroni bar of 0.004.

AND ITS PROFIT RESTS ON ABOUT TEN TRADES

    cell                  n    mean   median   skew   top 5% share of profit
    XAUUSD 480 band     200  +0.310   -0.401  +6.11                    174%
    XAUUSD 1200 band    124  +0.149   -0.480  +4.05                    231%
    USDJPY 2400 band     80  +0.748   -0.458  +5.91                    136%

The median trade LOSES 0.40R and the top 5% contribute more than the whole
profit - remove the best ten of two hundred and the strategy is negative. This
is the accepted shape of a trend-following payoff rather than a defect, and it
is exactly why the t-statistic is the wrong instrument here. But it also means
the effective sample is nearer ten observations than two hundred, and no
choice of test statistic repairs that.

THE VALIDATION INSTRUMENT FAILS, AND ITS BEST CELL IS THE CARRY TRADE
USDJPY 2400 band posts the largest mean in the grid at +0.748R, and it is long
+1.825R against short -0.329R on a pair that went 84 to 154. Out-of-sample t is
-3.27 with retention -4.90: it earned early and lost recently. That is a carry
position with a momentum label, and the symmetry gate is what catches it.

A SPECIFICATION DEFECT: THE FLIP EXIT IS NOT A TREND EXIT

    band exit   median hold 208-285 bars   (8.7 to 11.9 days)
    flip exit   median hold 3-5 bars

Entry fires on a FRESH sign change, which places it at the zero crossing where
momentum is near zero and therefore flips back within a few bars. The flip exit
converts a multi-week thesis into a three-to-five bar scalp and quadruples the
trade count. Half the filed grid is not testing time-series momentum at all.
A usable version would need either a threshold on the momentum magnitude at
entry or a hysteresis band around the sign flip.

CANDIDATE 20 - THE CROSS-SECTIONAL PORTFOLIO. THE GOLD RESULT DOES NOT GENERALISE.

Identical LB480 trailing-band logic, no per-market tuning, across ten macro
instruments, 2009-2026, 2,135 trades.

    sym         n    net R      t   win%     long    short  control  Welch
    xauusd    200   +0.310  +1.46   31%   +0.194   +0.431   +0.057  +1.18
    xagusd    201   +0.212  +1.36   33%   +0.262   +0.144   +0.005  +1.29
    audusd    206   +0.281  +1.50   35%   +0.102   +0.512   -0.049  +1.74
    nzdusd    217   +0.070  +0.62   35%   +0.117   +0.024   -0.045  +0.99
    usdjpy    206   -0.104  -1.13   29%   -0.029   -0.176   +0.013  -1.23
    usdchf    213   -0.110  -1.39   31%   -0.124   -0.091   -0.019  -1.10
    usdcad    215   -0.115  -1.47   33%   -0.018   -0.226   -0.019  -1.18
    gbpusd    209   -0.136  -1.94   35%   -0.150   -0.124   -0.029  -1.47
    eurjpy    244   -0.224  -2.95   26%   -0.118   -0.324   -0.031  -2.44
    eurusd    224   -0.265  -3.54   29%   -0.413   -0.102   -0.045  -2.83

    POOLED    2135  -0.016R   naive t -0.41   month-clustered t +0.53
              control -0.017R   Welch +0.03   long -0.020R  short -0.012R

    G1 OOS clustered t -0.39 (n=427) vs 2.96          FAIL
    G1b retention +2.16                               passes, but on a
                                                      negative mean it means
                                                      nothing
    G2 2021-2026 clustered t -0.12 (-0.042R)          FAIL
    G3 symmetry: long -0.020R, short -0.012R          FAIL
    G4 Welch +0.03, net -0.016R                       FAIL

BREADTH DID NOT BUY POWER BECAUSE THERE WAS NO GENERAL EFFECT TO AMPLIFY

Effective breadth was measured before the run, not assumed. Six of the ten are
USD pairs and two more are USD-denominated metals; the top eigenvalue of the
daily-return correlation matrix explains 45% of variance, the first two explain
63%, mean absolute pairwise correlation is 0.39, and the eigenvalue-based N_eff
is 3.75. For a trend follower the SIGN of a correlation does not help - long
EURUSD and short USDCHF at rho -0.66 is one bet expressed twice.

    gold alone                                     t +1.46
    predicted pooled if the effect were general    t +2.83  (sqrt of N_eff)
    actual pooled                                  t -0.41

Four of ten are positive - gold, silver, AUD, NZD - and they are not four
independent successes: xauusd-xagusd correlate +0.78 and audusd-nzdusd +0.83.
Two coupled pairs. Six markets are negative, EURUSD at t -3.54 and EURJPY at
-2.95. Pooling only the four that worked gives +0.216R at t +2.54, but
selecting them is hindsight and that figure is not a gate result. With ten
markets and no true effect, four positive is unremarkable.

DIVERSIFICATION DID NOT DILUTE THE CONCENTRATION EITHER

    grouping        n     median     skew   sum of top 5%   sum of the rest
    gold alone    200    -0.401R    +6.11         +107.8R            -45.7R
    the four      824    -0.416R    +6.11         +339.7R           -161.9R
    all ten      2135    -0.466R    +6.79         +587.3R           -621.3R

In every grouping the top 5% of trades carries more than the entire profit and
the remaining 95% is negative. Breadth did not help, because the losing tail
scales with the trade count exactly as the winning tail does. The payoff shape
is intrinsic to a trailing-band trend rule, not an artefact of one market.

TWO OF MY OWN METRICS BROKE AND ARE CORRECTED HERE
"Top 5% share of profit" and "trades to reach 100% of profit" both divide by
total profit. Pooled profit is negative (-34.0R), so the first returned -1726%
and the second returned 0 of 2135. Those were the metric failing, not findings.
The scale-free version is the table above.

ONE PATTERN WORTH PRE-REGISTERING RATHER THAN CLAIMING
The four positives - gold, silver, AUD, NZD - are all commodity and risk-linked
assets, and the six negatives are all developed-market funding currencies. That
is a coherent economic grouping rather than a random split, and it is exactly
the kind of post-hoc pattern this programme has repeatedly refuted. It is
recorded as a hypothesis for a future pre-registration on instruments not used
here, not as a finding.

VERDICT: gated. Underpowered on XAUUSD, refuted on the validation instrument.
The gold band cells are the only place in this programme where a strategy has
beaten the beta charge with its short leg, and that is worth keeping. What it
cannot do is clear an out-of-sample bar on forty trades whose outcome is
decided by ten of them. Candidate 20 tested the obvious next step - more instruments - and it failed:
ten markets pooled to a NEGATIVE expectancy. What remains is a gold-and-silver
plus AUD-and-NZD result that no longer has an untested universe to be confirmed
on.
"""
from __future__ import annotations

from typing import Optional

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, Direction, SignalResult,
)

BAND = 240


class TSMomentumStrategy(BaseStrategy):
    """Time-series momentum with a trailing-band exit."""

    name = "tsmom"
    requires = (DataNeed.OHLC,)
    intervals = ("1h", "H1", "60m")
    validated_on = ()

    def __init__(self, lookback: int = 480, band: int = BAND,
                 require_validation: bool = True):
        super().__init__(lookback=lookback, band=band,
                         require_validation=require_validation)
        self.lookback = lookback
        self.band = band
        self.require_validation = require_validation

    def min_bars(self) -> int:
        return self.lookback + self.band + 2

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        if self.require_validation:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "TSMOM_UNDERPOWERED: 12 cells over XAUUSD and USDJPY H1, "
                "16-17 years. No cell passes; the best is 2 of 5. XAUUSD at a "
                "480-bar lookback with the trailing-band exit nets +0.310R on "
                "n=200 and passes directional symmetry with its SHORT leg "
                "ahead of its long (+0.431R vs +0.194R) across a +322% gold "
                "market - the cleanest beta acquittal in this programme - with "
                "retention +2.07 and a block-bootstrap P(mean<=0) of 0.042. It "
                "fails out-of-sample (t +1.05 on 40 trades against 2.96), the "
                "modern third (t +1.12) and the control (Welch +1.43). Its "
                "median trade loses 0.40R and the top 5% of trades carry 174% "
                "of the profit, so the effective sample is nearer ten than two "
                "hundred. The validation instrument fails outright: USDJPY's "
                "best cell is long +1.825R against short -0.329R with OOS t "
                "-3.27, which is the carry trade wearing a momentum label. "
                "Note also that the filed 'momentum flip' exit holds a median "
                "of 3-5 bars against the band exit's 208-285, because entry "
                "fires at the zero crossing where the sign is unstable - half "
                "the grid was not testing time-series momentum.")

        i = len(bars.close) - 1
        if i < self.min_bars():
            return SignalResult.abstain(
                self.name, bars.symbol,
                f"need {self.min_bars()} bars for a {self.lookback}-bar "
                f"lookback and a {self.band}-bar band")

        mom = bars.close[i] - bars.close[i - self.lookback]
        prev = bars.close[i - 1] - bars.close[i - 1 - self.lookback]
        evidence = {"momentum": mom, "lookback": self.lookback,
                    "band": self.band}
        if mom == 0:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol,
                direction=Direction.FLAT,
                reason="momentum is exactly flat", evidence=evidence)

        side = 1 if mom > 0 else -1
        fresh = (1 if prev > 0 else -1) != side
        band = (min(bars.low[i - self.band:i]) if side > 0
                else max(bars.high[i - self.band:i]))
        evidence["band_level"] = band
        evidence["fresh_signal"] = fresh

        if not fresh:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol,
                direction=Direction.FLAT,
                reason=(f"{self.lookback}-bar momentum is already "
                        f"{'positive' if side > 0 else 'negative'}; entries "
                        f"are taken on a fresh sign change only"),
                evidence=evidence)

        return SignalResult(
            strategy=self.name, symbol=bars.symbol,
            direction=Direction.LONG if side > 0 else Direction.SHORT,
            conviction=0.5,
            entry=None,           # fills at the next bar's open
            stop=band,            # the band trails; this is its initial level
            target=None,          # the exit is the trailing band, not a level
            reason=(f"{self.lookback}-bar momentum turned "
                    f"{'positive' if side > 0 else 'negative'}; trailing "
                    f"{self.band}-bar band at {band:.5f}"),
            evidence=evidence,
        )
