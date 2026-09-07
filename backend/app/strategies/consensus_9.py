"""consensus_9: a nine-agent quorum, tested on EURUSD and GBPUSD M15.

PRE-REGISTERED

    engine     InstitutionalEdge/core/research_strategies/consensus_9.py
    primary    EURUSD M15, 99,000 bars, 2022-09 to 2026-09
    validation GBPUSD M15, same window
    grid       min_conviction [0.55, 0.62] x min_votes [2, 3]
               x hold [48, 96] x exit [time, levels]  = 32 cells
    stride     4 (the consensus is recomputed hourly and held between)
    costs      symmetric half-spread, $3.00/lot round turn
    gates      control Welch >= 2.00 AND net >= +0.05R; OOS clustered t >= 2.96
               with retention >= 0.70; 2025-2026 t >= 2.00; symmetry; transfer

PRIOR: the 2026-09-05 matrix scan found EURUSD hold 48 at net t +2.00, the best
of 16 cells, and it was moved to forward-testing on that basis.

RESULT - REFUTED. EVERY TESTABLE CELL IS NEGATIVE.

    pair    conv  v  hold exit       n    net R      t   win%   ctrl   Welch
    EURUSD  0.55  2    48 time    2027   -0.177  -3.02   18%  -0.110  -1.13
    EURUSD  0.55  2    48 levels  3046   -0.142  -5.76   32%  -0.139  -0.11
    EURUSD  0.55  2    96 time    1550   -0.174  -2.21   13%  -0.095  -1.00
    EURUSD  0.55  2    96 levels  2991   -0.135  -5.36   32%  -0.124  -0.43
    EURUSD  0.62  2    48 time    1729   -0.255  -4.29   17%  -0.109  -2.41
    EURUSD  0.62  2    48 levels  2476   -0.175  -6.15   32%  -0.131  -1.53
    EURUSD  0.62  2    96 time    1375   -0.268  -3.26   11%  -0.125  -1.72
    EURUSD  0.62  2    96 levels  2449   -0.168  -5.83   32%  -0.136  -1.10
    GBPUSD  0.55  2    48 time    2103   -0.159  -2.85   17%  -0.132  -0.49
    GBPUSD  0.55  2    48 levels  3150   -0.166  -6.90   32%  -0.127  -1.59
    GBPUSD  0.55  2    96 time    1604   -0.144  -1.95   13%  -0.129  -0.21
    GBPUSD  0.55  2    96 levels  3105   -0.169  -6.94   31%  -0.130  -1.59
    GBPUSD  0.62  2    48 time    1798   -0.153  -2.46   16%  -0.124  -0.46
    GBPUSD  0.62  2    48 levels  2573   -0.177  -6.67   31%  -0.125  -1.93
    GBPUSD  0.62  2    96 time    1425   -0.188  -2.37   12%  -0.115  -0.91
    GBPUSD  0.62  2    96 levels  2541   -0.180  -6.72   31%  -0.120  -2.19

Sixteen cells, 34,000 trades, both pairs, every one negative, reaching t -6.94.
Longs and shorts are negative in all sixteen, so symmetry fails everywhere. The
best cell is -0.135R.

THE +2.00 PRIOR IS NOT A COST ARTEFACT
Re-run with zero spread and zero commission on the same entries:

    EURUSD 48 time    gross -0.067R  t -1.09      GBPUSD 48 time    -0.047R  t -0.81
    EURUSD 48 levels  gross -0.037R  t -1.48      GBPUSD 48 levels  -0.056R  t -2.30
    EURUSD 96 time    gross -0.068R  t -0.84      GBPUSD 96 time    -0.037R  t -0.48
    EURUSD 96 levels  gross -0.032R  t -1.25      GBPUSD 96 levels  -0.060R  t -2.40

Gross is negative in all eight. The toll is a uniform 0.11R on top, but it is
not what killed this - there was nothing to kill. The earlier +2.00 was the
best of sixteen cells against a Bonferroni bar of 2.96 and does not survive
full-depth data with the engine's own value-area levels.

Nor does inverting it help: flipping the sign gives +0.067R gross against the
same 0.111R toll, which is -0.044R net. A negative gross this small is not
tradeable in either direction.

HALF THE FILED GRID WAS NEVER TESTABLE

    min_votes = 2   EURUSD 6,202 signals    GBPUSD 6,234
    min_votes = 3   EURUSD    47 signals    GBPUSD    30

Sixteen of the 32 filed cells produce 2 to 47 trades and cannot be evaluated.
The reason is structural: only four specialists ever vote directionally.
correlation, macro and sentiment return NEUTRAL on every bar, so they can never
be concordant with anything, and requiring three concordant votes from an
effective roster of four empties the cell.

THAT IS THE SAME FACT AS THE symbol= EQUIVALENCE

The brief specifies passing symbol= so the instrument-dependent specialists
participate. They do participate - and they contribute nothing, because
correlation, macro and sentiment read LIVE news and calendar state and never
the bar timestamp. Called on bars from 2022, 2023, 2024, 2025 and 2026 they
return byte-identical votes, the ones true on the day the scan was run.

Measured rather than assumed: across 400 dispersed bars per pair and all four
threshold combinations, symbol='EURUSD' and symbol=None disagree on 0 of 1,600
decisions. Same for GBPUSD. Zero of 3,200.

The symbol= arm costs 123 ms per call against 12 ms - 51 minutes per pair
against 5 - for provably identical output, the overhead being a Forex Factory
scrape that returns 403 on every call. It was therefore run with symbol=None,
having first demonstrated the equivalence rather than presuming it.

This is a BACKTEST validity problem, not a live defect. Live, those agents read
current news for the current bar, which is correct. What cannot be done is
carry that reading backwards over four years and call the result a nine-agent
test. Any historical figure for this engine is a four-specialist figure.

THE CONVICTION FLOOR IS ANTI-PREDICTIVE

    pair    hold exit     conv 0.55  conv 0.62    delta
    EURUSD    48 time        -0.177     -0.255   -0.078
    EURUSD    48 levels      -0.142     -0.175   -0.033
    EURUSD    96 time        -0.174     -0.268   -0.093
    EURUSD    96 levels      -0.135     -0.168   -0.034
    GBPUSD    48 time        -0.159     -0.153   +0.006
    GBPUSD    48 levels      -0.166     -0.177   -0.011
    GBPUSD    96 time        -0.144     -0.188   -0.043
    GBPUSD    96 levels      -0.169     -0.180   -0.011

Raising the conviction floor makes it worse in 7 of 8 cells. This is the second
engine here to show it: decasteljau measured quality>=70 at -0.167R against
quality>=60 at -0.009R. Both engines' internal confidence scores are negatively
related to realised return at the top of their range, which is worth more than
either strategy result - a confidence score that inverts is worse than no score,
because it is used to size.

THE CONTROL GATE, READ THE OTHER WAY
Welch is negative or negligible in all sixteen cells, reaching -2.41. This is
the opposite of the shadow artefact seen in artemis_squeeze, CRT, orb_london
and decasteljau: consensus_9 does not merely fail to beat a bias-matched random
entry with the same side, risk and hold - it loses to one, significantly, in
several cells.

A HARNESS TRAP WORTH RECORDING
The frame must be lowercase ohlcv WITH a 'Date' COLUMN. Passing a DatetimeIndex
instead - the natural reading - makes technical compute RSI as nan and vote
SHORT at 0.90 CONFIDENCE, while quant, order_flow and regime abstain on a
swallowed ValueError. The wrong format does not fail loudly; it produces one
confident vote built on a NaN comparison and three silent abstentions, and the
quorum is then decided by that one vote. Any prior scan of this engine should
be checked for which frame it passed.

VERDICT: refuted on FX M15. Sixteen testable cells, 34,000 trades, two pairs,
negative in every one before and after costs, losing to its own random control,
with a conviction score that runs backwards.
"""
from __future__ import annotations

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, SignalResult,
)


