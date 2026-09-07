"""orb_london_0830: break the 08:30-08:45 London range, ride the morning trend.

ECONOMIC MECHANISM AS FILED
The 08:00 London cash open produces a violent liquidity spike; anchoring the
range at 08:30 instead captures the post-open consolidation and breaks out into
the established European morning trend.

PRE-REGISTERED

    range     08:30-08:45 Europe/London (one M15 bar), via the Athens server
              clock through zoneinfo
    primary   GBPUSD M15, 99,000 bars, 2022-09 to 2026-09, 1,033 sessions
    validate  EURUSD M15, same window and session count
    controls  USDJPY and EURJPY - SEE THE BLOCKER BELOW
    entry     a close beyond the range; fill at the next bar's open with
              symmetric half-spread accounting; entry-bar stop check active
    stop      the opposite end of the range
    targets   measured move (1.0x range height from the breakout level) and,
              separately, a 1:1.5 reward-to-risk
    timeout   entries only within 8 bars of the range end (08:45-10:45 London)
    eod       flat by 16:30 London
    costs     quoted dynamic spread plus $3.00/lot round-turn commission
    gates     OOS |t| >= 3.06 on a chronological 80/20 split, modern third
              (2025-2026) |t| >= 2.00, directional symmetry, bias-matched control

THE PREMISE CHECKS OUT, AND IT IS SMALLER THAN IT SOUNDS
Median GBPUSD M15 range by London bar: 07:45 9.0 pips, 08:00 11.7, 08:15 10.3,
08:30 9.8, 08:45 9.9. The filed 117 and 98 "pts" are points, and they reconcile
exactly. So the 08:00 bar IS the widest of the morning - by 19% over 08:30, and
08:30 is no quieter than 07:45 or 08:45. "Violent initial spike" overstates a
bar one fifth wider than its neighbours.

TWO BLOCKERS, RECORDED RATHER THAN WORKED AROUND

1. THE JPY CONTROLS CANNOT RUN AT THIS SPECIFICATION. Only usdjpy_h1 and
   eurjpy_h1 exist; there is no M15 export for either. Both files contain ZERO
   bars at London 08:30, because an hourly bar cannot resolve a 15-minute
   range. Substituting the 08:00-09:00 H1 bar would anchor on precisely the
   open bar this mechanism is defined to avoid, so it is a different
   hypothesis. It was run anyway and is reported below, flagged, because a
   silent omission is worse than a labelled mismatch.

2. ZERO SPREADS ARE AN EXPORT ARTEFACT, AND THEY MATTER HERE. 56.4% of EURUSD
   and 26.5% of GBPUSD entry-window bars quote spread = 0. Read literally, over
   half the EURUSD sample would trade for free against a cost model that is the
   whole question. Zeros are floored at each instrument's non-zero median
   (3.0 points). Without that floor the EURUSD result is flattered by roughly
   half its true spread bill.

A SPECIFICATION DEFECT IN THE MEASURED-MOVE TARGET

The stop is the far end of the range and the fill is the open AFTER a close
beyond the near end, so risk is not the range height - it is 1.32x the range
height, the overshoot being the breakout bar's excursion plus the gap to the
next open. A target of 1.0x the range height measured from the breakout LEVEL
is therefore only 0.52R measured from the ENTRY.

That geometry needs a 66% win rate merely to break even. It gets 66%.

    pair    target     median target   win rate   breakeven win rate needed
    GBPUSD  measured       0.52R          66%              66%
    EURUSD  measured       0.51R          63%              66%
    GBPUSD  1:1.5          1.50R          43%              40%
    EURUSD  1:1.5          1.50R          40%              40%

Four cells, two geometries, two pairs, and the realised win rate lands within
three points of the arithmetic breakeven in every one. This is what an
efficiently priced breakout looks like: the market pays out exactly the odds
the structure implies, and the toll is the entire difference.

RESULT - 0 OF 4 CELLS PASS. REFUTED ON BOTH PAIRS.

    pair    target      n     net R      t    win   control   Welch
    GBPUSD  measured   889    -0.042  -1.75   66%   -0.054   +0.46
    GBPUSD  1:1.5     1015    +0.002  +0.04   43%   -0.080   +2.10
    EURUSD  measured   875    -0.077  -3.14   63%   -0.065   -0.46
    EURUSD  1:1.5     1003    -0.068  -1.81   40%   -0.073   +0.13

Gates on the only non-negative cell, GBPUSD at 1:1.5:

    G1  out-of-sample t +0.77 (n=203) against 3.06        FAIL
        retention -4.54 - in-sample Sharpe is negative, so the ratio is
        not a number, the same artefact seen in artemis_squeeze
    G2  2025-2026 t -0.59 (n=429), net -0.034R            FAIL
    G3  symmetry: long +0.045R, short -0.042R             FAIL
    G4  control Welch +2.10                               PASS

It passes the control gate on a net of +0.002R, for the third time in this
programme: the control loses -0.080R, so "beats its own shadow" is again
satisfied by a strategy that earns nothing. The validation pair is negative in
both geometries and reaches t -3.14.

THE DECISIVE MEASUREMENT: THERE IS NO EDGE FOR THE COSTS TO EAT

Re-run with zero spread and zero commission, the same entries:

    pair    target     gross R      t      net R      t     toll
    GBPUSD  measured    +0.017   +0.70    -0.042   -1.75   0.060
    GBPUSD  1:1.5       +0.053   +1.40    +0.002   +0.04   0.051
    EURUSD  measured    -0.010   -0.42    -0.077   -3.14   0.066
    EURUSD  1:1.5       +0.003   +0.07    -0.068   -1.81   0.071

Gross expectancy is statistically zero in all four cells - the best t is 1.40 -
before a single pip of cost is charged. So this is NOT a real edge destroyed by
the toll, which would leave open a cheaper-execution argument. It is nothing,
and then a uniform 0.05-0.07R toll on top. No commission schedule or spread
improvement reaches a positive number from here.

THE JPY CONTROLS, AT THE WRONG ANCHOR, AGREE ANYWAY

08:00-09:00 H1 range, 2-bar entry window, 16 years. Different hypothesis,
reported for completeness only:

    USDJPY  measured  n=2277  -0.034R  t -2.24      EURJPY  measured  -0.033R  t -2.30
    USDJPY  1:1.5     n=2554  -0.029R  t -1.40      EURJPY  1:1.5     -0.007R  t -0.35

All four negative, two significantly so, on 9,665 trades across 16 years.

VERDICT: refuted. This is the fifth instrument family on which the range-
breakout shape has failed here, after the equity Donchian work and CRT. The
distinctive contribution of this run is the geometry: the filed measured-move
target is sub-1R once entry overshoot is counted, and the realised win rate
matches its breakeven to within three points on every cell.
"""
from __future__ import annotations

