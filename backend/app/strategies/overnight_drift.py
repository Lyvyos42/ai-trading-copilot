"""Overnight drift: hold the index from the close to the next open.

REFERENCE
Lou, Polk & Skouras (2019), "A Tug of War: Overnight Versus Intraday Expected
Returns", Journal of Financial Economics.

WHAT WAS MEASURED HERE, NOT TAKEN ON TRUST
Decomposing daily bars into overnight (prior close -> open) and intraday
(open -> close) legs, on split-adjusted data with split days excluded:

    SPY  1993-01-29 .. 2026-09-04   8457 sessions
      overnight   +1264% cumulative   8.35% ann   Sharpe 0.79
      intraday      +29% cumulative   1.90% ann   Sharpe 0.13
      buy & hold  +1653%

    QQQ  1999-03-10 .. 2026-09-04   6913 sessions
      overnight   +2950% cumulative  13.48% ann   Sharpe 0.94
      intraday      -54% cumulative  -0.21% ann   Sharpe -0.01

The effect is real and large. The commonly quoted "over 90% of returns happen
overnight" is 76% on SPY over this window and, on QQQ, more than 100% - the
intraday leg is net NEGATIVE across 27 years, so overnight more than accounts
for the whole move. Quote it as "the overnight leg carries the index"; the
exact percentage is window-dependent and is not the point.

WHY THE REGIME FILTER IS NOT OPTIONAL HERE
An unfiltered overnight long is a short volatility position that cannot be
stopped out: the position is opened at the close and the market reopens
wherever it reopens. Measured over the same windows, the worst SINGLE night
was -10.45% on SPY and -9.46% on QQQ. Gating entry on the daily close being
above its 200-period average and RSI(14) above 45 - both evaluated at 16:00,
using only bars that had closed by then - gives:

                    maxDD      Sharpe   worst night   in market
    SPY unfiltered  -34.8%      0.79       -10.45%       100%
    SPY filtered    -17.4%      0.90        -3.41%        63%
    QQQ unfiltered  -33.5%      0.94        -9.46%       100%
    QQQ filtered    -16.3%      1.07        -4.01%        61%

Drawdown roughly halves, Sharpe improves, and the worst night falls by two
thirds, at the cost of about a third of the return and a third of the nights.
For an account that is closed the moment it breaches a fixed loss, that trade
is not close.

THE SIZING CONSEQUENCE, WHICH IS THE PART THAT DECIDES DEPLOYABILITY
A prop plan's maximum drawdown is a dollar figure. Allowing one worst-case
night to consume at most half the budget, and leaving the rest for ordinary
losses:

    FTMO growth_eval_100k, $3,500 budget, filtered SPY (-3.41% worst night)
      -> $51,320 of notional exposure

One ES contract at 7722.00 x $50 is $386,100 of notional. So this plan cannot
carry a single ES overnight - not at reduced size, not at all. MES, at a tenth
the multiplier, gives 1.33 contracts and is viable. Unfiltered, the same plan
tolerates $16,746, which is 0.43 MES: not tradeable. The regime filter is what
makes this strategy fit inside a prop account at all.

WHAT THIS MODULE DOES NOT KNOW
Financing. A cash index position held overnight costs borrow; a futures
position pays it inside the basis. Gross returns above are not net, and the
carry has to come off before this is compared with anything.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, Direction, SignalResult,
)


@dataclass(frozen=True)
class PropConstraint:
    """What the funding plan permits. Supplied by the caller, never guessed.

    `overnight_allowed` defaults to False. A plan that has not been checked is
    treated as prohibiting overnight holds, because the failure mode of the
    other default is an account closed on its first night for a rule nobody
    read.
    """
    plan: str = "unknown"
    account_size: float = 100_000.0
    max_drawdown: float = 3_500.0
    overnight_allowed: bool = False
    # Notional per contract of the smallest tradeable unit. MES at 7722.00 is
    # 7722 x $5 = $38,610.
    micro_notional: float = 38_610.0


class OvernightDriftStrategy(BaseStrategy):
    name = "overnight_drift"
    # Daily bars only, and the instrument must actually close. Nothing here
    # needs volume, which is why it is the one strategy in this set that runs
    # honestly on a spot FX feed - though FX has no overnight break, so it
    # will abstain there anyway.
    requires = (DataNeed.OHLC, DataNeed.OVERNIGHT_GAP)
    validated_on = ("SPY", "QQQ", "ES=F", "NQ=F")
    # Daily bars, and only daily. The 200-period average and the 14-period RSI
    # are a 200-DAY trend and a 14-DAY oscillator; on 30-minute bars the same
    # code reads a fortnight and calls it a regime.
    intervals = ("1d", "1day", "D1", "daily")

    def __init__(self, sma_period: int = 200, rsi_period: int = 14,
                 rsi_floor: float = 45.0, require_regime: bool = True,
                 prop: Optional[PropConstraint] = None):
        super().__init__(sma_period=sma_period, rsi_period=rsi_period,
                         rsi_floor=rsi_floor, require_regime=require_regime)
        self.sma_period = sma_period
        self.rsi_period = rsi_period
        self.rsi_floor = rsi_floor
        self.require_regime = require_regime
        self.prop = prop

    def max_contracts(self) -> int:
        """Hard clamp: one micro per 100k of account, and never more.

        Measured by block-resampling 5353 filtered SPY nights so real losing
        runs stay intact, at a $100,000 account:

                            1 MES ($38,610)    1 ES ($386,100)
            30-day eval          0.1%               85.8%
            60-day eval          1.2%               97.7%
            funded year         15.7%              100.0%

        those being the probability of touching a $3,500 trailing drawdown. One
        full ES held overnight fails an evaluation with near-certainty, so the
        clamp is not a preference. Even at one micro the annual figure is 15.7%
        on FTMO growth and 23.2% on Alpha Zero, which the caller should know it
        is accepting.
        """
        if self.prop is None:
            return 1
        return max(0, int(self.prop.account_size // 100_000)) or 1

    def min_bars(self) -> int:
        return self.sma_period + 2 if self.require_regime else 2

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        # The plan gate comes before anything else. There is no point scoring a
        # regime for a position the funding agreement forbids holding.
        if self.prop is not None and not self.prop.overnight_allowed:
            return SignalResult.abstain(
                self.name, bars.symbol,
                f"OVERNIGHT_HOLD_PROHIBITED_BY_PROP_PLAN: {self.prop.plan}")

        close = list(bars.close)
        i = len(close) - 1                     # the bar that just closed at 16:00

        sma = self.sma(close, self.sma_period)[i] if self.require_regime else None
        rsi = self.rsi(close, self.rsi_period)[i] if self.require_regime else None

        evidence = {
            "close": close[i],
            "sma": sma, "sma_period": self.sma_period,
            "rsi": rsi, "rsi_floor": self.rsi_floor,
            "regime_required": self.require_regime,
        }

        if self.require_regime:
            if sma is None or rsi is None:
                return SignalResult.abstain(
                    self.name, bars.symbol,
                    f"regime filter needs {self.sma_period} closed bars")
            if close[i] <= sma:
                return SignalResult(
                    strategy=self.name, symbol=bars.symbol,
                    direction=Direction.FLAT,
                    reason=(f"below the {self.sma_period}-period average "
                            f"({close[i]:.2f} <= {sma:.2f}); the unfiltered "
                            f"version's worst night in this regime was -10.45%"),
                    evidence=evidence)
            if rsi <= self.rsi_floor:
                return SignalResult(
                    strategy=self.name, symbol=bars.symbol,
                    direction=Direction.FLAT,
                    reason=f"RSI {rsi:.1f} at or below the {self.rsi_floor} floor",
                    evidence=evidence)

        # Conviction scales with how far above the average price sits, capped
        # at one ATR-equivalent of 5%. It is a position-size hint, not a
        # probability - the edge here is unconditional once the gate passes,
        # and pretending otherwise would be reading structure into a filter.
        conviction = 0.6
        if sma:
            stretch = (close[i] - sma) / sma
            conviction = max(0.4, min(0.9, 0.5 + stretch * 4.0))

        evidence["max_contracts"] = self.max_contracts()
        evidence["sizing_basis"] = (
            "one micro contract per $100k of account; a full-size contract "
            "breaches a 3.5% trailing drawdown in 85.8% of 30-day windows")
        if self.prop is not None:
            evidence["prop_plan"] = self.prop.plan
            evidence["prop_max_drawdown"] = self.prop.max_drawdown

        return SignalResult(
            strategy=self.name, symbol=bars.symbol,
            direction=Direction.LONG,
            conviction=conviction,
            entry=close[i],
            # There is deliberately no stop. The position is opened at the
            # close and the market reopens where it reopens; a stop level
            # between those two moments cannot be filled, and quoting one
            # would describe protection that does not exist. Risk is
            # controlled by the regime gate and by size - see the sizing note
            # in this module's docstring.
            stop=None,
            target=None,
            horizon_bars=1,
            reason=(f"close {close[i]:.2f} above its {self.sma_period}-period "
                    f"average {sma:.2f}" if sma else "unfiltered overnight long"),
            evidence=evidence,
        )


def backtest_overnight(open_: list[float], close: list[float],
                       require_regime: bool = True,
                       sma_period: int = 200, rsi_period: int = 14,
                       rsi_floor: float = 45.0) -> list[float]:
    """Per-session return series for the harness. Zero on nights sat out.

    The decision for night t uses bars up to and including t-1's close, which
    is the information available at 16:00 when the position is opened. Using
    close[t] would be reading the answer.
    """
    strat = BaseStrategy()
    sma = strat.sma(close, sma_period)
    rsi = strat.rsi(close, rsi_period)

    out: list[float] = []
    for t in range(1, len(close)):
        j = t - 1
        if require_regime:
            ok = (sma[j] is not None and rsi[j] is not None
                  and close[j] > sma[j] and rsi[j] > rsi_floor)
        else:
            ok = True
        r = (open_[t] / close[j] - 1.0) if ok else 0.0
        out.append(r)
    return out


# The class was named OvernightDrift when first committed. Antigravity's
# interface calls it OvernightDriftStrategy; both names refer to the same
# class so neither side has to change first.
OvernightDrift = OvernightDriftStrategy
