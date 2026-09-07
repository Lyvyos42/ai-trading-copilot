"""Internal Bar Strength: where the close sat inside the session's range.

    IBS = (close - low) / (high - low)

REFERENCES
Pagonidis (NAAIM, 2014); Cooper (2006). Both test it on DAILY bars of equity
indices, entering on a weak close and exiting the following session.

THE FINDING THAT CHANGES HOW THIS SHOULD BE DEPLOYED

Measured on 1098 cash sessions of sp500 and 493 of spy, aggregated from M30 to
the 09:30-16:00 session - not to the CFD's 24-hour day, whose close falls at
17:00 ET and would put IBS's defining price in the wrong place.

Splitting the following session into its two legs, with the 200-period regime
filter applied to BOTH groups so that IBS is the only thing separating them:

    sp500                    IBS < 0.2        IBS >= 0.2      Welch t
      overnight  C -> O      +17.8bp n=154    +0.6bp n=679     +3.01
      intraday   O -> C       +3.5bp n=154    +2.5bp n=679     +0.18
      full day   C -> C      +21.4bp n=154    +3.1bp n=679     +2.25

    spy                      IBS < 0.2        IBS >= 0.2      Welch t
      overnight  C -> O      +15.3bp n=42     +5.1bp n=239     +1.09
      intraday   O -> C       +0.5bp n=42     +0.4bp n=239     +0.01

Two things follow, and the second is the one that matters.

FIRST: IBS IS REAL, AND IT IS ENTIRELY AN OVERNIGHT EFFECT. On sp500 the weak
closes earn +17.8bp overnight against +0.6bp for everything else, a Welch t of
3.01 across 833 observations. The intraday leg separates at t=0.18, which is
nothing. So "exit at the next close" is not a variant of this strategy, it is
the same trade with an unpaid day of exposure bolted on.

SECOND: THIS IS THE SAME TRADE AS overnight_drift. Enter on the close, exit on
the next open, gated on the 200-period average - that IS the overnight drift
strategy, with IBS as an extra condition. Registering both as independent
voters would count one edge twice, and a consensus that does that reports
conviction it has not earned. registry.py records the exclusion.

WHY IT IS NOT PROMOTED ON ITS OWN NUMBERS

    sp500  IBS<0.2  Sharpe 1.54  OOS t 1.82  retention 1.29  maxDD -2.9%  exposure 14%
    sp500  IBS<0.3  Sharpe 1.45  OOS t 2.18  retention 1.83  maxDD -5.0%  exposure 20%
    spy    IBS<0.2  Sharpe 1.23  OOS t 1.57  retention 3.09  maxDD -1.4%  exposure  9%
    spy    IBS<0.3  Sharpe 1.68  OOS t 1.99  retention 2.63  maxDD -1.4%  exposure 14%

None clears the 3.08 threshold at the 24 hypotheses tried. The filter is
selective enough that 4.4 years yields only 154 qualifying sessions, and a
standalone t-test on 154 trades has little power. Note also that retention is
ABOVE 1 everywhere - 3.09 on 42 trades - which is not evidence of robustness;
it means the out-of-sample window happened to be the kinder one, and on
samples this small that is luck rather than a result.

The Welch test is the stronger evidence precisely because it uses all 833
sessions rather than the 154 that pass. It says IBS discriminates. It does not
say a strategy built only on IBS clears a corrected bar, and those are
different claims.
"""
from __future__ import annotations

from typing import Optional, Sequence

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, Direction, SignalResult,
)


def internal_bar_strength(high: float, low: float, close: float) -> Optional[float]:
    """Where the close sat in the bar, 0 at the low and 1 at the high.

    A bar with no range has no answer. Returning 0.5 for it - the tempting
    default - would place a doji in the middle of the distribution and make it
    look like an ordinary session, when what actually happened is that nothing
    traded. None is the honest value and the caller skips it.
    """
    if high <= low:
        return None
    return (close - low) / (high - low)