from datetime import time as dtime
from typing import Optional
from zoneinfo import ZoneInfo

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, Direction, SignalResult,
)

LONDON = ZoneInfo("Europe/London")
RANGE_START = dtime(8, 30)
RANGE_END = dtime(8, 45)
ENTRY_DEADLINE = dtime(10, 45)
EOD = dtime(16, 30)


class LondonORBStrategy(BaseStrategy):
    """Break the 08:30-08:45 London range into the European morning trend."""

    name = "orb_london_0830"
    requires = (DataNeed.OHLC, DataNeed.SESSION_TIMES)
    intervals = ("15m", "M15")
    validated_on = ()

    def __init__(self, target: str = "rr", rr: float = 1.5,
                 require_validation: bool = True):
        super().__init__(target=target, rr=rr,
                         require_validation=require_validation)
        self.target = target
        self.rr = rr
        self.require_validation = require_validation

    def min_bars(self) -> int:
        return 40

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        if self.require_validation:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "ORB_LONDON_0830_REFUTED: 3,782 trades on GBPUSD and EURUSD "
                "M15 over 1,033 sessions, at two target geometries. Zero of "
                "four cells pass. GROSS expectancy - zero spread, zero "
                "commission - is statistically nil in all four (best t 1.40), "
                "so there is no edge for the 0.05-0.07R toll to eat. The filed "
                "measured-move target is only 0.52R from entry once the 1.32x "
                "entry overshoot is counted, and needs a 66% win rate to break "
                "even; it gets 66%. The one non-negative cell, GBPUSD at "
                "1:1.5, nets +0.002R and clears the control gate at Welch 2.10 "
                "only because the control loses -0.080R. The validation pair "
                "is negative in both geometries, to t -3.14. JPY controls "
                "could not be run at this specification - no M15 export "
                "exists - but at the 08:00 H1 anchor all four cells are "
                "negative over 16 years.")

        i = len(bars.close) - 1
        rng = self._session_range(bars, i)
        if rng is None:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "the 08:30-08:45 London range is not complete in this session")
        hi, lo = rng
        height = hi - lo
        if height <= 0:
            return SignalResult.abstain(self.name, bars.symbol, "degenerate range")

        now = self._london(bars.time[i]).timetz()
        evidence = {"range_high": hi, "range_low": lo, "height": height,
                    "london_time": now.strftime("%H:%M")}

        if now.replace(tzinfo=None) > ENTRY_DEADLINE:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason="past the 10:45 London entry deadline",
                evidence=evidence)

        close = bars.close[i]
        if lo <= close <= hi:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=f"close {close:.5f} is inside {lo:.5f}-{hi:.5f}",
                evidence=evidence)

        side = 1 if close > hi else -1
        stop = lo if side > 0 else hi
        risk = abs(close - stop)
        if risk <= 0:
            return SignalResult.abstain(self.name, bars.symbol, "zero risk distance")
        if self.target == "measured":
            tgt = (hi + height) if side > 0 else (lo - height)
        else:
            tgt = close + side * self.rr * risk

        return SignalResult(
            strategy=self.name, symbol=bars.symbol,
            direction=Direction.LONG if side > 0 else Direction.SHORT,
            conviction=0.5,
            entry=None,        # fills at the next bar's open, not at a level
            stop=stop, target=tgt,
            reason=(f"closed beyond the 08:30-08:45 London range "
                    f"{lo:.5f}-{hi:.5f}"),
            evidence={**evidence, "target_R": abs(tgt - close) / risk},
        )

    def _london(self, epoch: int):
        from datetime import datetime, timezone
        return datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone(LONDON)

    def _session_range(self, bars: BarSeries,
                       i: int) -> Optional[tuple[float, float]]:
        """High and low of bars opening in [08:30, 08:45) London, this session."""
        today = self._london(bars.time[i]).date()
        hi = lo = None
        for k in range(i, -1, -1):
            lt = self._london(bars.time[k])
            if lt.date() != today:
                break
            t = lt.time()
            if RANGE_START <= t < RANGE_END:
                hi = bars.high[k] if hi is None else max(hi, bars.high[k])
                lo = bars.low[k] if lo is None else min(lo, bars.low[k])
        if hi is None or lo is None:
            return None
        return hi, lo