class Consensus9Strategy(BaseStrategy):
    """Nine-agent quorum. Refuted on FX M15."""

    name = "consensus_9"
    requires = (DataNeed.OHLC,)
    intervals = ("15m", "M15")
    validated_on = ()

    def __init__(self, min_conviction: float = 0.55, min_votes: int = 2,
                 require_validation: bool = True):
        super().__init__(min_conviction=min_conviction, min_votes=min_votes,
                         require_validation=require_validation)
        self.min_conviction = min_conviction
        self.min_votes = min_votes
        self.require_validation = require_validation

    def min_bars(self) -> int:
        return 400

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        if self.require_validation:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "CONSENSUS_9_REFUTED: 34,000 trades over EURUSD and GBPUSD M15, "
                "2022-2026. All 16 testable cells negative, to t -6.94, with "
                "longs and shorts negative in every one. Gross expectancy - "
                "zero spread, zero commission - is ALSO negative in all eight "
                "checked (-0.032 to -0.068R), so the filed +2.00 prior is not a "
                "cost artefact; it was the best of 16 cells against a 2.96 bar "
                "and does not reproduce at full depth. Welch against a "
                "bias-matched control is negative in every cell, to -2.41: it "
                "loses to a random entry with the same side, risk and hold. "
                "Raising min_conviction from 0.55 to 0.62 makes it WORSE in 7 "
                "of 8 cells - the second engine here whose own confidence score "
                "runs backwards, after decasteljau. Half the filed grid was "
                "never testable: min_votes=3 yields 30-47 signals against "
                "6,200, because correlation, macro and sentiment vote NEUTRAL "
                "on every bar and three concordant votes cannot be had from an "
                "effective roster of four. Those same three agents read live "
                "news and calendar state rather than the bar timestamp, so "
                "symbol= and symbol=None disagree on 0 of 3,200 decisions - any "
                "historical figure for this engine is a four-specialist figure.")

        return SignalResult.abstain(
            self.name, bars.symbol,
            "consensus_9 has no in-process implementation. The measured object "
            "is InstitutionalEdge/core/agents/, evaluated out of process. Note "
            "for any future harness: the frame must be lowercase ohlcv WITH a "
            "'Date' column - a DatetimeIndex makes the technical agent vote "
            "SHORT at 0.90 confidence on a NaN RSI while three specialists "
            "abstain on a swallowed ValueError.")
