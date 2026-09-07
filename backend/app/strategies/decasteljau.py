"""decasteljau: an 8-model curvature ensemble, tested on JPY H1.

MECHANISM AS FILED
Multi-scale Bezier curvature detects persistent trend regimes, which is the
complement of meanrev - the engine's prior note records +0.056R in TRENDING
against -0.120R in RANGING.

PRE-REGISTERED

    engine     InstitutionalEdge/core/decasteljau_engine.py v12.1
    primary    USDJPY H1, 99,000 bars, 2010-2026
    validation EURJPY H1, 99,000 bars, 2010-2026
    modes      conservative (quality 60, agreement 4, cooldown 10) and
               normal (quality 35, agreement 3, cooldown 6)
    exits      structural SL/TP on engine defaults, main target TP2
    costs      symmetric half-spread on entry and exit, $3.00/lot round turn
    gates      control Welch >= 2.00 AND net >= +0.05R; OOS clustered t >= 2.96
               with retention >= 0.70; 2021-2026 t >= 2.00; symmetry; transfer

THE FILED PRIOR OMITS ITS OWN SIGN
The engine's comment reads: "all signals -0.049R, quality>=60 -0.009R,
quality>=70 -0.167R". Quality 60 is the best measured cut and the best measured
cut is NEGATIVE. A null here confirms the engine's own record.

A LIVE PIP-SIZE DEFECT, FOUND BEFORE THE BACKTEST AND PATCHED DURING IT

_calc_sl_tp hardcoded pip_size = 0.0001 for every non-gold symbol. A JPY pip is
0.01, so max_sl_pips_fx (60 conservative, 80 normal) became a 0.006 cap on a
pair whose ATR is ~0.15. The cap crushed every stop and the atr*0.3 floor then
restored it, so EVERY JPY stop was exactly 0.30*ATR with reward-to-risk pinned
at 3.33 - independent of mode, of the structural swing level, and of
sl_mult_override. USDJPY was in the live watchlist and in the loop's fallback
list, so this traded.

Both conventions are therefore measured. `asfiled` is what ran live until the
patch; `pipfix` is the corrected specification, pip_size = 0.01.

RESULT - 0 OF 5 GATES ON ALL EIGHT CELLS, UNDER BOTH CONVENTIONS

    pair    mode          pips        n    net R      t   win%   ctrl   Welch
    USDJPY  conservative  asfiled  1165   -0.289  -5.59   21%  -0.367  +1.47
    USDJPY  conservative  pipfix    850   -0.024  -0.54   36%  -0.023  -0.03
    USDJPY  normal        asfiled  2716   -0.247  -5.91   16%  -0.300  +1.24
    USDJPY  normal        pipfix   1455   +0.020  +0.57   37%  -0.017  +1.05
    EURJPY  conservative  asfiled  1279   -0.312  -6.53   19%  -0.341  +0.58
    EURJPY  conservative  pipfix    941   +0.011  +0.24   37%  -0.027  +0.84
    EURJPY  normal        asfiled  2817   -0.198  -4.79   16%  -0.267  +1.63
    EURJPY  normal        pipfix   1573   +0.013  +0.38   37%  -0.025  +1.10

Best cell in the grid is +0.020R at t 0.57. Nothing clears anything.

WHAT THE BUG COST, MEASURED RATHER THAN ESTIMATED

    convention   median stop      rr   breakeven win   actual win      net
    asfiled       4.2-5.9 pips  3.33-5.00   16.7-23.1%   15.5-20.6%   -0.247R
    pipfix       45.8-62.6 pips      1.80        35.7%   35.9-37.4%   +0.008R

Under the bug the trade needed a 23.1% win rate and got 16-21%. Corrected it
needs 35.7% and gets 36-37%. The defect did not weaken an edge - it kept the
ATR-scaled target while shrinking the stop by an order of magnitude, pushing a
fair-odds trade below its own breakeven.

The exit mix says it plainly:

    asfiled   79-84% stopped, MEDIAN HOLD 1 BAR
    pipfix    62-64% stopped, median hold 19-22 bars

Under the bug the majority of positions were stopped out on their entry bar.
Aggregate: -1,967R across 7,977 trades against +39R across 4,819 corrected
ones, so the patch is worth +0.247R per trade. At 1% risk that is the whole
difference between an account that bleeds steadily and one that goes nowhere.

AND GOING NOWHERE IS WHERE IT GOES. The corrected cells net -0.024R to +0.020R
on 4,819 trades, with realised win rates 0.2 to 1.7 points from their
arithmetic breakeven in every cell. This is the third strategy in the programme
to land on exactly fair odds - after orb_london_0830, where four cells sat
within three points of breakeven, and CRT.

THE CONTROL GATE'S SHADOW ARTEFACT, FOR THE FOURTH TIME

Every asfiled cell posts a POSITIVE Welch (+0.58 to +1.63) while netting -0.198
to -0.312R, because the bias-matched control is equally destroyed by the same
4-pip stop. Welch read alone would have called the broken configuration the
better one. The amended gate - Welch >= 2.00 AND net >= +0.05R - rejects all
eight cells correctly, and this is the clearest vindication of that amendment
so far.

CARRY IS NOT LEAKING IN
USDJPY ran 84.20 to 154.49 (+83.5%) and EURJPY 113.16 to 179.64 (+58.8%) across
the sample. Under the corrected convention the long and short legs are
symmetric to within a tenth of an R (USDJPY normal: long +0.081R, short
-0.042R; EURJPY normal: long +0.005R, short +0.021R) and the matched control
sits at -0.017 to -0.027R. Whatever this is, it is not the carry trade wearing
a costume.

VERDICT: refuted on JPY H1. Eight cells, 12,796 trades, two instruments, two
modes and both pip conventions, and not one gate is cleared. The corrected
engine is not harmful - it is merely nothing, at fair odds, before slippage
beyond the modelled spread. The engine's own -0.009R at quality 60 is
reproduced and explained.

NOT TESTED HERE: M5, which is what the engine was written for. Every lookback
in it - linreg 20, lookback 50, swing 10, cooldown 10 - denominates in bars, so
on H1 they span 20 hours to 2 days rather than 100 minutes to 8 hours. This
result refutes decasteljau on H1 JPY. It does not refute the M5 scalping
configuration, which remains unmeasured on this data.
"""
from __future__ import annotations

