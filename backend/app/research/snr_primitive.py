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

================================================================================
ROUND 2 - THE THREE LEVEL TYPES THAT HAVE AN ACTUAL MECHANISM
================================================================================

The fractal pivots above are arbitrary. These three are not: resting stops
cluster beyond prior-day extremes, option strikes and human order placement sit
on round figures, and the fair value gap is the core SMC claim. Same machinery,
same controls, ~180,000 further observations.

ROUND NUMBERS - the cleanest test in the programme, and it fails

The level is EXOGENOUS: it is not derived from price, so there is no
circularity. The control is a grid of identical density offset off the round
figure - same spacing, same touch frequency, just not human-salient.

    pair     grid              n      mean       t   held%
    EURUSD   round (.00/.50) 9521   -0.0172   -0.66   49.7%
    EURUSD   offset control 10255   +0.0244   +0.94   49.8%
    GBPUSD   round          11635   +0.0286   +1.22   51.2%
    GBPUSD   offset control 12235   +0.0652   +2.81   51.0%
    XAUUSD   round          14996   +0.0017   +0.09   50.3%
    XAUUSD   offset control 16215   +0.0061   +0.31   50.4%

    round minus control:  EURUSD t -1.13   GBPUSD t -1.11   XAUUSD t -0.16

Round numbers are NEGATIVE against their own control on all three. And GBPUSD
is the object lesson: the round grid alone reads t +1.22 and looks promising,
while an ARBITRARY grid of the same density reads +2.81. Anyone testing round
numbers without the offset control would have reported a discovery.

PRIOR-DAY HIGH/LOW - the best of the three, and still not significant

Control is the high/low from five sessions back: an equally real extreme, but
stale, so it isolates recency rather than extremeness.

    pair     level              n      mean       t   held%
    EURUSD   prior day       3883   +0.0466   +0.98   52.7%
    EURUSD   5 days back     1958   -0.0658   -1.01   49.0%
    GBPUSD   prior day       3881   +0.0180   +0.40   51.0%
    GBPUSD   5 days back     1961   -0.0018   -0.03   49.1%
    XAUUSD   prior day       3828   -0.1050   -2.40   49.8%
    XAUUSD   5 days back     1899   -0.1088   -1.71   47.4%

    prior-day minus stale: EURUSD t +1.39   GBPUSD t +0.25   XAUUSD t +0.05

EURUSD holds 52.7% against 49.0% for the stale control - the highest hold rate
anywhere in this work - but at t +1.39 on the difference it does not clear, and
the other two instruments show nothing. Gold is significantly NEGATIVE on the
raw measure (t -2.40): price tends to carry through yesterday's extreme.

SMC FAIR VALUE GAP - the only primitive with a consistent sign

    pair     zone                 n      mean       t   held%
    EURUSD   FVG               9269   +0.0077   +0.27   49.8%
    EURUSD   displaced fake    8352   -0.0250   -0.83   49.2%
    GBPUSD   FVG               9099   +0.0245   +0.84   50.6%
    GBPUSD   displaced fake    8231   -0.0162   -0.54   49.4%
    XAUUSD   FVG               9544   +0.0410   +1.54   50.9%
    XAUUSD   displaced fake    8560   +0.0065   +0.22   50.3%

    FVG minus fake: +0.78, +0.97, +0.88 - positive on all three

    POOLED  FVG n=27912 mean +0.0246 ATR t +1.50   fake n=25143 t -0.67
            difference +0.0360 ATR at t +1.52, and because the three
            instruments correlate about 0.67 the effective t is nearer 1.24

This is the only level primitive whose sign is consistent across instruments.
It is also too small to trade:

    median EURUSD H1 ATR(14)   14.6 pips
    edge +0.0360 ATR         = +0.52 pips per touch
    round-trip toll            1.00 pips
    edge / toll                0.52x

VERDICT ON ALL FIVE PRIMITIVES
Fractal pivots: nothing, and worse than fakes on gold. Touch counts: flat.
Level flips: nothing. Round numbers: negative against an arbitrary grid of the
same density. Prior-day extremes: best raw hold rate seen (52.7% on EURUSD) and
still inside noise. Fair value gaps: consistent direction on three instruments
at roughly half the spread.

Across five primitives and about 330,000 observations, the only survivor points
the right way and is worth 0.52 of its own transaction cost. That is the same
scissors the programme-level power screen describes, reached from a completely
different direction - not through strategies, but through the raw inputs the
strategies were built from.

================================================================================
ROUND 3 - THE FULL BATTERY: 8 PRIMITIVES x 12 SYMBOLS
================================================================================

