"""artemis_squeeze: Bollinger bands pinched inside Keltner, traded on release.

The standard TTM/LazyBear construction:

    BB       SMA(20) +/- 2.0 * stdev(20)
    KC       EMA(20) +/- 1.5 * ATR(20)
    squeeze  ON while the Bollinger bands sit entirely inside the Keltner
    momentum linear-regression slope over 20 of
             close - mean( mean(highest(20), lowest(20)), SMA(close,20) )

PRE-REGISTERED - primary XAUUSD H1, validation XAGUSD H1, 99,000 bars each,
2009-10 to 2026-09.

    setup    the squeeze has been ON for >= `pinch` bars and is OFF this bar
    side     the sign of the momentum slope over the preceding 3 bars
    entry    the next bar's open
    stop     2.0 x ATR(20)
    exits    momentum crossing its own 6-bar signal line, or a 2.0-ATR trail
    screens  no entries within an hour of the 00:00 Athens rollover, no bars
             with spread above 2.0x the median
    gates    OOS |t| >= 3.21 (Bonferroni, 30 cells), retention >= 0.70,
             modern third |t| >= 2.00 with positive mean, directional
             symmetry, and a bias-matched control at Welch >= 2.00

ACCOUNTING IS SYMMETRIC, per the correction adopted after CRT: long enters at
Open + spread/2 and exits at price - spread/2, short the mirror. Each side pays
exactly one round turn and neither is handicapped when symmetry is the test.

TWO SPECIFICATION FAULTS FOUND BEFORE THE GRID WAS RUN

First, the filed threshold |slope| > 5.0 is an ABSOLUTE bound on a quantity
that scales with price. It fires on 0.1% of gold bars and 0.0% of silver bars -
the study would have returned almost nothing on the primary and literally
nothing on the validation symbol, and that would have read as "no setups
qualified" rather than as a broken threshold. Normalised by ATR the two
distributions coincide almost exactly (p90: gold 0.165, silver 0.163), which is
the evidence that the normalisation is the right one rather than a convenience.

Second, calibrating that threshold on ALL bars is still wrong. A squeeze
release is by construction a low-volatility moment, so the release-bar slope
distribution sits well below the all-bar distribution: |slope|/ATR > 0.10 cuts
973 gold releases to 47. Recalibrated on release bars, 0.05 retains ~40%.

AN UNRECONCILED EVENT-COUNT DISCREPANCY, RECORDED RATHER THAN SMOOTHED

This construction finds 973 releases on gold at pinch >= 6 and 388 at pinch >=
12, against 2,316 and 1,578 reported by the collaborating scan. That is a 2.4x
to 4.1x gap, and the shape of it - proportionally larger at the longer pinch -
points at a looser Keltner multiplier producing longer squeeze episodes. 15.6%
of gold bars are in squeeze under BB(20,2.0)/KC(20,1.5). The verdict below is
on the construction stated above; if the other scan used a different KC
multiplier it is testing a different object and this result does not transfer.

RESULT - NO CELL PASSES ALL FOUR GATES. 30 cells, two metals.

The best gold cell, and the only one to pass three gates:

    XAUUSD  pinch 12, ADX > 20, mom_cross     n=91   +0.231R   t +1.67
      G1  out-of-sample t +1.96 vs 3.21          FAIL   (n=19)
          retention +4.51 vs 0.70                PASS
      G2  modern third t +2.15 vs 2.00           PASS   (n=31)
      G3  symmetry  long +0.202R  short +0.256R  PASS
      G4  control Welch +1.51 vs 2.00            FAIL   (control +0.013R)

It fails on the two gates written to catch exactly this: 91 trades with 19 out
of sample, and no separation from a random entry carrying the same side, the
same risk and the same hold. Note also that retention of +4.51 is not a
robustness signal - it is the small-sample artefact this programme has now seen
three times, an out-of-sample Sharpe divided by a smaller in-sample one.

THE TWO CELLS THAT DO CLEAR THE CONTROL ARE THE MOST INSTRUCTIVE FAILURE

    XAGUSD  pinch 6,  no ADX, mom_cross   n=995  -0.003R  Welch +2.80
    XAGUSD  pinch 12, no ADX, mom_cross   n=477  -0.001R  Welch +2.24

Both clear the control gate, and both have zero expectancy. They clear it
because the control loses -0.111R and -0.125R, not because the strategy earns
anything. This is the CRT finding restated: on an instrument where a random
entry with a 2-ATR stop bleeds steadily, "beats its own shadow" and "makes
money" come apart completely. A control gate is a necessary condition and never
a sufficient one; reading Welch without reading the level would have promoted a
strategy netting minus three ten-thousandths of an R.

THE ATR TRAIL IS UNIFORMLY DESTRUCTIVE, AND THAT IS A REAL FINDING

Every one of the 15 atr_trail cells is negative, reaching t -8.82 on silver at
n=973, against mom_cross which is near zero or positive in almost all of its
cells on the same events. The two exit modes see the SAME entries, so this is a
clean comparison: a 2-ATR trailing stop on an H1 metal ratchets into noise and
converts flat trades into losses. The squeeze release does produce expansion;
it does not produce persistent directional expansion that a trail can hold.

WHAT SURVIVES

Gold is directionally symmetric in every cell with enough trades to say so
(long share 45-58%), so nothing here is the +141% gold drift wearing a costume.
And the ADX conditioner does what it claims: on gold at pinch 12 it lifts the
mean from +0.092R to +0.231R. Both are honest observations about the mechanism.
Neither survives the trade count. 91 trades is 17 years of gold H1 producing
five and a half events a year.

VERDICT: gated. Underpowered rather than refuted on gold; refuted on silver.
The mechanism is not demonstrated to differ from a random entry with matched
geometry. Promotion would need the event-count discrepancy resolved first,
since a looser Keltner yielding 2,316 events is a materially different test
with the power this one lacks.
"""
from __future__ import annotations

