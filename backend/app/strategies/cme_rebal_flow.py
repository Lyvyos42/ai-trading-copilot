"""cme_rebal_flow: mandated month-end rebalancing flow, signed by intra-month divergence.

SOURCE AND STATUS

prereg/CME_REBAL_FLOW_01.md, run by _cme_rebal_flow.py. Registry status CANDIDATE:
edge +30.06 bp per event, 95% CI [+1.89, +58.23], net t +2.34, z +2.63 against a
1,000-draw sign-permutation null, Control C (mid-month placebo) passes, Gate 4
fails on one era (2020-23, t -0.24). Validated on ES, YM and RTY futures
2010-2023, replicated on 368 SPY months 1993-2023.

THIS FILE IMPLEMENTS THE REGISTERED RULE AND NOTHING ELSE

Every number in that record belongs to the frozen specification. A variant with
a z threshold, a take-profit or a stop would be a different strategy with no
measurement behind it, so none of those exist here:

    signal     S = ln(C[s_{K-4}] / C[s_0])         close of the 5th-to-last session
               sigma = sd(daily log returns, 60 sessions ending s_{K-5})  ddof=1
               L = sessions of the month up to and including s_{K-4}
               z = S / (sigma * sqrt(L))
    trade      side -sign(z), size |clip(z, -2, 2)| / 2 - NO threshold, every month fires
    entry      open of s_{K-3}, the 4th-to-last session
    exit       settlement of s_K, the last session - a TIME exit
    levels     none. The registered rule has no stop and no target.

THE SESSION COUNT K COMES FROM THE PUBLISHED HOLIDAY SCHEDULE, NEVER FROM BARS

Knowing which session is the 5th-to-last requires knowing how many sessions the
month will have. Counting rows in the price data is look-ahead. K is taken from
ief/calendar_daemon.py over ief/data/exchange_holidays.csv - the same grid the
execution daemon uses - which raises rather than guesses when the schedule does
not reach far enough forward.

THE VOLATILITY WINDOW MATCHES THE HARNESS, NOT THE LIVE DAEMON

_cme_rebal_flow.py computes `rolling(60).std().shift(1)`: the window ends the
session BEFORE formation. ief/service.py passes closes through the formation date
and so includes the formation-day return. The harness is what produced the
measured edge, so the harness definition is reproduced here.

PURE SIGNAL. No broker, account, contract sizing or financing is computed. The
volatility-target weight is reported in evidence as the registered formula only.
"""
from __future__ import annotations

import math
import time
from datetime import date, datetime, time as dtime
from functools import lru_cache
from pathlib import Path
from typing import Optional

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, Direction, SignalResult,
)
from app.strategies.session_windows import EXCHANGE_TZ, et_epoch, session_date

Z_CAP = 2.0
VOL_LOOKBACK = 60
HORIZON_SESSIONS = 4
SETTLE = dtime(16, 0)
EARLY_SETTLE = dtime(13, 0)
CASH_OPEN = dtime(9, 30)

_BACKEND = Path(__file__).resolve().parents[2]
DEFAULT_HOLIDAYS = str(_BACKEND / "ief" / "data" / "exchange_holidays.csv")

# Wall clock. Module-level so a test can pin it; nothing else should touch it.
CLOCK = time.time


@lru_cache(maxsize=4)
def _daemon(holiday_csv: str):
    # Imported lazily: the daemon is stdlib-only, but the strategy package must
    # import cleanly on a host where ief/ has not been deployed.
    from ief.calendar_daemon import CalendarDaemon
    return CalendarDaemon(holiday_csv)


