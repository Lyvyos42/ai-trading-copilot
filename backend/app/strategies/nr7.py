"""Narrow Range 7: breakout after a volatility contraction.

REFERENCES
Crabel (1990), "Day Trading With Short Term Price Patterns and Opening Range
Breakout"; Raschke & Connors (1996).

PRE-REGISTERED AND REFUTED

Specification fixed in advance - PREREG_2026-09-07_nr7_breakout.md - before
any of it was run, which is why the numbers below are a result rather than the
best of a search:

  qualification  session range (09:30-16:00 ET) < min of the previous six
  breakout       09:30-10:00 of the following session sets ORH and ORL
  entry          close of the first M30 bar between 10:00 and 14:00 that
                 closes beyond one of them; exactly one trade per session
  exit           the 15:00 bar's close, being the last bar ending at or
                 before the specified 15:50 flatten
  stops          variant 1 the opposite edge, variant 2 the midpoint
  universe       sp500, nasdaq, us30, spy, qqq
  hurdle         chronological 80/20, out-of-sample |t| >= 2.96,
                 retention >= 0.70, net of spread and a 2.2%-of-R tick jump

RESULT, net of the spread quoted on the entry bar:

    symbol   stop        n    gross   net expR   win%    PF   full-sample t
    sp500    opposite   167   +0.164    +0.020   49.7   1.05      +0.27
    sp500    midpoint   167   +0.195    -0.025   43.7   0.96      -0.23
    nasdaq   opposite   142   +0.061    +0.019   50.7   1.06      +0.27
    nasdaq   midpoint   142   +0.128    +0.073   47.2   1.15      +0.67
    us30     opposite   144   +0.043    -0.027   46.5   0.92      -0.36
    us30     midpoint   144   +0.039    -0.062   41.0   0.88      -0.60
    spy      opposite    87   +0.120    +0.093   56.3   1.31      +1.08
    spy      midpoint    87   +0.209    +0.180   51.7   1.41      +1.38
    qqq      either      13   too few trades to test

Nothing reaches 2.96, and nothing reaches it IN SAMPLE either - the best
full-sample t is 1.38. Costs are not the explanation: the gross column is
+0.04R to +0.21R, so there was little to erode.

Out of sample it is worse than absent:

    spy    midpoint   IS Sharpe 1.23 -> OOS -0.18   t -0.12   retention -0.15
    spy    opposite   IS Sharpe 1.06 -> OOS -0.58   t -0.37   retention -0.55
    sp500  opposite   IS Sharpe 0.16 -> OOS -0.02   t -0.02   retention -0.16
    nasdaq midpoint   IS Sharpe 0.26 -> OOS  0.51   t +0.48   retention  1.96

Negative retention on three of four: the out-of-sample period lost money. The
one positive retention sits on an in-sample Sharpe of 0.26, so 1.96 of nearly
nothing is nothing.

WHY THIS IS WORTH KEEPING IN THE TREE

The pattern is genuine - a narrow session is followed by a wider one, that is
what volatility clustering means. What does not follow is that the DIRECTION
of the expansion is predictable from the opening range, and that is the claim
a breakout trade makes. Measured across 540 qualifying sessions and five
instruments, it is not.

The module stays so the specification, the hurdle and the outcome sit together
in one place. A future proposal to trade NR7 has to explain what is different
about its version, rather than rediscovering this one.
"""
from __future__ import annotations

from typing import Optional, Sequence

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, Direction, SignalResult,
)
from app.strategies.session_windows import (
    OPENING_RANGE_END, RTH_CLOSE, RTH_OPEN, et_epoch, to_et,
)

NR_LOOKBACK = 6           # "NR7" is this session against the previous six
NO_ENTRY_AFTER = 14       # hour, ET
DEFAULT_STOP = "midpoint"


def is_narrow_range(ranges: Sequence[float], lookback: int = NR_LOOKBACK) -> bool:
    """Is the last range narrower than every one of the previous `lookback`?

    Strictly narrower. Using <= would count a tie, and on instruments quoted
    to one decimal ties are common enough to inflate the qualification rate.
    """
    if len(ranges) < lookback + 1:
        return False
    return all(ranges[-1] < r for r in ranges[-1 - lookback:-1])


