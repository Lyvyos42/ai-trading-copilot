"""institutional_vwap: session-anchored VWAP, 2-sigma pierce-and-reject back to VWAP.

SOURCE

Institutional Edge core/research_strategies/institutional_vwap.py, the module armed
there as CANDIDATE. Its registry record is explicit that it is NOT BACKTESTED: an
execution benchmark whose value is the reference level, not a measured directional
edge. This port reproduces that module's rule exactly so the two systems cannot
disagree about the same bar, and the registry weight here reflects the same limit.

    anchor     09:30 America/New_York; accumulate 09:30-16:00 only
    VWAP       cumulative sum(typical * volume) / sum(volume), typical = (H+L+C)/3
    sigma      volume-weighted: sqrt(sum(v * typical^2) / sum(v) - VWAP^2)
    window     signals only on bars starting 10:00-15:30
    LONG       close[i-1] <  VWAP[i] - 2 sigma[i]  and  close[i] >= that band
    SHORT      close[i-1] >  VWAP[i] + 2 sigma[i]  and  close[i] <= that band
    target     VWAP[i]
    stop       0.5 sigma beyond the 2-sigma band, i.e. 2.5 sigma from VWAP
    geometry   the setup is DECLINED when price already sits past VWAP or the stop
               is inverted (the SPYG 2026-09-11 defect: BUY 121.12 with target 120.94)

The bands are volume-weighted SIGMA, not ATR. Nothing in the source uses ATR bands.

THE LONDON ANCHOR IS A SEPARATE, UNTESTED HYPOTHESIS

`anchor="london"` (08:00-16:00 Europe/London, signals 08:30-15:30) exists for FX
and gold. The source module never ran it. It is registered as an observer and
cannot vote.

VOLUME IS REQUIRED, AND MUST BE TRADED VOLUME

A VWAP without traded volume is a moving average of typical price under another
name. Spot FX has no consolidated tape and CFD feeds report quote counts. For FX
and gold the bar loader supplies the CME contract's tape (6E, 6B, 6A, GC) shifted
onto spot, and marks volume_kind accordingly; a series without traded volume
abstains through DataNeed.TRADED_VOLUME before this rule runs.
"""
from __future__ import annotations

import math
from datetime import datetime, time as dtime
from typing import Optional
from zoneinfo import ZoneInfo

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, Direction, SignalResult,
)

BAND_SIGMA = 2.0
STOP_BEYOND_BAND_SIGMA = 0.5

ANCHORS = {
    "ny_rth": {"tz": ZoneInfo("America/New_York"), "open": dtime(9, 30),
               "close": dtime(16, 0), "win_start": dtime(10, 0), "win_end": dtime(15, 30)},
    "london": {"tz": ZoneInfo("Europe/London"), "open": dtime(8, 0),
               "close": dtime(16, 0), "win_start": dtime(8, 30), "win_end": dtime(15, 30)},
}

# Symbols for which a traded-volume tape can exist. Membership is necessary, not
# sufficient: the series must also arrive with volume_kind == "traded".
ALLOWED = {
    "ES", "NQ", "YM", "RTY", "MES", "MNQ", "MYM", "M2K",
    "SPY", "QQQ", "DIA", "IWM", "US30",
    "6E", "6B", "6A", "6J", "GC", "MGC",
    "XAUUSD", "EURUSD", "GBPUSD", "AUDUSD", "USDJPY",
}
INVERTED_VS_SPOT = {"6J"}


def _root(symbol: str) -> str:
    return (symbol or "").upper().replace("=F", "").replace("=X", "").replace("/", "").strip()


