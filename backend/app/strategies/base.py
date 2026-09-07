"""Shared interface for quantitative strategies.

WHY A STRATEGY DECLARES WHAT DATA IT NEEDS

Every strategy here consumes bars, and bars are not interchangeable. Measured
on this project's own feeds on 2026-09-06:

  * Yahoo publishes NO volume for spot FX - 1440 of 1440 USDJPY 5m bars and
    1422 of 1422 EURUSD bars came back zero. There is no consolidated tape for
    spot FX, so this is structural rather than a gap to retry around.
  * Yahoo's spot FX bars are an indicative composite, not a tape: 24.5% of
    AUDUSD 15m bars OPEN more than half the previous bar's range away from its
    close, against 0.0% on Binance and 0.8% on a real exchange tape.
  * MT5 reports tick_volume - a count of price updates, not contracts.

A VWAP strategy on a feed with no volume is not a degraded VWAP; it is a
moving average wearing VWAP's name, and it will produce signals that look
identical to real ones. So `requires` is declared per strategy and checked
before any signal is emitted. A strategy that cannot be computed honestly
returns ABSTAIN with the reason, and the consensus layer treats that as an
absence of opinion rather than a neutral one.

This mirrors ief/strategies/base.py in Institutional Edge Futures, which
reached the same conclusion from the opposite direction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Sequence


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"


class DataNeed(str, Enum):
    """What a strategy must have before it can speak."""
    OHLC = "ohlc"                    # every feed has this
    TRADED_VOLUME = "traded_volume"  # contracts/shares actually exchanged
    ANY_VOLUME = "any_volume"        # traded OR tick count; a proxy will do
    SESSION_TIMES = "session_times"  # bars must be timestamped and RTH-aligned
    EARNINGS = "earnings"            # actual EPS, consensus, forecast dispersion
    OVERNIGHT_GAP = "overnight_gap"  # a real close-to-open break must exist


@dataclass(frozen=True)
class BarSeries:
    """Bars plus what is known about where they came from.

    `volume_kind` is the field that matters and the one most often missing:
    "traded", "tick_count" or "none". A strategy needing TRADED_VOLUME will
    abstain on "tick_count" rather than quietly treat a count of quote updates
    as size.
    """
    symbol: str
    interval: str
    time: Sequence[int]
    open: Sequence[float]
    high: Sequence[float]
    low: Sequence[float]
    close: Sequence[float]
    volume: Sequence[float]
    volume_kind: str = "none"
    is_continuous: bool = False      # 24/5 or 24/7 - no overnight break exists
    timezone: str = "America/New_York"
    source: str = "unknown"

    def __len__(self) -> int:
        return len(self.close)

    def has_traded_volume(self) -> bool:
        return self.volume_kind == "traded" and any(v > 0 for v in self.volume)

    def has_any_volume(self) -> bool:
        return self.volume_kind in ("traded", "tick_count") and any(v > 0 for v in self.volume)


@dataclass
class SignalResult:
    """One strategy's opinion, or its refusal to have one.

    ABSTAIN is a first-class outcome and is NOT the same as FLAT. Flat says
    "I looked and see nothing"; abstain says "I could not look". Averaging an
    abstention into a consensus as a neutral vote silently dilutes every other
    agent toward 50%, which is how a 9-agent panel ends up reporting 51%
    confidence on a symbol where seven agents had no data.
    """
    strategy: str
    symbol: str
    direction: Direction = Direction.FLAT
    abstained: bool = False
    reason: str = ""
    # 0..1. Only meaningful when not abstained.
    conviction: float = 0.0
    entry: Optional[float] = None
    stop: Optional[float] = None
    target: Optional[float] = None
    # When the position must be closed regardless of price. Several of these
    # strategies are defined by their exit time, not by a level.
    time_exit_utc: Optional[int] = None
    horizon_bars: Optional[int] = None
    evidence: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def abstain(cls, strategy: str, symbol: str, reason: str) -> "SignalResult":
        return cls(strategy=strategy, symbol=symbol, abstained=True, reason=reason)

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy, "symbol": self.symbol,
            "direction": self.direction.value, "abstained": self.abstained,
            "reason": self.reason, "conviction": round(self.conviction, 4),
            "entry": self.entry, "stop": self.stop, "target": self.target,
            "time_exit_utc": self.time_exit_utc, "horizon_bars": self.horizon_bars,
            "evidence": self.evidence,
        }


class BaseStrategy:
    """Subclass, declare `name` and `requires`, implement `_evaluate`."""

    name: str = "base"
    requires: tuple[DataNeed, ...] = (DataNeed.OHLC,)
    # Instruments the published research actually covers. A strategy measured
    # on cash equity indices has not been measured on EURUSD, and running it
    # there is a new hypothesis, not a deployment.
    validated_on: tuple[str, ...] = ()

    def __init__(self, **params):
        self.params = params

    def generate_signals(self, bars: BarSeries) -> SignalResult:
        gate = self._check_requirements(bars)
        if gate is not None:
            return gate
        return self._evaluate(bars)

    def _check_requirements(self, bars: BarSeries) -> Optional[SignalResult]:
        if len(bars) < self.min_bars():
            return SignalResult.abstain(
                self.name, bars.symbol,
                f"needs {self.min_bars()} bars, has {len(bars)}")

        for need in self.requires:
            if need is DataNeed.TRADED_VOLUME and not bars.has_traded_volume():
                return SignalResult.abstain(
                    self.name, bars.symbol,
                    f"needs traded volume; {bars.source} reports "
                    f"volume_kind={bars.volume_kind!r} for {bars.symbol}")
            if need is DataNeed.ANY_VOLUME and not bars.has_any_volume():
                return SignalResult.abstain(
                    self.name, bars.symbol,
                    f"needs volume of some kind; {bars.source} publishes none "
                    f"for {bars.symbol}")
            if need is DataNeed.OVERNIGHT_GAP and bars.is_continuous:
                return SignalResult.abstain(
                    self.name, bars.symbol,
                    f"{bars.symbol} trades continuously, so there is no "
                    f"overnight close-to-open break to trade")
        return None

    def min_bars(self) -> int:
        return 2

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        raise NotImplementedError

    # Convenience for subclasses -------------------------------------------

    @staticmethod
    def sma(values: Sequence[float], n: int) -> list[Optional[float]]:
        out: list[Optional[float]] = [None] * len(values)
        if len(values) < n:
            return out
        run = sum(values[:n])
        out[n - 1] = run / n
        for i in range(n, len(values)):
            run += values[i] - values[i - n]
            out[i] = run / n
        return out

    @staticmethod
    def rsi(values: Sequence[float], n: int = 14) -> list[Optional[float]]:
        """Wilder's RSI. Seeded on the first n changes, then smoothed."""
        out: list[Optional[float]] = [None] * len(values)
        if len(values) <= n:
            return out
        gain = loss = 0.0
        for i in range(1, n + 1):
            ch = values[i] - values[i - 1]
            gain += max(ch, 0.0)
            loss += max(-ch, 0.0)
        gain /= n
        loss /= n
        out[n] = 100.0 - 100.0 / (1.0 + (gain / loss if loss else 1e9))
        for i in range(n + 1, len(values)):
            ch = values[i] - values[i - 1]
            gain = (gain * (n - 1) + max(ch, 0.0)) / n
            loss = (loss * (n - 1) + max(-ch, 0.0)) / n
            out[i] = 100.0 - 100.0 / (1.0 + (gain / loss if loss else 1e9))
        return out

    @staticmethod
    def atr(high: Sequence[float], low: Sequence[float],
            close: Sequence[float], n: int = 14) -> list[Optional[float]]:
        out: list[Optional[float]] = [None] * len(close)
        trs: list[float] = []
        for i in range(1, len(close)):
            trs.append(max(high[i] - low[i],
                           abs(high[i] - close[i - 1]),
                           abs(low[i] - close[i - 1])))
            if len(trs) >= n:
                out[i] = sum(trs[-n:]) / n
        return out
