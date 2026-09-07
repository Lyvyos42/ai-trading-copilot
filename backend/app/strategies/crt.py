"""Candle Range Theory: sweep a higher-timeframe extreme, reject, fade the far side.

WHAT THIS IS, STATED BEFORE THE RESULT

Structurally this is the Donchian breakout failure trade at a different anchor:
price takes out an extreme, closes back inside, and is faded toward the
opposite side. That mechanism was already refuted on equities across four
instruments. CRT anchors on a completed 1H or 4H candle rather than a rolling
N-bar channel, and runs inside session killzones, but the trade is the same
shape. Read the result against that prior.

PRE-REGISTERED - two specifications, primary and validation symbol each

    Spec A   1H reference candle -> M5 entry    XAUUSD, validated on XAGUSD
    Spec B   4H reference candle -> M15 entry   XAUUSD, validated on XAGUSD
    setup    an LTF bar trades beyond the reference extreme and CLOSES back
             inside it
    entry    open of the next LTF bar
    stop     the sweep bar's extreme +/- 0.10 x ATR(14)
    target   the opposite extreme of the reference candle
    screens  no entries within 30 minutes of the 00:00 Athens rollover; no bars
             with spread above 2.0x the median
    gates    OOS |t| >= 2.96, retention >= 0.70, modern third |t| >= 2.00,
             directional symmetry, and a bias-matched control

KILLZONES ARE SESSION-LOCAL, NOT GMT
The original specification wrote both windows in GMT. London runs BST for seven
months a year, so a fixed 07:00-10:00 GMT is a different hour of the London
session for most of the calendar; and 12:30-15:00 GMT is not the New York cash
open under either offset. Implemented as 07:00-10:00 Europe/London and
08:00-11:00 America/New_York.

THE CONTROL IS THE EXPERIMENT

Gold ran +141% across the M15 sample and silver +243%. A signal with any long
tilt shows profit from that alone. Each real trade is matched with a random
entry carrying the SAME side, the SAME risk distance and the SAME target
distance, drawn from the same killzone on a different day, twenty draws per
trade. If the setup has an edge it beats its own shadow.

RESULT - CRT DOES NOT BEAT ITS OWN CONTROL ON ANY SPECIFICATION

    Spec B, 4H -> M15, 4.2 years
      XAUUSD   n=2020   net +0.021R  t +0.43   control -0.024R   Welch +0.92
      XAGUSD   n=1802   net -0.180R  t -3.83   control -0.128R   Welch -1.08

    Spec A, 1H -> M5, 17 months
      XAUUSD   n=1803   net -0.017R  t -0.36   control -0.027R   Welch +0.22
      XAGUSD   n=1932   net -0.221R  t -4.75   control -0.312R   Welch +1.93

The best figure in the table is silver on Spec A, where CRT beats the control
at Welch 1.93 - and both sides are deeply negative. Being less bad than a
random entry is not an edge.

The validation symbol fails outright on both specifications, at t -3.83 and
-4.75.

ONE REASSURING FINDING FROM THE CONTROL

The long share is 46-49% on every run. So the +141% drift is NOT flowing into
the signal - CRT is genuinely two-sided, and its near-zero result on gold is
real nothing rather than hidden beta. That is what the control was built to
establish, and it establishes it in the direction that clears the strategy of
the beta charge while still finding no edge.

EVERY GATE, ON THE STRONGEST CASE (XAUUSD Spec B)

    Gate 1  out-of-sample t 0.76 against 2.96
            (retention reads 43.66, which is noise: in-sample Sharpe is 0.02,
             so the ratio is a small number divided by a smaller one)
    Gate 2  modern third t 0.38 against a required 2.00
    Gate 3  directional symmetry FAILS - long +0.077R at t 1.12, short -0.031R
    Gate 3  bias-matched control Welch +0.92, not significant

Also worth recording: maximum drawdown is -53.6% at 1% risk per trade, with a
19-trade losing streak, and the Monte Carlo p99 is -83.2%. Even had the
expectancy been positive, that path is not tradeable at this risk fraction.

VERDICT: refuted. Two specifications, two instruments, 7557 trades, and the
mechanism does not distinguish itself from a random entry with the same
geometry. Together with the equity work this is the same trade shape refused on
six instruments across three asset classes.
"""
from __future__ import annotations