Expanding the symbol set changed the answer twice, which is the point of doing
it. Symbols: EURUSD GBPUSD AUDUSD NZDUSD USDCAD USDCHF USDJPY EURJPY EURGBP
XAUUSD XAGUSD WTI, H1, ~99k bars each.

THE MATRIX - t of (real minus its own control), 10-bar horizon

    primitive        +ve/12   pooled t        n
    prior_week_hl      8/12      +0.67    11,029
    asian_range        6/11      +0.52    68,665
    round_number       6/12      +0.16    95,201
    prior_day_hl       5/12      -1.09    84,561
    order_block        3/12      -1.14    17,356
    equal_highs        3/12      -1.94     9,037
    fractal_pivot      5/12      -2.46   105,710

Under the null, 8/12 has p = 0.194. Nothing here is distinguishable from chance,
and three primitives are significantly NEGATIVE pooled.

ACROSS ALL 95 CELLS
    mean t -0.203, median -0.178, sd 1.216
    cells |t| > 2: 10 of 95 against ~4 expected - and 9 of the 10 are NEGATIVE

The consistent negative tilt is the finding: price is marginally MORE likely to
continue through a level than through a matched control price. Every folklore
claim points the other way.

A REIMPLEMENTATION FAULT, CAUGHT BY THE EXPANSION

The battery's FVG used the gap MIDPOINT as a level and returned 6/12, pooled
-0.27, which appeared to kill the earlier 3/3 result. That was my error: the
pre-registered construction measures ZONE ENTRY - price entering anywhere in the
gap band - which is what SMC actually claims. The battery was not faithful to
the primitive it was re-testing.

FAIR VALUE GAP, CORRECT CONSTRUCTION, ALL 12 SYMBOLS

    symbol       n    real t   held%   fake t   diff t
    eurusd    9269    +0.27   49.8%    -0.83    +0.78
    gbpusd    9099    +0.84   50.6%    -0.54    +0.97
    audusd    9947    +1.13   49.9%    -1.00    +1.50
    nzdusd    9798    +1.26   50.7%    +0.62    +0.41
    usdcad    9357    -0.11   49.5%    -0.62    +0.37
    usdchf    8967    +1.03   50.7%    +0.67    +0.21
    usdjpy    9421    +1.33   51.2%    +0.63    +0.41
    eurjpy    9260    -0.15   50.6%    -1.07    +0.69
    eurgbp    8031    +1.40   50.1%    -1.80    +2.26
    xauusd    9544    +1.54   50.9%    +1.24    +0.14
    xagusd    8952    +2.93   50.9%    +1.54    +0.78
    wti       5363    +0.84   49.6%    +1.03    -0.15

    POSITIVE ON 11 OF 12    pooled diff-t +2.42
    binomial P(>= 11/12 | null) = 0.003

That is the strongest cross-sectional result in this programme. It is not a
single-instrument curiosity, it is not a pooling artefact, and it survives a
displaced-zone control on every instrument but one.

AND IT IS SMALLER THAN THE SPREAD ON ALL TWELVE

    symbol    edge ATR   edge px    toll px   edge/toll
    eurgbp     +0.0952   0.00009    0.00010      0.93x
    gbpusd     +0.0407   0.00008    0.00012      0.63x
    audusd     +0.0491   0.00006    0.00011      0.59x
    eurusd     +0.0327   0.00005    0.00010      0.48x
    eurjpy     +0.0255   0.00519    0.01304      0.40x
    usdcad     +0.0151   0.00002    0.00010      0.22x
    usdjpy     +0.0159   0.00237    0.01147      0.21x
    xagusd     +0.0308   0.00315    0.02060      0.15x
    nzdusd     +0.0136   0.00002    0.00014      0.12x
    xauusd     +0.0053   0.02009    0.21000      0.10x
    usdchf     +0.0086   0.00001    0.00012      0.09x
    wti        -0.0070  -0.00096    0.01300     -0.07x

    mean 0.32x    best 0.93x (EURGBP)    symbols above 1.0x: 0 of 12

VERDICT
The fair value gap is REAL and it is UNTRADEABLE at retail cost. Eleven of
twelve instruments agree at p = 0.003, and not one of them produces an effect
larger than its own round-trip friction. EURGBP comes closest at 0.93x - the
tightest spread relative to ATR in the set - and still loses.

This is the clearest single statement of the scissors the programme has
produced. It is not "there is no edge". It is "there is an edge, measured on
110,000 observations across twelve instruments, and it is worth about a third
of what it costs to collect". At institutional execution the same effect would
clear; at a retail CFD spread it cannot.

Every other primitive tested - fractal pivots, touch counts, level flips, round
numbers, prior-day and prior-week extremes, Asian session extremes, order
blocks, equal highs - shows nothing, and several are mildly anti-predictive.

"""
