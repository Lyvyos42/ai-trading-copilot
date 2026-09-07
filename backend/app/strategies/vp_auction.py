"""Volume profile: value area, and the auction's behaviour around it.

REFERENCES
Steidlmayer (CBOT, 1984) for the profile and the value area; Dalton, Jones &
Dalton (1990) for the acceptance/rejection framework and the "80% rule".

THREE CONSTRUCTION DETAILS THAT CHANGE THE ANSWER

1. THE VALUE AREA EXPANDS TWO ROWS AT A TIME.
   Steidlmayer's construction compares the SUM of the next two rows above the
   developing area against the sum of the two below, and takes the heavier
   PAIR whole. Expanding one row at a time is a different algorithm: it can
   walk into a single fat row on one side and stop where the pair rule would
   have taken a heavier pair on the other. The two give different VAH and VAL
   on identical data, and every other platform implements the pair rule - so a
   one-row version would disagree with Sierra and look broken while being
   internally consistent. Ported from ief/core/amt.py, which reached this the
   hard way.

2. THE PROFILE IS THE CASH SESSION, NOT THE BROKER DAY.
   An index CFD's day closes at 17:00 ET and a 24-hour profile mixes the
   overnight auction into the value area. The 80% rule is a cash-session
   construct: it is about where the day's participants agreed on price.

3. VOLUME AT PRICE IS APPROXIMATED FROM BARS, AND SAYS SO.
   True volume at price needs the tape. From M30 bars the best available is to
   spread each bar's volume across the prices it traded through, weighted
   toward the body. That is an approximation and it widens value areas
   slightly against a tick-built profile. It is stated rather than buried,
   because a VAH quoted to the cent from bar data implies a precision the
   input does not have.

WHAT THE MEASUREMENT SAYS: THE 80% RULE IS 60%, AND 60% IS THE BASE RATE

Measured on 493 SPY cash sessions, 2024-09 to 2026-09. Price opens outside the
prior session's value area, returns, holds for N brackets, and the question is
whether it then reaches the FAR edge before the close:

    acceptance rule          opens outside  never back  setups  traversed  rate
    1 bracket, close inside            313         178     135         79  58.5%
    2 brackets, close inside           313         213     100         60  60.0%
    3 brackets, close inside           313         237      76         46  60.5%
    2 brackets, whole bar inside       313         266      47         22  46.8%

Sixty percent, not eighty, and stable across every variant of the acceptance
rule. Requiring the whole bar inside rather than just the close makes it worse.

But the rate on its own is not the test, because a value area is a region
price is already inside - reaching one of its edges is not a rare event. The
null: enter at a random bar whose close sits inside the value area, pick an
edge at random, and ask the same question.

    setup traversal                60.0%   n=100
    random entry, random edge      54.6%   n=284
    two-proportion z                +0.94   (needs 3.08 at 24 hypotheses)

The setup adds about five points over doing it arbitrarily, and that
difference is not distinguishable from noise.

TRADED, BOTH HALVES LOSE MONEY

    REJECTION  target the far edge, stop 25% of value-area width beyond the
               near edge:  n=96  win 53.1%  expectancy -0.023R  PF 0.94  t -0.25
               15 of those had target and stop both touched in one bar; order
               is unknowable at 30-minute granularity so they scored as losses.

    ACCEPTANCE opened outside and stayed out, stop at the near edge, exit on
               the close:
                 1 confirmation bar   n=266  win 38.7%  +0.160R  PF 1.31  t +1.04
                 2 confirmation bars  n=247  win 44.5%  -0.038R  PF 0.92  t -0.52
                 3 confirmation bars  n=227  win 47.1%  -0.039R  PF 0.90  t -0.53

Nothing clears the threshold, and acceptance degrades as confirmation is
added, which is the wrong direction for a real effect.

The value area itself remains worth computing - VAH, VAL and POC are the
reference levels other strategies and the chart quote against, and that use
does not depend on the auction rules being tradeable. It is the RULES that
failed, not the construct.

CONFIRMED ON IWM, AND THE SPY NUMBER WAS THE HIGH END OF NOISE

The SPY study rested on 493 sessions and 100 setups. IWM supplies 3818
sessions from 2011 and 871 setups, nearly nine times as many:

    IWM   opened outside the prior value area   2404
          setups (returned, held two brackets)   871
          traversed to the far edge              457     52.5%
          null: random entry inside the VA               53.5%   n=2271
          two-proportion z                               -0.50

On the larger sample the setup traverses slightly LESS often than an
arbitrary entry does. SPY's 60.0% against a 54.6% base was the high end of
sampling noise, which its z of +0.94 already implied; IWM puts the point
estimate essentially on the null.

The folklore figure is 80%. Two instruments and 971 setups between them give
52.5% and 60.0%, against base rates of 53.5% and 54.6%.

WHY THIS IS SPY AND QQQ ONLY

A value area is a VOLUME construct. On the broker's OTC index CFDs
real_volume is 0 and only tick_volume exists, so a profile built there marks
where the price feed updated most often, not where size traded. The POC of a
quote-update profile is not a point of control. The DataNeed.TRADED_VOLUME
gate refuses those instruments, and the allowlist below is the second lock.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, Direction, SignalResult,
)
from app.strategies.session_windows import (
    OPENING_RANGE_END, RTH_CLOSE, RTH_OPEN, et_epoch, last_complete_session,
    session_date, to_et,
)

ALLOWED = {"SPY", "QQQ", "IWM", "DIA"}

# Profile bin, as a fraction of the session's range. A fixed tick would give
# ~1200 rows on a quiet SPY session and 40 on a violent one; a fixed row COUNT
# keeps the resolution of the profile constant across regimes, which is what
# makes value areas comparable between sessions.
DEFAULT_ROWS = 60
VALUE_AREA_RATIO = 0.70


def build_profile(high: Sequence[float], low: Sequence[float],
                  close: Sequence[float], open_: Sequence[float],
                  volume: Sequence[float],
                  rows: int = DEFAULT_ROWS) -> tuple[list[float], list[float], float]:
    """Volume at price from bars. Returns (prices, volumes, bin_size).

    Each bar's volume is spread across the rows between its high and low, with
    the body weighted higher than the wicks. Dumping it all at the midpoint -
    the obvious shortcut - collapses a range into one row and produces a
    profile with a spuriously sharp point of control.
    """
    hi = max(high)
    lo = min(low)
    if hi <= lo:
        return [], [], 0.0
    step = (hi - lo) / rows
    if step <= 0:
        return [], [], 0.0

    buckets = [0.0] * (rows + 1)
    for i in range(len(close)):
        v = volume[i]
        if v <= 0:
            continue
        r_lo = max(0, min(rows, int((low[i] - lo) / step)))
        r_hi = max(0, min(rows, int((high[i] - lo) / step)))
        body_lo = min(open_[i], close[i])
        body_hi = max(open_[i], close[i])
        weights = []
        total_w = 0.0
        for r in range(r_lo, r_hi + 1):
            p = lo + (r + 0.5) * step
            w = 1.0 if body_lo <= p <= body_hi else 0.35
            weights.append(w)
            total_w += w
        if total_w <= 0:
            continue
        for k, r in enumerate(range(r_lo, r_hi + 1)):
            buckets[r] += v * weights[k] / total_w

    prices = [lo + (r + 0.5) * step for r in range(rows + 1)]
    return prices, buckets, step


def value_area(prices: Sequence[float], volumes: Sequence[float],
               ratio: float = VALUE_AREA_RATIO
               ) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """(poc, vah, val) by Steidlmayer's two-row expansion.

    Ties on the point of control go to the row nearest the middle of the
    range. Taking the first by index would make the POC depend on which end
    the loop started from, which is not a property of the market.
    """
    total = sum(volumes)
    if not prices or total <= 0:
        return None, None, None

    peak = max(volumes)
    candidates = [i for i, v in enumerate(volumes) if v == peak]
    mid = (len(prices) - 1) / 2
    poc_idx = min(candidates, key=lambda i: abs(i - mid))

    target = total * ratio
    covered = volumes[poc_idx]
    lo_i = hi_i = poc_idx

    while covered < target and (lo_i > 0 or hi_i < len(prices) - 1):
        up = [i for i in (hi_i + 1, hi_i + 2) if i < len(prices)]
        dn = [i for i in (lo_i - 1, lo_i - 2) if i >= 0]
        if not up and not dn:
            break
        up_v = sum(volumes[i] for i in up)
        dn_v = sum(volumes[i] for i in dn)
        # Ties go up, matching the common implementation. Arbitrary, but it has
        # to be decided somewhere or the result depends on iteration order.
        take_up = bool(up) and (up_v >= dn_v or not dn)
        if take_up:
            covered += up_v
            hi_i = up[-1]
        else:
            covered += dn_v
            lo_i = dn[-1]

    return prices[poc_idx], prices[hi_i], prices[lo_i]


class VolumeProfileAuctionStrategy(BaseStrategy):
    """Acceptance outside the prior value area, or rejection back into it.

    Two opposite trades, separated by whether price HOLDS outside the prior
    day's value area or returns into it:

      ACCEPTANCE  - opens outside and stays outside. The market has repriced;
                    trade in the direction of the move.
      REJECTION   - opens outside, comes back in, and holds inside for two
                    brackets. The move was rejected; trade back toward the
                    point of control. This is Dalton's "80% rule".

    The empirical traversal rate is measured rather than assumed - see
    measure_eighty_percent_rule() and the number in the registry.
    """

    name = "vp_auction"
    requires = (DataNeed.OHLC, DataNeed.TRADED_VOLUME, DataNeed.SESSION_TIMES)
    intervals = ("30m", "M30", "15m", "M15")
    validated_on = ()

    def __init__(self, acceptance_brackets: int = 2,
                 rows: int = DEFAULT_ROWS,
                 require_validation: bool = True):
        super().__init__(acceptance_brackets=acceptance_brackets, rows=rows,
                         require_validation=require_validation)
        self.acceptance_brackets = acceptance_brackets
        self.rows = rows
        self.require_validation = require_validation

    def min_bars(self) -> int:
        return 20

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        sym = bars.symbol.upper().replace("=F", "").replace("=X", "")
        if sym not in ALLOWED:
            return SignalResult.abstain(
                self.name, bars.symbol,
                f"VP_INSTRUMENT_NOT_ALLOWED: {bars.symbol} has no traded-volume "
                f"tape on this broker. A profile built on quote counts marks "
                f"where the feed updated, not where size traded.")

        if self.require_validation:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "VP_AUCTION_RULES_NOT_SUPPORTED: the 80% rule measures 60.0% "
                "on 493 SPY sessions against a 54.6% base rate for a random "
                "entry inside the value area - two-proportion z 0.94. Traded, "
                "rejection returns -0.023R (t -0.25) and acceptance -0.038R at "
                "two confirmation bars. The value area itself is still "
                "computed and exported as reference levels.")

        sessions = _split_sessions(bars)
        if len(sessions) < 2:
            return SignalResult.abstain(
                self.name, bars.symbol, "needs a prior complete session")

        prior_day, prior = sessions[-2]
        today_day, today = sessions[-1]

        prices, vols, step = build_profile(
            [bars.high[i] for i in prior], [bars.low[i] for i in prior],
            [bars.close[i] for i in prior], [bars.open[i] for i in prior],
            [bars.volume[i] for i in prior], self.rows)
        poc, vah, val = value_area(prices, vols)
        if poc is None:
            return SignalResult.abstain(
                self.name, bars.symbol, "prior session carried no volume")

        evidence = {"prior_session": prior_day.isoformat(),
                    "poc": poc, "vah": vah, "val": val,
                    "bin_size": step, "rows": self.rows}

        opened = bars.open[today[0]]
        if val <= opened <= vah:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=(f"opened at {opened:.2f}, inside the prior value area "
                        f"{val:.2f}-{vah:.2f}; neither setup applies"),
                evidence=evidence)

        above = opened > vah
        closes = [bars.close[i] for i in today]
        inside = [val <= c <= vah for c in closes]

        accepted_in = _run_of(inside, True, self.acceptance_brackets)
        if accepted_in is not None:
            # Rejection: came back in and held. Target the far side.
            target = val if above else vah
            return SignalResult(
                strategy=self.name, symbol=bars.symbol,
                direction=Direction.SHORT if above else Direction.LONG,
                conviction=0.55,
                entry=closes[-1],
                stop=(vah + (vah - val) * 0.25) if above else (val - (vah - val) * 0.25),
                target=target,
                time_exit_utc=et_epoch(today_day, RTH_CLOSE),
                reason=(f"opened {'above' if above else 'below'} the prior value "
                        f"area and accepted back inside for "
                        f"{self.acceptance_brackets} brackets; target the far "
                        f"edge at {target:.2f}"),
                evidence={**evidence, "mode": "rejection", "opened": opened})

        if not any(inside):
            return SignalResult(
                strategy=self.name, symbol=bars.symbol,
                direction=Direction.LONG if above else Direction.SHORT,
                conviction=0.5,
                entry=closes[-1],
                stop=vah if above else val,
                target=None,
                time_exit_utc=et_epoch(today_day, RTH_CLOSE),
                reason=(f"opened {'above' if above else 'below'} the prior value "
                        f"area and has not traded back inside; the market has "
                        f"repriced"),
                evidence={**evidence, "mode": "acceptance", "opened": opened})

        return SignalResult(
            strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
            reason=("opened outside the prior value area and has touched back "
                    "inside without holding for the acceptance window"),
            evidence={**evidence, "mode": "undecided", "opened": opened})


def _split_sessions(bars: BarSeries) -> list[tuple[object, list[int]]]:
    """Cash-session bar indices, oldest first. RTH only."""
    out: dict = {}
    for i, t in enumerate(bars.time):
        et = to_et(t)
        if not (RTH_OPEN <= et.time() < RTH_CLOSE):
            continue
        out.setdefault(et.date(), []).append(i)
    return sorted(out.items())


def _run_of(flags: Sequence[bool], value: bool, n: int) -> Optional[int]:
    """Index where the first run of `n` consecutive `value` completes."""
    run = 0
    for i, f in enumerate(flags):
        run = run + 1 if f is value else 0
        if run >= n:
            return i
    return None
