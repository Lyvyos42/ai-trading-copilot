"""meanrev: fade a five-factor extension composite on H4 FX back to equilibrium.

MECHANISM
Hourly FX continues - order flow dominates and the H1 cell measures -0.15R at
t -0.52, which is expected rather than disappointing (Evans & Lyons 2002). The
claim is that multi-day H4 extension is stationary and reverts.

PRE-REGISTERED

    primary    EURUSD H4, resampled from 99,000 H1 bars, 2010-09 to 2026-09
    validation GBPUSD H4, same window
    signal     |composite z| >= 1.5, each component normalised over 200 bars
    exits      A time-based, 48 H4 bars (~8 trading days)
               B dynamic, close crossing the 20-period SMA
    stop       3.0 x ATR(14), catastrophic only - it is not the exit
    costs      symmetric half-spread on entry and exit, $3.00/lot round turn
    gates      control Welch >= 2.00 AND net >= +0.05R; OOS clustered t >= 2.96
               with Sharpe retention >= 0.70; 2021-2026 clustered t >= 2.00;
               longs and shorts both positive

R IS THE 3.0-ATR STOP DISTANCE, so +0.112R is +0.337 ATR per trade. Quoted in
ATR the leading cell reproduces the engine's filed +0.3175 almost exactly, which
is the check that this is the same object and not a re-specification.

THE FILED FACTOR LIST IS NOT THE ONE THE ENGINE COMPUTES

    filed                              core/meanrev_engine.py actually computes
    distance from SMA(20) / ATR(14)    z((c - SMA(50)) / ATR)
    RSI(14) extension                  z(RSI(48) - 50)
    Bollinger %B extension             z((c - c[-48]) / ATR)     48-bar momentum
    ATR stretch ratio                  z((c - c[-96]) / ATR)     96-bar momentum
    Donchian mid-distance              z((c - low96) / (high96 - low96))

Only the last is close. Both were run: `engine` is the composite carrying the
t +1.82 prior, `brief` is the filed list, which is an untested construction.

THE H4 RESAMPLE HAD TO BE DONE ON THE WALL CLOCK
Resampling a tz-aware index with pandas bins on absolute time, so the Athens
bucket labels drift an hour across DST and the bars stop matching the
00/04/08/12/16/20 server-clock bars MT5 itself draws - 12 distinct bucket hours
instead of 6. Resampled on the naive Athens wall clock the count is 24,812 H4
bars, against the ~24,750 expected.

RESULT - NO CELL PASSES ALL FIVE GATES. BEST IS 3 OF 5.

    pair    factors  exit        n    net R      t   ATR/tr  control  Welch
    EURUSD  engine   time      384   +0.112  +1.64   +0.337   -0.038  +2.13
    EURUSD  engine   sma       657   +0.003  +0.12   +0.009   -0.010  +0.49
    EURUSD  brief    time      305   +0.020  +0.25   +0.061   -0.024  +0.53
    EURUSD  brief    sma       402   +0.003  +0.08   +0.008   -0.011  +0.37
    GBPUSD  engine   time      389   +0.038  +0.55   +0.114   -0.029  +0.94
    GBPUSD  engine   sma       662   -0.011  -0.46   -0.034   -0.010  -0.05
    GBPUSD  brief    time      281   +0.102  +1.13   +0.306   -0.052  +1.67
    GBPUSD  brief    sma       370   +0.042  +1.11   +0.127   -0.008  +1.27

The pre-registered primary arm, EURUSD engine/time:

    G1  out-of-sample clustered t +1.69 (n=77) against 2.96      FAIL
        Sharpe retention +1.99                                   PASS
    G2  2021-2026 clustered t +1.76 (n=142, +0.089R)             FAIL
    G3  symmetry: long +0.033R, short +0.192R, both positive     PASS
    G4  control Welch +2.13 AND net +0.112R >= +0.05R            PASS

It is the first candidate in this programme to pass the AMENDED control gate on
its merits - a real positive expectancy, not merely a less-negative one. It then
fails on power, twice.

The validation pair fails the same specification: GBPUSD engine/time nets
+0.038R at Welch +0.94, and its short leg is negative, so it fails both the
control gate and symmetry.

THE MONTHLY CLUSTERED t IS NOT A ROBUSTNESS ADJUSTMENT - IT CHANGES THE ESTIMAND

On the leading cell the clustered t is +3.75 against a naive +1.64. Clustering
normally LOWERS a t by admitting within-cluster correlation. It raises this one
because equal-weighting months is a different portfolio:

    pooled mean, equal weight per TRADE      +0.1125R
    mean of month means, equal per MONTH     +0.3061R

    months with 1 trade    49 months   +0.928R
    months with 2 trades   60 months   +0.322R
    months with 3 trades   45 months   -0.163R
    months with 4 trades   16 months   -0.239R
    months with 5 trades    2 months   -0.196R
    months with 6 trades    1 month    -0.268R

Monotonic across every bucket: the more extension signals fire in a month, the
worse they do. That is economically legible - a month generating many extension
readings is a trending month, and fades lose in trends - but it means the
monthly average upweights precisely the quiet months that carry the result. You
cannot trade the equal-weighted-month version without knowing in advance which
months will be quiet. The tradeable number is +0.112R.

This matters beyond this run: the engine's historical figures (+3.42 originally,
+2.23 and +1.82 on re-run) are all monthly clustered t, so all of them carry the
same inflation. The honest prior for meanrev is weaker than the record states.

THE ARBITER, WHICH AVERAGES NOTHING AWAY
Stationary block bootstrap on the trade sequence, 10,000 draws, mean block 12:

    mean +0.1125R   95% CI [-0.0029, +0.2298]   P(mean <= 0) = 0.028

Marginally significant alone, nowhere near the 8-cell Bonferroni bar of 0.006.

WHAT SURVIVES, AND IT IS NOT NOTHING

Era stability on the primary cell is the best in this programme:

    2010-2014  n= 97  +0.115R      2019-2021  n= 80  +0.056R
    2015-2018  n= 92  +0.131R      2022-2026  n=115  +0.135R

Four eras, all positive, no decay, and not one of them significant. Compare the
two GBPUSD `brief` cells, which post the grid's strongest modern thirds
(clustered t +3.01 and +4.06) on eras that flip sign: -0.135R in 2015-2018 and
+0.188R in 2022-2026. Those are regimes discovered by searching eight cells, not
edges - and they sit on the arm that is neither the pre-registered composite nor
the primary pair.

The beta charge is cleared. The composite fires exactly 192 long and 192 short,
and the bias-matched control shows only a 0.024R tilt toward shorts across a
sample where EURUSD went 1.3327 to 1.1626. The short leg beats its own matched
control by +0.218R at Welch +2.10, so the asymmetry is not the euro downtrend.

VERDICT: gated, underpowered - not refuted. Positive sign in 7 of 8 cells, era
stability across 16 years, a clean control result on the primary, and no gate
cleared on significance. This is the same conclusion the engine reached in
August - "what a small genuine edge looks like, and also what a subtle bias
looks like" - with two things added: the beta charge is now disposed of, and the
clustered-t inflation is now measured, which makes the true prior weaker than
the filed one rather than stronger. Promotion needs an independent sample, not
another pass over these sixteen years.
"""
from __future__ import annotations