from datetime import time as dtime
from typing import Optional, Sequence

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, Direction, SignalResult,
)
from app.strategies.session_windows import to_et

LONDON_KILLZONE = (dtime(7, 0), dtime(10, 0))     # Europe/London
NY_KILLZONE = (dtime(8, 0), dtime(11, 0))         # America/New_York
STOP_BUFFER_ATR = 0.10
MAX_SPREAD_MULTIPLE = 2.0


class CRTStrategy(BaseStrategy):
    """Fade a swept higher-timeframe candle extreme back toward its far side."""

    name = "crt"
    requires = (DataNeed.OHLC, DataNeed.SESSION_TIMES)
    intervals = ("5m", "M5", "15m", "M15")
    validated_on = ()

    def __init__(self, htf_hours: int = 4, stop_buffer_atr: float = STOP_BUFFER_ATR,
                 require_validation: bool = True):
        super().__init__(htf_hours=htf_hours, stop_buffer_atr=stop_buffer_atr,
                         require_validation=require_validation)
        self.htf_hours = htf_hours
        self.stop_buffer_atr = stop_buffer_atr
        self.require_validation = require_validation

    def min_bars(self) -> int:
        return max(60, self.htf_hours * 12 + 20)

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        if self.require_validation:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "CRT_REFUTED: 7557 trades across two specifications and two "
                "metals. Against a bias-matched control with identical side, "
                "risk and target distance, the best Welch is +1.93 - on silver "
                "M5, where both the strategy and the control are deeply "
                "negative. XAUUSD Spec B nets +0.021R at t 0.43 with the "
                "control at -0.024R (Welch 0.92); the validation symbol fails "
                "outright at t -3.83 and -4.75. Modern-third t is 0.38 against "
                "a required 2.00, and shorts are negative so directional "
                "symmetry fails.")

        i = len(bars.close) - 1
        atr = self.atr(bars.high, bars.low, bars.close, 14)[i]
        if atr is None or atr <= 0:
            return SignalResult.abstain(self.name, bars.symbol, "ATR unavailable")

        ref = self._reference_candle(bars, i)
        if ref is None:
            return SignalResult.abstain(
                self.name, bars.symbol,
                f"no completed {self.htf_hours}H reference candle available")
        ref_hi, ref_lo = ref
        if ref_hi <= ref_lo:
            return SignalResult.abstain(self.name, bars.symbol, "degenerate reference candle")

        hi, lo, cl = bars.high[i], bars.low[i], bars.close[i]
        evidence = {"ref_high": ref_hi, "ref_low": ref_lo,
                    "htf_hours": self.htf_hours, "atr": atr}

        swept_high = hi > ref_hi and cl < ref_hi
        swept_low = lo < ref_lo and cl > ref_lo
        if not (swept_high or swept_low):
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=(f"no sweep and rejection of the {self.htf_hours}H "
                        f"range {ref_lo:.2f}-{ref_hi:.2f}"),
                evidence=evidence)

        side = -1 if swept_high else 1
        stop = ((hi + self.stop_buffer_atr * atr) if swept_high
                else (lo - self.stop_buffer_atr * atr))
        target = ref_lo if swept_high else ref_hi

        return SignalResult(
            strategy=self.name, symbol=bars.symbol,
            direction=Direction.SHORT if side < 0 else Direction.LONG,
            conviction=0.5,
            entry=None,        # fills at the next bar's open, not at a level
            stop=stop, target=target,
            reason=(f"swept the {self.htf_hours}H "
                    f"{'high' if swept_high else 'low'} and closed back inside; "
                    f"fade toward {target:.2f}"),
            evidence={**evidence, "swept": "high" if swept_high else "low"},
        )

    def _reference_candle(self, bars: BarSeries,
                          i: int) -> Optional[tuple[float, float]]:
        """High and low of the last COMPLETED higher-timeframe candle."""
        secs = self.htf_hours * 3600
        current_bucket = bars.time[i] // secs
        prev_bucket = current_bucket - 1
        hi = lo = None
        for k in range(i, -1, -1):
            b = bars.time[k] // secs
            if b < prev_bucket:
                break
            if b != prev_bucket:
                continue
            hi = bars.high[k] if hi is None else max(hi, bars.high[k])
            lo = bars.low[k] if lo is None else min(lo, bars.low[k])
        if hi is None or lo is None:
            return None
        return hi, lo
