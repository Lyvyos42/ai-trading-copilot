"""vpa_smc: VPA/SMC confluence, tested unconditioned AND macro-conditioned.

This is the first candidate evaluated under the Tier 1 hierarchical directive,
and it is therefore also the first test OF that directive: does conditioning on
an exogenous macro regime rescue a technical pattern?

PRE-REGISTERED

    engine     InstitutionalEdge/core/vpa_smc.py via vpa_smc_adapter
    primary    EURUSD M15, 99,000 bars, 2022-09 to 2026-09
    validation GBPUSD M15, same window
    grid       crs_min [6, 7, 8]
    exits      the engine's own structural SL/TP - substituting a generic ATR
               stop would be testing a different strategy
    costs      symmetric half-spread, $3.00/lot round turn
    regime     Fed policy epochs. HIKING -> hawkish USD -> SHORT only;
               CUTTING -> dovish USD -> LONG only; HOLD -> no permission
    control    1,000-iteration circular block permutation of the epoch labels

THE REGIME IS A SUBSTITUTION, STATED PLAINLY
The directive specifies real rate differentials and net liquidity
(WALCL - TGA - RRP). Neither exists in either repository; the only macro
artefact anywhere is fomc_dates.csv, and fetching the rest needs a FRED key
that is not configured. Fed policy epochs are coarser but genuinely exogenous
and knowable on the day, because the Fed announces its own stance.

WINDOW. The engine's continuation loop is `for k in range(i + 1)`, so a full
pass is O(history) per bar. A fixed 600-bar window makes it O(600) - the same
asymptotic win as rewriting the swing track as a forward pass, without editing
984 lines of a live engine. Validated rather than assumed: on 119 bars that
fired at window 600, a 1500-bar window agrees on 119, for both pairs.

ARM 1 - UNCONDITIONED. NEGATIVE IN ALL SIX CELLS.

    pair    crs     n   net R      t   win%   control  Welch   long    short
    EURUSD    6   525  -0.171  -2.95   36%    -0.075  -1.62  -0.208  -0.136
    EURUSD    7   182  -0.112  -1.16   36%    -0.040  -0.73  -0.167  -0.066
    EURUSD    8   152  -0.155  -1.53   36%    -0.057  -0.94  -0.269  -0.059
    GBPUSD    6   532  -0.065  -0.96   37%    -0.059  -0.10  -0.030  -0.106
    GBPUSD    7   203  -0.068  -0.70   37%    -0.029  -0.40  -0.059  -0.077
    GBPUSD    8   167  -0.117  -1.12   35%    -0.046  -0.67  -0.183  -0.046

Welch is negative in every cell: it loses to a bias-matched random entry with
the same side, risk and target distance. Longs and shorts are both negative
everywhere, so symmetry fails independently of anything macro.

ARM 2 - MACRO-CONDITIONED. WORSE IN FIVE OF SIX.

    pair    crs   uncond R    cond n   cond R       t
    EURUSD    6     -0.171       158   -0.234   -2.31
    EURUSD    7     -0.112        58   -0.498   -3.45
    EURUSD    8     -0.155        51   -0.476   -3.02
    GBPUSD    6     -0.065       202   -0.025   -0.23
    GBPUSD    7     -0.068        78   -0.091   -0.60
    GBPUSD    8     -0.117        69   -0.256   -1.76

Only GBPUSD crs6 improves, from -0.065R to -0.025R, and it is still negative.

ARM 3 - THE PERMUTATION CONTROL, WHICH IS THE ACTUAL EXPERIMENT

    pair    crs   cond R   null mean   null p95        p
    EURUSD    6   -0.234      -0.181     -0.091    0.751
    EURUSD    7   -0.498      -0.143     +0.126    0.911
    EURUSD    8   -0.476      -0.209     +0.054    0.896
    GBPUSD    6   -0.025      -0.044     +0.096    0.399
    GBPUSD    7   -0.091      -0.069     +0.133    0.561
    GBPUSD    8   -0.256      -0.160     +0.090    0.536

Not one cell approaches significance, and in five of six the TRUE Fed-epoch
labelling does worse than the median random rotation of itself. The real macro
regime is not merely uninformative here - it is on the wrong side of chance.

WHAT THE NULL DISTRIBUTION SHOWS, AND WHY THE CONTROL IS NOT OPTIONAL

    pair    crs   P(null > 0)   P(null > +0.05R)   best random rotation
    EURUSD    6         0.0%               0.0%                 -0.055
    EURUSD    7        32.1%              23.3%                 +0.203
    EURUSD    8        17.7%               7.5%                 +0.071
    GBPUSD    6        32.7%              19.5%                 +0.128
    GBPUSD    7        32.8%              18.8%                 +0.172
    GBPUSD    8        33.5%              22.6%                 +0.131

A MEANINGLESS regime label - the real epoch sequence rotated to a random
offset, carrying no macro information whatsoever - produces a positive
conditioned expectancy about a third of the time, and clears +0.05R in one run
of five. The best random rotation reaches +0.203R on EURUSD crs7.

That is precisely the magnitude a macro-conditioning study reports as a
discovery. Any conditioned result presented without this null is
uninterpretable, because a third of arbitrary regime definitions beat zero on
this data by construction.

SCOPE - WHAT THIS DOES AND DOES NOT REFUTE
It refutes: vpa_smc on FX M15, unconditioned and under Fed-epoch conditioning,
and the specific proposal that macro conditioning would rescue it.

It does NOT refute macro conditioning in general. This test conditions a
strategy with no edge to condition, and no filter can turn nothing into
something - the arithmetic forbids it. A fair test of the Tier 1 thesis needs a
base signal with a measurable edge, which in this programme means meanrev H4
(+0.112R, era-stable, control-clearing) rather than another null pattern. What
this DOES establish is that the permutation control works and that the
degrees-of-freedom problem it was built to catch is large: a third of random
regimes look profitable.

ONE STRUCTURAL NOTE ON THE GRID
The adapter checks continuation breakout BEFORE the CRS confluence score, so
the crs_min threshold barely binds: continuation share is 21% at crs 6, 79% at
crs 7 and 99-100% at crs 8. Scanning crs_min is therefore close to scanning
"how much of the sample is the continuation rule", not "how much confluence is
required". A future grid should vary the two independently.

VERDICT: gated. Refuted on FX M15 unconditioned; macro conditioning makes it
worse and does not beat its own shuffle.
"""
from __future__ import annotations

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, SignalResult,
)