class InstitutionalVWAPStrategy(BaseStrategy):
    name = "institutional_vwap"
    requires = (DataNeed.OHLC, DataNeed.TRADED_VOLUME, DataNeed.SESSION_TIMES)
    validated_on = ()          # not backtested anywhere - see module docstring
    intervals = ("5m", "15m", "30m")

    def __init__(self, anchor: str = "ny_rth"):
        if anchor not in ANCHORS:
            raise ValueError(f"anchor must be one of {sorted(ANCHORS)}, got {anchor!r}")
        super().__init__(anchor=anchor)
        self.anchor = anchor

    def min_bars(self) -> int:
        return 20

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        sym = _root(bars.symbol)
        if sym not in ALLOWED:
            return SignalResult.abstain(
                self.name, bars.symbol,
                f"VWAP_INSTRUMENT_NOT_ALLOWED: {bars.symbol} has no traded-volume tape")

        a = ANCHORS[self.anchor]
        tz = a["tz"]
        loc = [datetime.fromtimestamp(float(t), tz=tz) for t in bars.time]
        n = len(loc)
        last_day = loc[-1].date()

        # Cumulative session VWAP and volume-weighted variance, per bar, for the
        # session containing the last bar. Earlier sessions cannot influence it.
        vwap = [None] * n
        sd = [None] * n
        cv = cvp = cvp2 = 0.0
        session_bars = 0
        for i in range(n):
            if loc[i].date() != last_day:
                continue
            t = loc[i].time()
            if not (a["open"] <= t <= a["close"]):
                continue
            v = float(bars.volume[i])
            if v <= 0:
                continue
            tp = (bars.high[i] + bars.low[i] + bars.close[i]) / 3.0
            cv += v
            cvp += tp * v
            cvp2 += tp * tp * v
            session_bars += 1
            m = cvp / cv
            vwap[i] = m
            sd[i] = math.sqrt(max(0.0, cvp2 / cv - m * m))

        i = n - 1
        ev = {"anchor": self.anchor, "session": last_day.isoformat(),
              "session_bars": session_bars, "volume_kind": bars.volume_kind,
              "source": bars.source, "band_sigma": BAND_SIGMA,
              "registry_record": "NOT BACKTESTED - execution benchmark",
              "quoted_inverse_of_spot": sym in INVERTED_VS_SPOT}

        if vwap[i] is None or sd[i] is None:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=(f"last bar is outside the {self.anchor} cash session or carries "
                        f"no volume; no anchored VWAP to read"),
                evidence=ev)

        m, s = vwap[i], sd[i]
        u2, l2 = m + BAND_SIGMA * s, m - BAND_SIGMA * s
        px, prev = float(bars.close[i]), float(bars.close[i - 1])
        ev.update({"vwap": m, "sigma": s, "upper_2": u2, "lower_2": l2,
                   "z": ((px - m) / s) if s > 0 else None})

        t_last = loc[i].time()
        in_window = a["win_start"] <= t_last <= a["win_end"]
        same_session = loc[i - 1].date() == last_day
        if not in_window or not same_session or s <= 0:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=(f"bar at {t_last:%H:%M} is outside the "
                        f"{a['win_start']:%H:%M}-{a['win_end']:%H:%M} signal window"
                        if not in_window else "no prior bar in this session to pierce from"),
                evidence=ev)

        side = 0
        if prev < l2 and px >= l2:
            side = 1
        elif prev > u2 and px <= u2:
            side = -1
        if side == 0:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=f"no 2-sigma pierce-and-reject on this bar (z {ev['z']:+.2f})",
                evidence=ev)

        stop = (l2 - STOP_BEYOND_BAND_SIGMA * s) if side > 0 else (u2 + STOP_BEYOND_BAND_SIGMA * s)
        target = m
        coherent = ((side > 0 and px < target and stop < px) or
                    (side < 0 and px > target and stop > px))
        if not coherent:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=("DECLINED: pierce-and-reject fired but price is already past VWAP "
                        "or the stop is inverted - an incoherent setup is not emitted"),
                evidence={**ev, "declined_stop": stop, "declined_target": target})

        close_dt = datetime.combine(last_day, a["close"], tzinfo=tz)
        direction = Direction.LONG if side > 0 else Direction.SHORT
        band = "lower" if side > 0 else "upper"
        return SignalResult(
            strategy=self.name, symbol=bars.symbol, direction=direction,
            conviction=1.0,
            entry=px, stop=stop, target=target,
            time_exit_utc=int(close_dt.timestamp()),
            reason=(f"pierced and closed back inside the {band} 2-sigma VWAP band "
                    f"({prev:.5g} -> {px:.5g}, band {l2 if side > 0 else u2:.5g}); "
                    f"target VWAP {m:.5g}, stop at 2.5 sigma {stop:.5g}"),
            evidence={**ev, "mode": "pierce_and_reject"})
