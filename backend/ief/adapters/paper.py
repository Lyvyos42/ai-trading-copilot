"""
IEF execution adapters — protocol plus a paper implementation
============================================================
The paper adapter is what the dry-run exercises end to end. A live Tradovate
adapter implements the same protocol and is NOT included here: it requires
credentials, an API contract, and a settlement-window confirmation that is still
open (see docs/SPEC_IEF_EXECUTION_BLUEPRINT.md, BLOCKING 1). Shipping a stub
that looked live would be worse than shipping none.

EXECUTION AUDIT IS NOT OPTIONAL.
Every fill records the touch price at submission alongside the fill, so the
realised slippage multiplier

    M_realised = |fill - mid| / (0.5 * spread)

can be compared against the Phase 4 measured 1.0829. That comparison is the only
way to learn whether the toll model survives contact with a real book, and the
whole cost case for this strategy rests on it.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from dataclasses import dataclass, asdict, field
from typing import Protocol

MARKET_ON_OPEN = "MOO"
TIME_SLICED = "SLICED"


@dataclass
class Fill:
    ts: str
    symbol: str
    contracts: int
    side: int
    order_type: str
    intended_price: float
    fill_price: float
    touch_bid: float
    touch_ask: float
    slippage_bp: float
    m_realised: float
    note: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


class ExecutionAdapter(Protocol):
    def submit(self, symbol: str, contracts: int, side: int, order_type: str,
               quote: dict, note: str = "") -> Fill: ...
    def positions(self) -> dict[str, int]: ...


@dataclass
class PaperAdapter:
    """Fills at the touch, plus an optional adverse tick allowance.

    `adverse_ticks = 0.0` is the DEFAULT and reproduces the Phase 4 measurement:
    93-97% of GLBX.MDP3 prints execute AT the touch, which is M = 1.0 exactly.
    Use 1.0 as a STRESS case; it yields M = 3.0, which is the measured 21-100
    contract band and is far worse than a 5-lot order should ever see. The default
    must match the measurement so the audit detects real degradation rather than
    an assumption baked into the simulator.
    """
    tick_size: dict[str, float] = field(default_factory=dict)
    multiplier: dict[str, float] = field(default_factory=dict)
    adverse_ticks: float = 0.0
    log_path: str | None = None
    starting_equity: float = 190_000.0
    _pos: dict[str, int] = field(default_factory=dict)
    _entry_px: dict[str, float] = field(default_factory=dict)
    _realised: float = 0.0
    _fills: list[Fill] = field(default_factory=list)

    def submit(self, symbol: str, contracts: int, side: int, order_type: str,
               quote: dict, note: str = "") -> Fill:
        bid, ask = float(quote["bid"]), float(quote["ask"])
        mid = 0.5 * (bid + ask)
        tick = self.tick_size.get(symbol, 0.25)
        touch = ask if side > 0 else bid
        fill = touch + side * self.adverse_ticks * tick * (1.0 if order_type == MARKET_ON_OPEN else 0.5)
        half_spread = max(0.5 * (ask - bid), 1e-12)
        f = Fill(
            ts=dt.datetime.now(dt.timezone.utc).isoformat(),
            symbol=symbol, contracts=contracts, side=side, order_type=order_type,
            intended_price=mid, fill_price=fill, touch_bid=bid, touch_ask=ask,
            slippage_bp=abs(fill - mid) / mid * 1e4,
            m_realised=abs(fill - mid) / half_spread,
            note=note)
        prev = self._pos.get(symbol, 0)
        new = prev + side * contracts
        mult = self.multiplier.get(symbol, 5.0)
        if prev != 0 and (side * contracts) * prev < 0:
            closed = min(abs(prev), contracts)
            direction = 1 if prev > 0 else -1
            entry = self._entry_px.get(symbol, fill)
            self._realised += direction * (fill - entry) * closed * mult
        if new != 0 and (prev == 0 or prev * new < 0):
            self._entry_px[symbol] = fill
        if new == 0:
            self._entry_px.pop(symbol, None)
        self._pos[symbol] = new
        self._fills.append(f)
        self._write(f)
        return f

    def positions(self) -> dict[str, int]:
        return {k: v for k, v in self._pos.items() if v != 0}

    @property
    def fills(self) -> list[Fill]:
        return list(self._fills)

    def _write(self, f: Fill) -> None:
        if not self.log_path:
            return
        os.makedirs(os.path.dirname(self.log_path) or ".", exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(f.as_dict()) + "\n")

    def audit(self, measured_m: float = 1.0829) -> dict:
        """Realised slippage against the Phase 4 measured multiplier."""
        if not self._fills:
            return {"fills": 0}
        ms = [f.m_realised for f in self._fills]
        bps = [f.slippage_bp for f in self._fills]
        return {"fills": len(ms),
                "m_realised_mean": sum(ms) / len(ms),
                "m_measured": measured_m,
                "m_excess": sum(ms) / len(ms) - measured_m,
                "slippage_bp_mean": sum(bps) / len(bps),
                "slippage_bp_total": sum(bps)}

    # -- account state ------------------------------------------------------
    def equity(self, marks: dict[str, float] | None = None) -> float:
        """Realised P&L plus mark-to-market on any open leg.

        The service polls this for the sentinel, so it must reflect OPEN risk,
        not just closed trades. Without the mark-to-market term an intra-trade
        drawdown guard would see a flat equity curve and never fire.
        """
        eq = self.starting_equity + self._realised
        for sym, q in self._pos.items():
            if q == 0 or not marks or sym not in marks:
                continue
            mult = self.multiplier.get(sym, 5.0)
            eq += (marks[sym] - self._entry_px.get(sym, marks[sym])) * q * mult
        return eq