class IBSMeanReversionStrategy(BaseStrategy):
    """Weak close, long overnight, gated on the longer-term trend."""

    name = "ibs_mean_reversion"
    requires = (DataNeed.OHLC, DataNeed.OVERNIGHT_GAP)
    # Daily bars of the CASH SESSION. On 30-minute bars "IBS" would describe
    # where a half hour closed inside itself, which is a different and much
    # noisier quantity than the one the papers measure.
    intervals = ("1d", "1day", "D1", "daily")
    validated_on = ()   # discriminates well; not proven standalone - see above

    def __init__(self, ibs_max: float = 0.2, sma_period: int = 200,
                 require_regime: bool = True, require_validation: bool = True):
        super().__init__(ibs_max=ibs_max, sma_period=sma_period,
                         require_regime=require_regime,
                         require_validation=require_validation)
        self.ibs_max = ibs_max
        self.sma_period = sma_period
        self.require_regime = require_regime
        self.require_validation = require_validation

    def min_bars(self) -> int:
        return self.sma_period + 2 if self.require_regime else 2

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        if self.require_validation:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "IBS_DUPLICATES_OVERNIGHT_DRIFT: the edge is entirely the "
                "overnight leg (Welch t 3.01 against t 0.18 intraday), which "
                "is the trade overnight_drift already makes. Standalone OOS t "
                "is 1.82-2.18 against a 3.08 threshold on 154-218 sessions. "
                "Use ibs_max on OvernightDriftStrategy instead of voting twice.")

        i = len(bars.close) - 1
        ibs = internal_bar_strength(bars.high[i], bars.low[i], bars.close[i])
        if ibs is None:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "session had no range; IBS is undefined")

        evidence = {"ibs": round(ibs, 4), "ibs_max": self.ibs_max}

        sma = self.sma(list(bars.close), self.sma_period)[i] if self.require_regime else None
        if self.require_regime:
            if sma is None:
                return SignalResult.abstain(
                    self.name, bars.symbol,
                    f"regime filter needs {self.sma_period} closed sessions")
            evidence["sma"] = sma
            if bars.close[i] <= sma:
                return SignalResult(
                    strategy=self.name, symbol=bars.symbol,
                    direction=Direction.FLAT,
                    reason=(f"IBS {ibs:.2f} is weak but price is below its "
                            f"{self.sma_period}-session average - a weak close "
                            f"in a downtrend is not the same setup"),
                    evidence=evidence)

        if ibs >= self.ibs_max:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=f"IBS {ibs:.2f} at or above the {self.ibs_max} threshold",
                evidence=evidence)

        return SignalResult(
            strategy=self.name, symbol=bars.symbol, direction=Direction.LONG,
            # Deeper into the range is a stronger reading, but only mildly -
            # the measured effect is a step at the threshold, not a gradient,
            # so the conviction range is deliberately narrow.
            conviction=min(0.8, 0.5 + (self.ibs_max - ibs) * 1.2),
            entry=bars.close[i],
            # No stop, for the same reason as overnight_drift: the position is
            # opened at the close and the market reopens where it reopens.
            stop=None, target=None,
            horizon_bars=1,
            reason=(f"IBS {ibs:.2f} below {self.ibs_max} with price above its "
                    f"{self.sma_period}-session average; hold overnight only"),
            evidence=evidence,
        )


def backtest_ibs(open_: Sequence[float], high: Sequence[float],
                 low: Sequence[float], close: Sequence[float],
                 ibs_max: float = 0.2, sma_period: int = 200,
                 require_regime: bool = True,
                 exit_at: str = "open") -> list[float]:
    """Per-session returns for the harness. Zero on sessions sat out.

    `exit_at="close"` is supported so the choice stays testable, but it was
    measured and the extra day contributes nothing - the intraday leg
    separates at Welch t 0.18. It holds risk for no measured return.
    """
    base = BaseStrategy()
    sma = base.sma(list(close), sma_period)
    out: list[float] = []
    for t in range(1, len(close)):
        j = t - 1
        ibs = internal_bar_strength(high[j], low[j], close[j])
        ok = ibs is not None and ibs < ibs_max
        if ok and require_regime:
            ok = sma[j] is not None and close[j] > sma[j]
        if not ok:
            out.append(0.0)
            continue
        out.append((open_[t] / close[j] - 1.0) if exit_at == "open"
                   else (close[t] / close[j] - 1.0))
    return out
