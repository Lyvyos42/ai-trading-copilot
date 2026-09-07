"""Do support/resistance levels carry information? Measured, not assumed.

WHY THIS IS NOT ANOTHER CANDIDATE
S/R is a PRIMITIVE that several refuted strategies were built on: crt (sweep a
level and fade), donchian_fail (break a level and fade), vp_auction (value-area
edges), orb and orb_london_0830 (range boundaries). If levels carry no forward
information, that is one root cause behind four separate refutations, and it is
cheaper to test the primitive once than the strategies one at a time.

DETECTION IS NOT THE PROBLEM
InstitutionalEdge/core/decasteljau_engine.py::_snr_check already detects levels
competently - causal fractal pivots, merged into ATR-scaled zones, with touch
counts and expiry. Nothing is wrong with it. The question is whether what it
finds predicts anything.

THE TRAP THIS TEST AVOIDS
A pivot high IS a local maximum by construction. Price reversed there - that is
what made it a pivot. Measuring reversals over the window that created the level
is circular and always confirms. So levels are built causally, and every
measurement is taken on a touch at least 20 bars AFTER the pivot that formed it.

THE CONTROL
Sitting at a particular price is not neutral. Each real level is matched with a
FAKE level on the same instrument and bar, displaced 1-3 ATR, preserving the
distance-from-price geometry but placed where no pivot exists.

CLAIM 1 - "price reverses at S/R more often than at an arbitrary price"

Signed so positive means the level HELD. Horizons in ATR units.

    pair     set       n       r5 t   hold%      r10 t   hold%      r20 t   hold%
    eurusd   real  10289    +0.13    50.4%      -0.29    50.6%      -0.74    49.9%
    eurusd   fake  10077    -0.52    49.8%      -0.02    50.1%      -0.31    50.0%
    gbpusd   real  10220    -0.67    49.3%      -0.14    49.6%      -0.28    49.4%
    gbpusd   fake   9925    -0.15    49.4%      -0.12    49.0%      +0.29    50.0%
    xauusd   real  10048    -2.08    49.6%      -2.81    49.3%      -1.94    50.0%
    xauusd   fake   9811    +0.85    50.4%      +0.24    50.1%      -0.23    50.2%

    real minus fake:  eurusd +0.46 / -0.19 / -0.31
                      gbpusd -0.37 / -0.01 / -0.41
                      xauusd -2.08 / -2.17 / -1.22

Every hold rate sits between 49.3% and 50.6%. On EURUSD and GBPUSD real levels
are indistinguishable from displaced fakes. On XAUUSD real levels are
SIGNIFICANTLY WORSE than fakes - price is slightly more likely to continue
through a genuine pivot than through an arbitrary price at the same distance.

CLAIM 2 - "more touches make a level stronger"

Hold rate by touch number, 10-bar horizon:

    pair       t1      t2      t3      t4      t5      t6
    eurusd   50.6%   50.6%   49.8%   49.8%   49.4%   49.3%
    gbpusd   49.6%   49.3%   49.7%   50.2%   50.4%   49.9%
    xauusd   49.3%   48.6%   49.7%   49.9%   49.1%   50.2%

Flat. n runs 7,688 to 10,289 per cell, so this is not a power problem: a level
touched six times holds no better than one touched once.

CLAIM 3 - "a broken level flips: old resistance becomes support"

    pair          n     mean       t   holds%
    eurusd     8915  +0.0234   +0.79    49.6%
    gbpusd     8867  -0.0158   -0.55    50.5%
    xauusd     8509  +0.0286   +1.03    50.1%

Nothing.

VERDICT
Across roughly 150,000 touch observations on three instruments and sixteen
years, horizontal S/R levels carry no measurable forward information. All three
folklore claims fail, and the strongest single result is that real levels are
WORSE than random ones on gold.

This is the best-powered test in the programme - n per cell is 10,000 rather
than the 167 that the event studies had - which is the power screen's own point:
questions asked at high observation frequency can actually be answered.

SCOPE, STATED SO IT IS NOT OVER-READ
Tested: horizontal fractal-pivot levels on H1, 0.25-ATR zones, 5-bar pivots,
500-bar expiry, on EURUSD, GBPUSD and XAUUSD.
NOT tested: session levels (prior-day high/low, overnight range), round numbers,
volume-profile nodes, trendlines, or levels on other timeframes.

One caveat worth keeping: zero UNCONDITIONAL information does not strictly
prove zero CONDITIONAL information - a level could matter only in some regime.
But a variable this flat is a poor candidate for a conditional effect, and the
strategies built on it have already been refuted independently.
"""