from typing import Optional

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, Direction, SignalResult,
)


class DecasteljauStrategy(BaseStrategy):
    """Curvature-ensemble trend entries. Refuted on JPY H1."""

    name = "decasteljau"
    requires = (DataNeed.OHLC, DataNeed.SESSION_TIMES)
    intervals = ("1h", "H1", "60m")
    validated_on = ()

    def __init__(self, mode: str = "conservative",
                 require_validation: bool = True):
        super().__init__(mode=mode, require_validation=require_validation)
        self.mode = mode
        self.require_validation = require_validation

    def min_bars(self) -> int:
        return 300

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        if self.require_validation:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "DECASTELJAU_REFUTED_ON_JPY_H1: 12,796 trades over USDJPY and "
                "EURJPY H1, 2010-2026, two modes and both pip conventions. Zero "
                "of five gates on all eight cells; the best is +0.020R at "
                "t 0.57. Corrected for the pip-size defect the realised win "
                "rate sits 0.2 to 1.7 points from arithmetic breakeven in every "
                "cell - fair odds, no edge - which reproduces and explains the "
                "engine's own -0.009R at quality 60. Uncorrected it nets "
                "-0.247R per trade because a 0.30*ATR stop against an "
                "ATR-scaled target needs a 23.1% win rate and gets 16-21%, "
                "stopping out on the ENTRY BAR in the median case. Carry is not "
                "leaking in: long and short legs agree to within a tenth of an "
                "R across a sample where USDJPY ran +83.5%. Does NOT refute the "
                "M5 configuration the engine was written for, which is "
                "unmeasured here - every lookback denominates in bars and means "
                "something different on H1.")

        return SignalResult.abstain(
            self.name, bars.symbol,
            "decasteljau has no in-process implementation. The measured object "
            "is InstitutionalEdge/core/decasteljau_engine.py, an 8-model "
            "ensemble with stateful per-bar confirmation counters; it is "
            "evaluated out of process and is not reimplemented here. Porting it "
            "would create a second construction to keep in sync, which is how "
            "the RSI and ATR divergence in meanrev happened.")