from typing import Optional

import math

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, Direction, SignalResult,
)

THRESHOLD = 1.5
Z_WINDOW = 200
HOLD_BARS = 48
STOP_ATR = 3.0


# The engine's own RSI and ATR, reproduced rather than borrowed from
# BaseStrategy. BaseStrategy.rsi is Wilder-smoothed and the engine's is a plain
# rolling mean of gains and losses; at n=48 that difference moves the composite
# by a constant 0.125 z and disagrees on 7% of signals at the 1.5 threshold. The
# measured result belongs to the engine's construction, so the class has to
# compute that one or the docstring above describes a different strategy.
def _engine_rsi(c: list, n: int) -> list:
    out = [None] * len(c)
    g = l = 0.0
    gains, losses = [], []
    for i in range(len(c)):
        d = c[i] - c[i - 1] if i else 0.0
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
        w = min(n, i + 1)
        g = sum(gains[i - w + 1:i + 1]) / w
        l = sum(losses[i - w + 1:i + 1]) / w
        out[i] = 100.0 - 100.0 / (1.0 + g / (l if l else 1e-9))
    return out


def _engine_atr(high: list, low: list, close: list, n: int = 14) -> list:
    tr = [high[0] - low[0]]
    for i in range(1, len(close)):
        tr.append(max(high[i] - low[i],
                      abs(high[i] - close[i - 1]),
                      abs(low[i] - close[i - 1])))
    out = []
    for i in range(len(tr)):
        w = tr[max(0, i - n + 1):i + 1]
        out.append(sum(w) / len(w))
    return out


