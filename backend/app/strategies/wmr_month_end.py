"""wmr_month_end: London 16:00 WMR month-end equity-rebalancing flow.

MECHANISM (Melvin & Prins 2015; Evans 2018)
Managers holding US equities and hedging back to base currency must resize the
hedge at month-end. US equities up over the month leaves them under-hedged, so
they sell USD into the 16:00 London WMR fix. Predicted sign: beta > 0.

PRE-REGISTERED
    primary     GBPUSD H1, validation EURUSD H1, 2010-2026
    window      15:00-16:00 London = server hour 17. Athens leads London by a
                constant 2.0h - both follow EU DST - so this mapping is exact
                year-round, verified on all 4,137 London-15:00 bars.
    predictor   monthly SPY return, CAUSAL: close(last day M-1) to OPEN(last
                day M). The fix is 11:00 ET, five hours before the US close, so
                a close-based predictor is lookahead and is an upper bound only.
    costs       measured fix-hour toll: GBPUSD 1.30 pips, EURUSD 1.00 pips
    power       filed in advance: sigma 15.5 pips, N=192 detects r >= 0.120 at
                t 1.65. First candidate here with an a priori power calculation.

RESULT - THE MECHANISM IS REAL. THE TRADE IS NOT.

Independently replicated. My figures, collaborating scan in brackets:

    GBPUSD fix hour        beta +192.6  t +3.31  r +0.249   [+228.5  +4.02]
    EURUSD fix hour        beta  -18.7  t -0.41  r -0.032   [  +8.8  +0.20]
    pre-fix 14:00 London   beta  +51.1  t +1.19             [ +41.2  +0.98]
    post-fix 16:00 London  beta  -71.1  t -1.84             [ -76.0  -2.04]
    non-month-end placebo  beta  +52.4  t +6.22  n=3970     [ +47.3  +5.49]
    Era 2 (2016-2026)      beta +238.4  t +3.32  r +0.303   [+268.9  +3.92]

The spatial signature is the strongest evidence in the programme: the slope
rises about 3.8x into the fix and INVERTS immediately after, against an ambient
non-month-end beta of +52. That surge-and-invert is hard to produce by chance
and is the shape a non-discretionary flow exhausting at a benchmark should
make. EURUSD is flat on both scans, consistent with Euro-area funds
benchmarking to the ECB 14:15 CET fix rather than London 16:00.

THE RESULT IS CARRIED BY ABOUT TEN MONTHS

    full sample                 beta +192.6  t +3.31  r +0.249
    drop 1 largest |SPY|             +158.2     +2.70    +0.206
    drop 3                           +134.6     +2.19    +0.170
    drop 5                           +132.6     +2.06    +0.161
    drop 10 (6% of sample)            +76.2     +1.10    +0.088
    Spearman rank                          -     +2.26    +0.173

Of the five most extreme SPY months, 2020-11 has the WRONG SIGN (-19.8 pips on
+11.1% SPY) and 2020-03 is flat. The rank correlation survives at t +2.26, so
the relationship is real on ordinal evidence - but Pearson is magnified by two
months, 2020-04 (+108 pips) and 2011-10 (+91 pips).

THE TRADEABLE CLAIM FAILS ITS OWN HURDLE

    sign strategy, full     +2.98 pips net   t +1.17   win 56.3%
    Era 1 (2010-2015)       -1.13 pips       t -0.32
    Era 2 (2016-2026)       +5.06 pips       t +1.50

Against a pre-registered 1.65. The 1.30-pip toll is about 40% of the effect.

VERDICT: OBSERVER on GBPUSD, EURUSD permanently gated. The mechanism is
established; the execution is not. The promotion contract is outlier-proof by
design - a positive MEDIAN net and a positive Spearman correlation over 24
forward month-ends, criteria a single COVID-scale print cannot buy.

Sample note: 167 strict month-ends with UK bank-holiday roll-backs applied,
against 191 on raw calendar matching. Both give the same structural result.

PORTFOLIO NOTE
Combined equal-risk with meanrev EURUSD H4 and tsmom XAUUSD H1, the three are
effectively uncorrelated (mean |rho| 0.053, every pair inside one standard
error of zero) and the portfolio reaches t +2.76 at an annualised Sharpe of
0.69 - the first figure in this programme to clear anything. That is in-sample
and inherits the selection of all three components rather than escaping it.
See the registry entry for the drawdown profile and what it implies.
"""
from __future__ import annotations

from app.strategies.base import BarSeries, BaseStrategy, DataNeed, SignalResult


class WMRMonthEndStrategy(BaseStrategy):
    """Month-end London fix rebalancing flow. Observer on GBPUSD."""

    name = "wmr_month_end"
    requires = (DataNeed.OHLC, DataNeed.SESSION_TIMES)
    intervals = ("1h", "H1", "60m", "15m", "M15")
    validated_on = ()

    def min_bars(self) -> int:
        return 48

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        return SignalResult.abstain(
            self.name, bars.symbol,
            "WMR_MONTH_END_OBSERVER: mechanism established on GBPUSD, "
            "execution not. Fix-hour beta +192.6 (t +3.31, r +0.249) on 167 "
            "strict month-ends, the slope rising about 3.8x into the 16:00 "
            "London fix and INVERTING after (t -1.84) against an ambient "
            "non-month-end beta of +52 on n=3,970. EURUSD is flat (t -0.41), "
            "consistent with Euro-area funds using the ECB 14:15 CET fix. But "
            "the result is carried by about 10 months: dropping the 10 largest "
            "|SPY| observations takes t from +3.31 to +1.10, one of the five "
            "most extreme months has the wrong sign, and Spearman is +0.173 "
            "(t +2.26) against Pearson +0.249. The sign strategy nets +2.98 "
            "pips at t +1.17 against a pre-registered 1.65, Era 1 is NEGATIVE "
            "(-1.13 pips), and the 1.30-pip toll is about 40% of the effect. "
            "No in-process signal: the predictor is a monthly SPY return, "
            "evaluated out of process at month-end.")
