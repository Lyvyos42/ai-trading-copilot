"""ten_am_macro: the 10:00 ET macro-window sweep, structure shift and retest.

SOURCE AND STATUS

Institutional Edge core/research_strategies/ten_am_macro.py, registry status
OBSERVE: "no backtest exists. Mechanism verified on 99k M5 bars; edge unknown.
Armed on DEMO to collect forward data only." Registered here as an observer so
the forward record accumulates without the strategy ever voting.

THE RULE IS THE SOURCE MODULE'S DEFAULTS, PORTED EXACTLY

    anchor        the bar opening at exactly 10:00:00 ET; p10 = its open, atr0 = ATR there
    manipulation  10:00 -> 10:25 ET, running high/low
    sweep         side qualifies when its excursion from p10 >= 0.25 * atr0
    shift         2 consecutive closes on the far side of p10 (below -> short, above -> long)
    two-sided     the larger excursion defines the setup
    entry         retest: fires when a bar touches p10 +/- 0.10 * atr0, entry = p10
    stop          beyond the manipulation extreme by 0.10 * atr0
    target        entry +/- 2.0 R
    expiry        re-arm allowed after 24 bars without a retest; one trade per session
    session end   16:00 ET
    ATR           Wilder, alpha 1/14, seeded on the first true range - as the source

A directive describing this strategy as "volume stabilisation after ISM" and an
"initial balance midpoint" target describes a different rule. Neither volume nor
a release calendar appears in the source, so neither appears here.

M5 ONLY. The 25-minute manipulation window and the 24-bar expiry are denominated
in M5 bars; on M15 or H1 they measure something else.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, Direction, SignalResult,
)

NY = ZoneInfo("America/New_York")
ANCHOR_MIN = 10 * 60
SESSION_END_MIN = 16 * 60


def wilder_atr(high, low, close, length: int = 14) -> list[float]:
    out: list[float] = []
    prev = None
    for i in range(len(close)):
        pc = close[i - 1] if i else close[0]
        tr = max(high[i] - low[i], abs(high[i] - pc), abs(low[i] - pc))
        prev = tr if prev is None else prev + (tr - prev) / length
        out.append(prev)
    return out


class TenAMMacroStrategy(BaseStrategy):
    name = "ten_am_macro"
    requires = (DataNeed.OHLC, DataNeed.SESSION_TIMES)
    validated_on = ()
    intervals = ("5m",)

    def __init__(self, manip_minutes: int = 25, min_sweep_atr: float = 0.25,
                 confirm_bars: int = 2, retest_tolerance: float = 0.10,
                 buffer_atr: float = 0.10, rr_min: float = 2.0,
                 retest_expiry_bars: int = 24, atr_len: int = 14):
        super().__init__(manip_minutes=manip_minutes, min_sweep_atr=min_sweep_atr,
                         confirm_bars=confirm_bars, retest_tolerance=retest_tolerance,
                         buffer_atr=buffer_atr, rr_min=rr_min,
                         retest_expiry_bars=retest_expiry_bars, atr_len=atr_len)
        self.manip_minutes = manip_minutes
        self.min_sweep_atr = min_sweep_atr
        self.confirm_bars = confirm_bars
        self.retest_tolerance = retest_tolerance
        self.buffer_atr = buffer_atr
        self.rr_min = rr_min
        self.retest_expiry_bars = retest_expiry_bars
        self.atr_len = atr_len

    def min_bars(self) -> int:
        return self.atr_len + 12

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        o, h, l, c = bars.open, bars.high, bars.low, bars.close
        atr = wilder_atr(h, l, c, self.atr_len)
        ny = [datetime.fromtimestamp(float(t), tz=NY) for t in bars.time]
        day = ny[-1].date()
        manip_end = ANCHOR_MIN + int(self.manip_minutes)

        p10 = atr0 = hm = lm = sess_hi = sess_lo = None
        cu = cd = 0
        armed, armed_bar, armed_sl = 0, -1, None
        fired = None
        up_sweep = dn_sweep = 0.0

        for i in range(len(c)):
            if ny[i].date() != day:
                continue
            m = ny[i].hour * 60 + ny[i].minute
            if p10 is None:
                if m == ANCHOR_MIN and atr[i] > 0:
                    p10, atr0 = o[i], atr[i]
                    hm, lm, sess_hi, sess_lo = h[i], l[i], h[i], l[i]
                continue
            sess_hi, sess_lo = max(sess_hi, h[i]), min(sess_lo, l[i])
            if m < manip_end:
                hm, lm = max(hm, h[i]), min(lm, l[i])
                continue
            if m >= SESSION_END_MIN or fired:
                continue

            if c[i] < p10:
                cd, cu = cd + 1, 0
            elif c[i] > p10:
                cu, cd = cu + 1, 0
            else:
                cu = cd = 0

            up_sweep, dn_sweep = hm - p10, p10 - lm
            thresh = self.min_sweep_atr * atr0
            if armed == 0:
                short_ok = up_sweep >= thresh and cd >= self.confirm_bars
                long_ok = dn_sweep >= thresh and cu >= self.confirm_bars
                if short_ok and long_ok:
                    if up_sweep >= dn_sweep:
                        long_ok = False
                    else:
                        short_ok = False
                if short_ok or long_ok:
                    side = -1 if short_ok else 1
                    ext = hm if side < 0 else lm
                    armed, armed_bar = side, i
                    armed_sl = ext - side * self.buffer_atr * atr0
            else:
                tol = self.retest_tolerance * atr0
                if l[i] <= p10 + tol and h[i] >= p10 - tol:
                    risk = abs(p10 - armed_sl)
                    if risk > 0:
                        fired = {"i": i, "side": armed, "entry": p10, "sl": armed_sl,
                                 "tp": p10 + armed * self.rr_min * risk,
                                 "rr": self.rr_min, "time": ny[i].strftime("%H:%M"),
                                 "sweep_atr": (up_sweep if armed < 0 else dn_sweep) / atr0}
                    armed, armed_bar, armed_sl = 0, -1, None
                elif i - armed_bar >= self.retest_expiry_bars:
                    armed, armed_bar, armed_sl = 0, -1, None
                    cu = cd = 0

        ev = {"session": day.isoformat(), "p10": p10, "atr0": atr0,
              "h_manip": hm, "l_manip": lm, "armed": armed,
              "registry_status": "OBSERVE - no backtest exists"}
        if p10 is None:
            return SignalResult(strategy=self.name, symbol=bars.symbol,
                                direction=Direction.FLAT,
                                reason="no bar opening at exactly 10:00 ET in this session",
                                evidence=ev)
        last_min = ny[-1].hour * 60 + ny[-1].minute
        if fired is None:
            state = ("armed, waiting for the p10 retest" if armed else
                     "manipulation window still open" if last_min < manip_end else
                     "no qualifying sweep and structure shift")
            return SignalResult(strategy=self.name, symbol=bars.symbol,
                                direction=Direction.FLAT, reason=state, evidence=ev)
        if last_min >= SESSION_END_MIN:
            return SignalResult(strategy=self.name, symbol=bars.symbol,
                                direction=Direction.FLAT,
                                reason=f"setup fired at {fired['time']} ET; session has ended",
                                evidence={**ev, "fired": fired})

        side = fired["side"]
        close_dt = datetime.combine(day, datetime.min.time(), tzinfo=NY).replace(hour=16)
        return SignalResult(
            strategy=self.name, symbol=bars.symbol,
            direction=Direction.LONG if side > 0 else Direction.SHORT,
            conviction=0.5,
            entry=fired["entry"], stop=fired["sl"], target=fired["tp"],
            time_exit_utc=int(close_dt.timestamp()),
            horizon_bars=len(c) - 1 - fired["i"],
            reason=(f"10:00 ET {'high' if side < 0 else 'low'} swept "
                    f"{fired['sweep_atr']:.2f} ATR from p10 {fired['entry']:.5g}, structure "
                    f"shifted, retest filled at {fired['time']} ET; stop {fired['sl']:.5g}, "
                    f"target {fired['tp']:.5g} (2R)"),
            evidence={**ev, "fired": fired})