from typing import Optional

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, Direction, SignalResult,
)

BB_N, BB_K = 20, 2.0
KC_N, KC_K = 20, 1.5
MOM_N = 20
SLOPE_LOOKBACK = 3
STOP_ATR = 2.0


class ArtemisSqueezeStrategy(BaseStrategy):
    """Trade the release of a Bollinger-inside-Keltner volatility squeeze."""

    name = "artemis_squeeze"
    requires = (DataNeed.OHLC,)
    intervals = ("1h", "H1", "60m")
    validated_on = ()

    def __init__(self, pinch: int = 12, adx_min: Optional[float] = 20.0,
                 slope_min: float = 0.05, require_validation: bool = True):
        super().__init__(pinch=pinch, adx_min=adx_min, slope_min=slope_min,
                         require_validation=require_validation)
        self.pinch = pinch
        self.adx_min = adx_min
        self.slope_min = slope_min
        self.require_validation = require_validation

    def min_bars(self) -> int:
        return max(60, self.pinch + MOM_N * 2)

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        if self.require_validation:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "ARTEMIS_SQUEEZE_UNDERPOWERED: 30 cells across XAUUSD and "
                "XAGUSD H1, 99k bars each. No cell passes all four gates. The "
                "best gold cell nets +0.231R at t 1.67 on n=91 - 19 trades out "
                "of sample against a required |t| of 3.21 - and reaches only "
                "Welch +1.51 against a bias-matched random entry. The two cells "
                "that DO clear the control at Welch 2.80 and 2.24 are silver "
                "cells netting -0.003R and -0.001R: they beat a control that "
                "loses -0.11R, which is not an edge. Every atr_trail cell is "
                "negative, to t -8.82. Also unresolved: this BB(20,2.0)/"
                "KC(20,1.5) construction finds 973 gold releases at pinch 6 "
                "against 2,316 reported elsewhere, so the channel parameters "
                "under test differ.")

        i = len(bars.close) - 1
        atr_series = self.atr(bars.high, bars.low, bars.close, KC_N)
        atr = atr_series[i]
        if atr is None or atr <= 0:
            return SignalResult.abstain(self.name, bars.symbol, "ATR unavailable")

        sq = self._squeeze_series(bars, atr_series)
        mom = self._momentum(bars)
        if sq is None or mom is None:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "insufficient bars for the BB/KC channels or the momentum slope")
        if mom[i] is None or mom[i - SLOPE_LOOKBACK] is None:
            return SignalResult.abstain(
                self.name, bars.symbol, "momentum series incomplete")

        slope = (mom[i] - mom[i - SLOPE_LOOKBACK]) / atr
        evidence = {"in_squeeze": bool(sq[i]), "pinch_required": self.pinch,
                    "slope_per_atr": slope, "atr": atr}

        released = (not sq[i]) and all(sq[i - self.pinch:i])
        if not released:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=("no release: the squeeze is on" if sq[i] else
                        f"the squeeze has not been on for {self.pinch} bars"),
                evidence=evidence)

        if abs(slope) < self.slope_min:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=(f"released, but |slope|/ATR {abs(slope):.3f} is under "
                        f"{self.slope_min:.3f} - no direction to take"),
                evidence=evidence)

        side = 1 if slope > 0 else -1
        close = bars.close[i]
        return SignalResult(
            strategy=self.name, symbol=bars.symbol,
            direction=Direction.LONG if side > 0 else Direction.SHORT,
            conviction=0.5,
            entry=None,          # fills at the next bar's open, not at a level
            stop=close - side * STOP_ATR * atr,
            target=None,         # exits on the momentum cross, not a level
            reason=(f"squeeze released after {self.pinch}+ bars with momentum "
                    f"slope {slope:+.3f} ATR"),
            evidence=evidence,
        )

    def _squeeze_series(self, bars: BarSeries,
                        atr: list) -> Optional[list[bool]]:
        n = len(bars.close)
        if n < max(BB_N, KC_N) + 2:
            return None
        ema = self.ema(bars.close, KC_N)
        sma = self.sma(bars.close, BB_N)
        sd = self.stdev(bars.close, BB_N)
        out = []
        for k in range(n):
            if None in (atr[k], ema[k], sma[k], sd[k]):
                out.append(False)
                continue
            out.append(sma[k] - BB_K * sd[k] > ema[k] - KC_K * atr[k]
                       and sma[k] + BB_K * sd[k] < ema[k] + KC_K * atr[k])
        return out

    def _momentum(self, bars: BarSeries) -> Optional[list[Optional[float]]]:
        """Linear-regression slope of close minus the Donchian/SMA midpoint."""
        n = len(bars.close)
        if n < MOM_N * 2:
            return None
        sma = self.sma(bars.close, MOM_N)
        xs = list(range(MOM_N))
        xm = sum(xs) / MOM_N
        denom = sum((x - xm) ** 2 for x in xs)
        dev: list[Optional[float]] = [None] * n
        for k in range(MOM_N - 1, n):
            if sma[k] is None:
                continue
            hh = max(bars.high[k - MOM_N + 1:k + 1])
            ll = min(bars.low[k - MOM_N + 1:k + 1])
            dev[k] = bars.close[k] - ((hh + ll) / 2 + sma[k]) / 2
        out: list[Optional[float]] = [None] * n
        for k in range(MOM_N * 2 - 2, n):
            w = dev[k - MOM_N + 1:k + 1]
            if any(v is None for v in w):
                continue
            wm = sum(w) / MOM_N
            out[k] = sum((x - xm) * (v - wm) for x, v in zip(xs, w)) / denom
        return out