class NR7BreakoutStrategy(BaseStrategy):
    """Opening-range breakout, taken only after a narrow-range session."""

    name = "nr7_breakout"
    requires = (DataNeed.OHLC, DataNeed.SESSION_TIMES)
    intervals = ("30m", "M30", "15m", "M15")
    validated_on = ()

    def __init__(self, stop_variant: str = DEFAULT_STOP,
                 lookback: int = NR_LOOKBACK,
                 require_validation: bool = True):
        super().__init__(stop_variant=stop_variant, lookback=lookback,
                         require_validation=require_validation)
        self.stop_variant = stop_variant
        self.lookback = lookback
        self.require_validation = require_validation

    def min_bars(self) -> int:
        return (self.lookback + 2) * 10

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        if self.require_validation:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "NR7_REFUTED: pre-registered and tested across 540 qualifying "
                "sessions on five instruments. Best full-sample t is 1.38 "
                "against a 2.96 hurdle, and out-of-sample retention is "
                "NEGATIVE on three of four variants. Gross expectancy is "
                "+0.04R to +0.21R, so costs are not the explanation.")

        sessions = _sessions(bars)
        if len(sessions) < self.lookback + 2:
            return SignalResult.abstain(
                self.name, bars.symbol,
                f"needs {self.lookback + 2} sessions of history")

        ranges = [hi - lo for _, _, hi, lo in sessions[:-1]]
        if not is_narrow_range(ranges, self.lookback):
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=(f"prior session was not narrower than each of the "
                        f"{self.lookback} before it"),
                evidence={"prior_range": ranges[-1] if ranges else None,
                          "lookback_ranges": ranges[-self.lookback:]})

        today, idx, _, _ = sessions[-1]
        opening = [i for i in idx if RTH_OPEN <= to_et(bars.time[i]).time() < OPENING_RANGE_END]
        if not opening:
            return SignalResult.abstain(
                self.name, bars.symbol, "no 09:30-10:00 bars this session")

        orh = max(bars.high[i] for i in opening)
        orl = min(bars.low[i] for i in opening)
        orm = (orh + orl) / 2.0
        if orh <= orl:
            return SignalResult.abstain(self.name, bars.symbol, "degenerate opening range")

        evidence = {"orh": orh, "orl": orl, "orm": orm,
                    "prior_range": ranges[-1],
                    "session": str(today)}

        window = [i for i in idx
                  if OPENING_RANGE_END <= to_et(bars.time[i]).time()
                  and to_et(bars.time[i]).hour < NO_ENTRY_AFTER]
        if not window:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason="narrow-range session behind, opening range set, no "
                       "entry window bars yet",
                evidence=evidence)

        for i in window:
            c = bars.close[i]
            side = 1 if c > orh else (-1 if c < orl else 0)
            if side == 0:
                continue
            stop = (orl if side > 0 else orh) if self.stop_variant == "opposite" else orm
            risk = abs(c - stop)
            if risk <= 0:
                break
            return SignalResult(
                strategy=self.name, symbol=bars.symbol,
                direction=Direction.LONG if side > 0 else Direction.SHORT,
                conviction=0.5,
                entry=c, stop=stop,
                target=c + side * 2.0 * risk,
                time_exit_utc=et_epoch(today, RTH_CLOSE),
                reason=(f"closed beyond the opening range after a narrow-range "
                        f"session; {self.stop_variant} stop at {stop:.4f}"),
                evidence={**evidence, "stop_variant": self.stop_variant},
            )

        return SignalResult(
            strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
            reason="narrow-range session behind, but price has not closed "
                   "beyond the opening range inside the entry window",
            evidence=evidence)


def _sessions(bars: BarSeries) -> list[tuple[object, list[int], float, float]]:
    """(date, indices, high, low) per cash session, oldest first."""
    by_day: dict = {}
    for i, t in enumerate(bars.time):
        et = to_et(t)
        if not (RTH_OPEN <= et.time() < RTH_CLOSE):
            continue
        by_day.setdefault(et.date(), []).append(i)
    out = []
    for d in sorted(by_day):
        idx = by_day[d]
        out.append((d, idx,
                    max(bars.high[i] for i in idx),
                    min(bars.low[i] for i in idx)))
    return out