class MeanReversionStrategy(BaseStrategy):
    """Fade an extension composite on H4 FX toward the moving-average mean."""

    name = "meanrev"
    requires = (DataNeed.OHLC,)
    intervals = ("4h", "H4", "240m")
    validated_on = ()

    def __init__(self, threshold: float = THRESHOLD, hold_bars: int = HOLD_BARS,
                 stop_atr: float = STOP_ATR, require_validation: bool = True):
        super().__init__(threshold=threshold, hold_bars=hold_bars,
                         stop_atr=stop_atr, require_validation=require_validation)
        self.threshold = threshold
        self.hold_bars = hold_bars
        self.stop_atr = stop_atr
        self.require_validation = require_validation

    def min_bars(self) -> int:
        return max(Z_WINDOW + 50, 250)

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        if self.require_validation:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "MEANREV_UNDERPOWERED: 3,450 trades over EURUSD and GBPUSD H4, "
                "16 years, 8 cells. No cell passes all five gates. The "
                "pre-registered primary (EURUSD, engine composite, time exit) "
                "nets +0.112R on n=384 and is the first candidate here to pass "
                "the amended control gate on merit - Welch +2.13 with a real "
                "+0.112R, not a less-negative one - and it holds +0.115/+0.131/"
                "+0.056/+0.135R across four eras with no decay. It then fails "
                "out-of-sample (clustered t +1.69 against 2.96) and the modern "
                "third (+1.76 against 2.00), and the validation pair fails the "
                "control gate at Welch +0.94 with a negative short leg. A block "
                "bootstrap puts P(mean<=0) at 0.028, short of the 8-cell "
                "Bonferroni bar of 0.006. Note also that the engine's filed "
                "clustered t figures are inflated: monthly clustering "
                "equal-weights months, and months with 1 trade return +0.928R "
                "against -0.239R for months with 4, so the estimand shifts from "
                "+0.112R to +0.306R. Underpowered, not refuted; promotion needs "
                "an independent sample.")

        i = len(bars.close) - 1
        atr = _engine_atr(bars.high, bars.low, bars.close, 14)[i]
        if atr is None or atr <= 0:
            return SignalResult.abstain(self.name, bars.symbol, "ATR unavailable")

        score = self._composite(bars)
        if score is None or score[i] is None or not math.isfinite(score[i]):
            return SignalResult.abstain(
                self.name, bars.symbol,
                f"extension composite needs {self.min_bars()} H4 bars")

        s = score[i]
        close = bars.close[i]
        evidence = {"score": s, "threshold": self.threshold, "atr": atr,
                    "hold_bars": self.hold_bars}

        if abs(s) < self.threshold:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=(f"extension {s:+.2f} is inside +/-{self.threshold} - "
                        f"not stretched"),
                evidence=evidence)

        side = -1 if s > 0 else 1          # stretched up, fade down
        return SignalResult(
            strategy=self.name, symbol=bars.symbol,
            direction=Direction.LONG if side > 0 else Direction.SHORT,
            conviction=min(abs(s) / self.threshold, 3.0) / 3.0,
            entry=None,                    # fills at the next bar's open
            stop=close - side * self.stop_atr * atr,
            target=None,                   # the exit is time-based, not a level
            reason=(f"extension {s:+.2f} beyond {self.threshold}; fade for "
                    f"{self.hold_bars} H4 bars"),
            evidence=evidence,
        )

    # The engine's composite, reproduced exactly - NOT the filed factor list.
    def _composite(self, bars: BarSeries) -> Optional[list[Optional[float]]]:
        n = len(bars.close)
        if n < self.min_bars():
            return None
        c = list(bars.close)
        atr = _engine_atr(bars.high, bars.low, bars.close, 14)
        sa = [a if (a and a > 0) else 1e-9 for a in atr]
        sma50 = [sum(c[max(0, k - 49):k + 1]) / len(c[max(0, k - 49):k + 1])
                 for k in range(n)]
        rsi48 = _engine_rsi(c, 48)

        parts = []
        parts.append([(r - 50.0) if r is not None else None for r in rsi48])
        parts.append([(c[k] - sma50[k]) / sa[k] if sma50[k] is not None else None
                      for k in range(n)])
        parts.append([(c[k] - c[k - 48]) / sa[k] if k >= 48 else None
                      for k in range(n)])
        parts.append([(c[k] - c[k - 96]) / sa[k] if k >= 96 else None
                      for k in range(n)])
        pos: list[Optional[float]] = [None] * n
        for k in range(n):
            hi = max(bars.high[max(0, k - 95):k + 1])
            lo = min(bars.low[max(0, k - 95):k + 1])
            pos[k] = (c[k] - lo) / (hi - lo) if hi > lo else 0.5
        parts.append(pos)

        zs = [self._rolling_z(p, Z_WINDOW) for p in parts]
        out: list[Optional[float]] = [None] * n
        for k in range(n):
            vals = [z[k] for z in zs if z[k] is not None and math.isfinite(z[k])]
            out[k] = sum(vals) / len(vals) if vals else None
        return out

    @staticmethod
    def _rolling_z(x: list, w: int, min_periods: int = 50) -> list:
        n = len(x)
        out: list[Optional[float]] = [None] * n
        for k in range(n):
            lo = max(0, k - w + 1)
            win = [v for v in x[lo:k + 1] if v is not None]
            if len(win) < min_periods:
                continue
            m = sum(win) / len(win)
            var = sum((v - m) ** 2 for v in win) / (len(win) - 1)
            sd = var ** 0.5
            if sd > 0 and x[k] is not None:
                out[k] = (x[k] - m) / sd
        return out