class VPASMCStrategy(BaseStrategy):
    """VPA/SMC confluence with structural levels. Refuted on FX M15."""

    name = "vpa_smc"
    requires = (DataNeed.OHLC,)
    intervals = ("15m", "M15")
    validated_on = ()

    def __init__(self, crs_min: int = 7, require_validation: bool = True):
        super().__init__(crs_min=crs_min, require_validation=require_validation)
        self.crs_min = crs_min
        self.require_validation = require_validation

    def min_bars(self) -> int:
        return 600

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        if self.require_validation:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "VPA_SMC_REFUTED: 1,761 trades over EURUSD and GBPUSD M15, "
                "2022-2026, six cells. Negative in all six unconditioned "
                "(-0.065 to -0.171R), with Welch negative in every one - it "
                "loses to a bias-matched random entry - and longs and shorts "
                "both negative throughout. Conditioning on Fed policy epochs "
                "makes it WORSE in five of six. Against a 1,000-iteration "
                "circular block permutation of the epoch labels, p ranges 0.399 "
                "to 0.911 and the true labelling does worse than the median "
                "random rotation in five of six cells. Note for any future "
                "conditioned study: a meaningless rotated regime produces "
                "positive conditioned expectancy ~33% of the time here and "
                "reaches +0.203R at best, so a conditioned result without this "
                "null is uninterpretable. Scope: this conditions a strategy "
                "with no edge, and no filter turns nothing into something - it "
                "does not refute Tier 1 conditioning in general.")

        return SignalResult.abstain(
            self.name, bars.symbol,
            "vpa_smc has no in-process implementation. The measured object is "
            "InstitutionalEdge/core/vpa_smc.py via its adapter, evaluated out "
            "of process with the engine's own structural SL/TP. Note that the "
            "adapter tests continuation breakout BEFORE the CRS score, so "
            "crs_min binds far less than it appears to.")