class CMERebalFlowStrategy(BaseStrategy):
    name = "cme_rebal_flow"
    requires = (DataNeed.OHLC, DataNeed.SESSION_TIMES)
    validated_on = ("ES=F", "YM=F", "RTY=F", "SPY")
    intervals = ("1d", "1day", "D1", "daily")

    def __init__(self, holiday_csv: str = DEFAULT_HOLIDAYS):
        super().__init__(holiday_csv=holiday_csv)
        self.holiday_csv = holiday_csv

    def min_bars(self) -> int:
        return VOL_LOOKBACK + 2

    # ------------------------------------------------------------------ core
    def _evaluate(self, bars: BarSeries) -> SignalResult:
        try:
            cal = _daemon(self.holiday_csv)
        except Exception as exc:
            return SignalResult.abstain(
                self.name, bars.symbol,
                f"exchange holiday schedule unavailable ({type(exc).__name__}: {exc}); "
                f"K cannot be derived without it and is never counted from bars")

        now = float(CLOCK())
        today = datetime.fromtimestamp(now, tz=EXCHANGE_TZ).date()
        month = f"{today.year:04d}-{today.month:02d}"
        try:
            plan = cal.month_plan(month)
        except Exception as exc:          # HolidayHorizonError and malformed files
            return SignalResult.abstain(self.name, bars.symbol, str(exc))
        if plan is None:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=f"{month} has too few sessions for a formation period")

        s0, form, entry, exit_ = (date.fromisoformat(x) for x in
                                  (plan.prior_close, plan.formation, plan.entry, plan.exit))
        base_ev = {"month": month, "K": plan.K, "prior_close": plan.prior_close,
                   "formation": plan.formation, "entry": plan.entry, "exit": plan.exit,
                   "registry_status": "CANDIDATE",
                   "levels": "none - the registered rule exits on time at month-end settlement"}

        if now < self._close_epoch(cal, form):
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=(f"outside the month-end window: formation close {plan.formation} "
                        f"not yet printed; trade window {plan.entry} open to {plan.exit} close"),
                evidence={**base_ev, "phase": "PRE_FORMATION"})
        if now >= self._close_epoch(cal, exit_):
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=f"{month} window closed at the {plan.exit} settlement",
                evidence={**base_ev, "phase": "SETTLED"})

        idx = {}
        for i, t in enumerate(bars.time):
            idx[session_date(t)] = i       # last bar per session date

        missing = [d.isoformat() for d in (s0, form) if d not in idx]
        if missing:
            return SignalResult.abstain(
                self.name, bars.symbol, f"no daily bar for required session(s) {missing}")

        # K integrity, causally: every scheduled session of the month up to the
        # formation date must have a bar, and no bar may sit on a non-session day.
        # A mismatch is a data defect and the month is dropped, not filled.
        sched = [d for d in cal.sessions_in_month(month) if d <= form]
        have = sorted(d for d in idx if d.year == form.year and d.month == form.month
                      and d <= form)
        if have != sched:
            return SignalResult.abstain(
                self.name, bars.symbol,
                f"bar dates disagree with the exchange calendar for {month} through "
                f"{plan.formation} (calendar {len(sched)} sessions, bars {len(have)}); "
                f"a month with a session-count defect is dropped, never repaired")

        fi, i0 = idx[form], idx[s0]
        if fi < VOL_LOOKBACK + 1:
            return SignalResult.abstain(
                self.name, bars.symbol,
                f"needs {VOL_LOOKBACK + 1} closes before the formation session, has {fi}")

        c = bars.close
        rets = [math.log(c[k] / c[k - 1]) for k in range(fi - VOL_LOOKBACK, fi)]
        mu = sum(rets) / len(rets)
        sigma = math.sqrt(sum((r - mu) ** 2 for r in rets) / (len(rets) - 1))
        if not sigma > 0:
            return SignalResult.abstain(self.name, bars.symbol, "zero trailing volatility")

        L = len(sched)
        S = math.log(c[fi] / c[i0])
        z = S / (sigma * math.sqrt(L))
        zc = max(-Z_CAP, min(Z_CAP, z))

        phase = "IN_WINDOW" if now >= et_epoch(entry, CASH_OPEN) else "FORMED_AWAITING_ENTRY"
        entry_px: Optional[float] = None
        if phase == "IN_WINDOW" and entry in idx:
            entry_px = float(bars.open[idx[entry]])

        ev = {**base_ev, "phase": phase, "z": round(z, 4), "z_capped": round(zc, 4),
              "S_bp": round(S * 1e4, 2), "sigma_daily": sigma, "L": L,
              "registered_weight_sign_and_magnitude": round(-zc / Z_CAP, 4),
              "vol_window": "60 daily log returns ending the session before formation"}

        if z == 0:
            return SignalResult(strategy=self.name, symbol=bars.symbol,
                                direction=Direction.FLAT, reason="formation return is exactly zero",
                                evidence=ev)

        direction = Direction.SHORT if z > 0 else Direction.LONG
        lean = "above" if z > 0 else "below"
        return SignalResult(
            strategy=self.name, symbol=bars.symbol, direction=direction,
            conviction=abs(zc) / Z_CAP,
            entry=entry_px, stop=None, target=None,
            time_exit_utc=int(self._close_epoch(cal, exit_)),
            horizon_bars=HORIZON_SESSIONS,
            reason=(f"month-to-date return {S * 1e4:+.1f} bp is z {z:+.2f} ({lean} its own "
                    f"dispersion over L={L} sessions, daily sigma {sigma * 1e4:.1f} bp); "
                    f"fixed-weight mandates rebalance against it into month-end - "
                    f"{direction.value} from the {plan.entry} open to the {plan.exit} settlement"),
            evidence=ev)

    @staticmethod
    def _close_epoch(cal, d: date) -> int:
        return et_epoch(d, EARLY_SETTLE if cal.is_early_close(d) else SETTLE)
