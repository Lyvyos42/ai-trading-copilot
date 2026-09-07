"""Session-anchored VWAP with standard deviation bands: two modes.

WHY THE INSTRUMENT LIST IS AN ALLOWLIST AND NOT A GUIDELINE

VWAP is a volume-weighted average. Without volume it is not a degraded VWAP,
it is an arithmetic mean of typical price - a moving average wearing VWAP's
name - and it will emit signals indistinguishable from real ones. Measured on
this project's feeds on 2026-09-06:

    Yahoo USDJPY=X 5m   volume on    0 of 1440 bars
    Yahoo EURUSD=X 5m   volume on    0 of 1422 bars
    MT5 FX              tick_volume: a count of quote updates, not contracts

So the allowlist below is enforced in code and a symbol outside it abstains.
An instrument's presence on the list is a statement that a real traded-volume
tape exists for it, nothing more.

THE 6E/6B/6J ENTRY IS THE CME CONTRACT, NOT THE SPOT PAIR
6J is quoted as JPY per USD - the reciprocal of USDJPY - so a signal computed
on 6J is not directly a signal on USDJPY without inverting the direction. That
inversion is the caller's job and is flagged in the evidence rather than done
silently here.

THE TWO MODES ARE OPPOSITE TRADES AND MUST NOT BOTH FIRE

    Trend continuation: price holds beyond VWAP with participation rising.
    Mean reversion:     price stretches past a band on THINNING participation
                        and is expected back to VWAP.

The distinguishing variable is not distance, it is whether volume confirms the
move. A stretch on heavy volume is a trend; the same stretch on light volume
is an overshoot. Deciding on distance alone gives a strategy that buys
breakouts and fades them at the same price, which nets to noise and a lot of
commission. `volume_ratio` is what separates them, and when it is ambiguous
this returns FLAT rather than picking.

RAW VWAP CROSSES ARE NOT TRADED
A cross of the line itself fires constantly in chop, which is the standard
criticism of naive VWAP systems and the reason the bands exist. Entries are at
the bands; VWAP is the target, not the trigger.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, Direction, SignalResult,
)
from app.strategies.session_windows import (
    RTH_CLOSE, RTH_OPEN, et_epoch, last_complete_session, session_date,
)

# Instruments with a real traded-volume tape. Nothing else is permitted.
ALLOWED = {
    # equity index futures and their ETFs
    "ES", "ES=F", "NQ", "NQ=F", "SPY", "QQQ", "MES", "MES=F", "MNQ", "MNQ=F",
    # CME FX contracts - the contract, not the spot pair
    "6E", "6E=F", "6B", "6B=F", "6J", "6J=F",
}
# Contracts quoted as the reciprocal of the conventional spot pair.
INVERTED_VS_SPOT = {"6J", "6J=F"}


class InstitutionalVWAPStrategy(BaseStrategy):
    name = "institutional_vwap"
    requires = (DataNeed.OHLC, DataNeed.TRADED_VOLUME, DataNeed.SESSION_TIMES)
    validated_on = ("ES=F", "NQ=F", "SPY", "QQQ")

    def __init__(self,
                 reversion_sigma: float = 1.5,
                 trend_sigma: float = 1.0,
                 volume_lookback: int = 20,
                 trend_volume_ratio: float = 1.2,
                 reversion_volume_ratio: float = 0.8,
                 atr_period: int = 14,
                 min_atr_bp: float = 3.0,
                 min_session_fraction: float = 0.25,
                 min_session_bars_floor: int = 4):
        super().__init__(reversion_sigma=reversion_sigma, trend_sigma=trend_sigma,
                         volume_lookback=volume_lookback,
                         trend_volume_ratio=trend_volume_ratio,
                         reversion_volume_ratio=reversion_volume_ratio,
                         atr_period=atr_period, min_atr_bp=min_atr_bp)
        self.reversion_sigma = reversion_sigma
        self.trend_sigma = trend_sigma
        self.volume_lookback = volume_lookback
        self.trend_volume_ratio = trend_volume_ratio
        self.reversion_volume_ratio = reversion_volume_ratio
        self.atr_period = atr_period
        self.min_atr_bp = min_atr_bp
        # How far into the session the VWAP must be before it means anything,
        # as a FRACTION of a session rather than a bar count. A fixed count is
        # interval-dependent in the worst way: 12 bars is half an hour on 5m
        # data and, on 1h data, more bars than a cash session contains - so
        # the strategy abstained on every 1h series, permanently, and looked
        # like it was working.
        self.min_session_fraction = min_session_fraction
        self.min_session_bars_floor = min_session_bars_floor

    def min_bars(self) -> int:
        return max(self.volume_lookback, self.atr_period) + 2

    @staticmethod
    def _root(symbol: str) -> str:
        return (symbol or "").upper().strip()

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        sym = self._root(bars.symbol)
        if sym not in ALLOWED:
            return SignalResult.abstain(
                self.name, bars.symbol,
                f"VWAP_INSTRUMENT_NOT_ALLOWED: {bars.symbol} is not on the "
                f"traded-volume allowlist. Spot FX publishes no volume and MT5 "
                f"reports quote counts; a VWAP on either is a moving average "
                f"under another name.")

        day = last_complete_session(bars.time)
        if day is None:
            return SignalResult.abstain(self.name, bars.symbol, "no bars")

        idx = [i for i, t in enumerate(bars.time) if session_date(t) == day]
        # Yahoo appends a zero-volume stub at 16:00 - the closing bucket, with
        # a price and no trades. It is the LAST bar, so it is the one every
        # "current bar" calculation lands on, and participation measured
        # against it is measured against nothing. Trailing bars that did not
        # trade are dropped rather than evaluated.
        while idx and bars.volume[idx[-1]] <= 0:
            idx.pop()
        if not idx:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "no bar in this session carries volume")
        needed = self._min_bars_for_session(bars, day)
        if len(idx) < needed:
            return SignalResult.abstain(
                self.name, bars.symbol,
                f"only {len(idx)} of a typical {needed} bars into the session; "
                f"VWAP is not yet anchored on enough volume to mean anything")

        vwap, sigma = self._session_vwap(bars, idx)
        if vwap is None or sigma is None or sigma <= 0:
            return SignalResult.abstain(
                self.name, bars.symbol, "no volume traded in this session yet")

        last = idx[-1]
        price = bars.close[last]
        z = (price - vwap) / sigma

        atr = self.atr(bars.high, bars.low, bars.close, self.atr_period)[last]
        atr_bp = (atr / price * 1e4) if (atr and price) else 0.0

        vol_ratio = self._volume_ratio(bars, last)

        evidence = {
            "vwap": vwap, "sigma": sigma, "z": z,
            "atr_bp": atr_bp, "volume_ratio": vol_ratio,
            "session_bars": len(idx), "session": day.isoformat(),
            "quoted_inverse_of_spot": sym in INVERTED_VS_SPOT,
        }

        # Flat tape. Bands computed on a session that has barely moved are
        # narrow enough that any tick clears them, which is how a VWAP system
        # ends up trading the pre-market and the lunch hour.
        if atr_bp < self.min_atr_bp:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=(f"ATR {atr_bp:.1f}bp under the {self.min_atr_bp:.0f}bp "
                        f"floor - too flat to distinguish a move from noise"),
                evidence=evidence)

        if vol_ratio is None:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "no volume history to compare participation against")

        # --- mean reversion: stretched AND participation thinning -----------
        if abs(z) >= self.reversion_sigma and vol_ratio <= self.reversion_volume_ratio:
            direction = Direction.SHORT if z > 0 else Direction.LONG
            stop_z = self.reversion_sigma + 1.0
            stop = vwap + math.copysign(stop_z * sigma, z)
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=direction,
                conviction=min(0.85, 0.45 + (abs(z) - self.reversion_sigma) * 0.2),
                entry=price, stop=stop, target=vwap,
                time_exit_utc=et_epoch(day, RTH_CLOSE),
                reason=(f"{abs(z):.2f} sigma from VWAP on {vol_ratio:.2f}x "
                        f"participation - an overshoot, not a trend; target VWAP"),
                evidence={**evidence, "mode": "mean_reversion"})

        # --- trend continuation: beyond the inner band AND volume rising ----
        if abs(z) >= self.trend_sigma and vol_ratio >= self.trend_volume_ratio:
            direction = Direction.LONG if z > 0 else Direction.SHORT
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=direction,
                conviction=min(0.85, 0.45 + (vol_ratio - self.trend_volume_ratio) * 0.3),
                entry=price,
                # Losing VWAP invalidates a move that was defined by holding it.
                stop=vwap,
                target=price + math.copysign(2.0 * abs(price - vwap), z),
                time_exit_utc=et_epoch(day, RTH_CLOSE),
                reason=(f"{abs(z):.2f} sigma beyond VWAP on {vol_ratio:.2f}x "
                        f"participation - volume confirms the move"),
                evidence={**evidence, "mode": "trend_continuation"})

        # Stretched but the volume does not say which trade this is. Both modes
        # would fire on distance alone, in opposite directions.
        if abs(z) >= self.trend_sigma:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=(f"{abs(z):.2f} sigma from VWAP but participation "
                        f"{vol_ratio:.2f}x is between the reversion "
                        f"({self.reversion_volume_ratio}) and trend "
                        f"({self.trend_volume_ratio}) thresholds - the volume "
                        f"does not say whether this is a trend or an overshoot"),
                evidence={**evidence, "mode": "ambiguous"})

        return SignalResult(
            strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
            reason=f"{abs(z):.2f} sigma from VWAP - inside the bands",
            evidence={**evidence, "mode": "inside_bands"})

    def _min_bars_for_session(self, bars: BarSeries, day) -> int:
        """Bars required, measured against how long a session actually is.

        Taken from the most recent COMPLETE prior session in the series, so it
        adapts to the bar interval instead of assuming one.
        """
        counts: dict = {}
        for t in bars.time:
            d = session_date(t)
            if d < day:
                counts[d] = counts.get(d, 0) + 1
        if not counts:
            return self.min_session_bars_floor
        typical = counts[max(counts)]
        return max(self.min_session_bars_floor,
                   int(typical * self.min_session_fraction))

    def _session_vwap(self, bars: BarSeries,
                      idx: Sequence[int]) -> tuple[Optional[float], Optional[float]]:
        """Anchored VWAP and the volume-weighted standard deviation about it.

        The deviation is weighted the same way the mean is. Using an unweighted
        standard deviation of price around a volume-weighted mean mixes two
        different averages and gives bands that do not correspond to the line
        they are drawn around.
        """
        pv = 0.0
        vol = 0.0
        for i in idx:
            typical = (bars.high[i] + bars.low[i] + bars.close[i]) / 3.0
            v = bars.volume[i]
            if v <= 0:
                continue
            pv += typical * v
            vol += v
        if vol <= 0:
            return None, None
        vwap = pv / vol

        var = 0.0
        for i in idx:
            typical = (bars.high[i] + bars.low[i] + bars.close[i]) / 3.0
            v = bars.volume[i]
            if v <= 0:
                continue
            var += v * (typical - vwap) ** 2
        return vwap, math.sqrt(var / vol)

    def _volume_ratio(self, bars: BarSeries, last: int) -> Optional[float]:
        """Current bar's volume against the median of the previous N.

        Median, not mean: one spike would raise a mean enough to hide the next
        one, and participation regime is exactly what this is trying to read.
        """
        start = max(0, last - self.volume_lookback)
        hist = [bars.volume[i] for i in range(start, last) if bars.volume[i] > 0]
        if len(hist) < 5 or bars.volume[last] <= 0:
            return None
        hist.sort()
        med = hist[len(hist) // 2]
        return (bars.volume[last] / med) if med > 0 else None
