"""
IEF Sentinel — intra-trade capital-preservation guard
====================================================
Watches high-water-mark drawdown while a month-end position is open and forces a
scale-down or flatten if headroom is breached.

READ THIS BEFORE ENABLING IT.
prereg/CME_REBAL_FLOW_01.md section 2 specifies: "No stop, no target, no
intrabar exit." The measured maximum drawdown of -3.96% is the UNMANAGED figure.

A drawdown breaker is therefore NOT part of the evaluated strategy. It is a
capital-preservation override layered on top, and the moment it fires the live
event stops being comparable to the backtest. Every firing marks the month
CONTAMINATED so it can be excluded from any live-versus-measured comparison.
Silently stopping out and then comparing live returns to a no-stop backtest is
how a strategy's track record stops meaning anything.

CALIBRATION NOTE. At native sizing the strategy's worst 13-year monthly drawdown
was -3.96%; at the governed 1.9x it is roughly -7.5%. A 10% intra-trade headroom
breaker should therefore almost never fire. That is the intended design: it is a
tail guard against an execution or data fault, not a risk-management layer the
returns depend on. If it fires often, something else is wrong.
"""
from __future__ import annotations

from dataclasses import dataclass, field

SCALE_DOWN = "SCALE_DOWN"
FLATTEN = "FLATTEN"
OK = "OK"


@dataclass
class SentinelDecision:
    action: str                  # OK | SCALE_DOWN | FLATTEN
    drawdown: float              # current drawdown from HWM, negative
    headroom_used: float         # fraction of the breach budget consumed
    reason: str = ""
    target_scale: float = 1.0    # multiplier to apply to open size


@dataclass
class Sentinel:
    """Headroom is measured against the high-water mark of account equity."""
    headroom: float = 0.10           # 10% breach budget
    scale_down_at: float = 0.60      # de-risk at 60% of the budget
    scale_down_to: float = 0.50      # halve the position
    hwm: float = 0.0
    fired: bool = False
    log: list[dict] = field(default_factory=list)

    def observe(self, equity: float) -> SentinelDecision:
        if equity > self.hwm:
            self.hwm = equity
        if self.hwm <= 0:
            return SentinelDecision(OK, 0.0, 0.0, "no high-water mark yet")

        dd = equity / self.hwm - 1.0
        used = abs(dd) / self.headroom if self.headroom > 0 else 0.0

        if dd <= -self.headroom:
            self.fired = True
            d = SentinelDecision(
                FLATTEN, dd, used,
                f"drawdown {dd:+.2%} breached {self.headroom:.0%} headroom; "
                f"flattening. THIS MONTH IS CONTAMINATED and must be excluded "
                f"from live-versus-measured comparison.",
                target_scale=0.0)
        elif used >= self.scale_down_at:
            d = SentinelDecision(
                SCALE_DOWN, dd, used,
                f"drawdown {dd:+.2%} consumed {used:.0%} of headroom; "
                f"scaling to {self.scale_down_to:.0%}. Deviation from the "
                f"pre-registered no-intervention rule.",
                target_scale=self.scale_down_to)
        else:
            return SentinelDecision(OK, dd, used)

        self.log.append({"equity": equity, "hwm": self.hwm, "drawdown": dd,
                         "action": d.action, "reason": d.reason})
        return d

    def reset_for_new_trade(self, equity: float) -> None:
        """HWM restarts at entry so the guard measures INTRA-TRADE drawdown, not
        drawdown since inception."""
        self.hwm = equity
        self.fired = False

    def state(self) -> dict:
        return {"headroom": self.headroom, "hwm": self.hwm, "fired": self.fired,
                "events": len(self.log)}

    @classmethod
    def from_state(cls, d: dict) -> "Sentinel":
        s = cls(headroom=d.get("headroom", 0.10))
        s.hwm = d.get("hwm", 0.0)
        s.fired = bool(d.get("fired", False))
        return s
