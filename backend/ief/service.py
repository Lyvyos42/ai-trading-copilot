"""
IEF continuous background service — month-end rebalance daemon
==============================================================
Wires calendar_daemon + sizing + sentinel + an execution adapter into a
long-running state machine that sleeps between decision windows.

    IDLE -> FORMATION -> ARMED -> IN_TRADE -> SETTLED -> IDLE(next month)

THE HARD PROBLEM HERE IS NOT SCHEDULING, IT IS CRASH RECOVERY.
A naive daemon persists state AFTER acting. If it dies between sending orders and
writing the file, the next start either re-sends (double position) or believes
nothing happened (unhedged, unflattened). Both are worse than never starting.

So this service uses a WRITE-AHEAD INTENT LOG:
  1. write pending_dispatch{step, orders} and fsync BEFORE any order is sent
  2. send, collecting fills
  3. write fills + positions, clear pending_dispatch

On startup, a non-null pending_dispatch means the process died mid-dispatch. The
service then RECONCILES AGAINST THE BROKER'S ACTUAL POSITIONS rather than
guessing from its own record. The broker is the authority on what exists; the
state file is only the authority on what was intended.

State writes are atomic: temp file, fsync, os.replace. A plain open("w") can
leave a truncated JSON file if the process dies mid-write, and an unparseable
state file on a live position is the worst possible failure.

All decision times are America/New_York. Every clock read goes through the Clock
protocol so tests drive time deterministically instead of sleeping.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
from dataclasses import dataclass, field
from typing import Protocol, Callable
from zoneinfo import ZoneInfo

from ief.calendar_daemon import CalendarDaemon, MonthPlan, FORMATION, ENTRY, EXIT
from ief import sizing as SZ
from ief.core.sentinel import Sentinel, FLATTEN, SCALE_DOWN

ET = ZoneInfo("America/New_York")

IDLE, PH_FORMATION, ARMED, IN_TRADE, SETTLED = (
    "IDLE", "FORMATION", "ARMED", "IN_TRADE", "SETTLED")

T_FORMATION = dt.time(16, 15)       # session T-5, after settlement
T_SIZING = dt.time(9, 20)           # session T-4
T_ENTRY = dt.time(9, 29, 55)        # session T-4, just before the open
T_EXIT = dt.time(15, 59, 30)        # session T, settlement VWAP window

STATE_VERSION = 2
DEFAULT_STATE_PATH = "data/rebal_state.json"
DEFAULT_LOG_PATH = "logs/ief_rebal_execution.log"


class Clock(Protocol):
    def now(self) -> dt.datetime: ...


class SystemClock:
    def now(self) -> dt.datetime:
        return dt.datetime.now(tz=ET)


@dataclass
class FakeClock:
    t: dt.datetime

    def now(self) -> dt.datetime:
        return self.t

    def set(self, iso: str) -> None:
        d = dt.datetime.fromisoformat(iso)
        self.t = d if d.tzinfo else d.replace(tzinfo=ET)


def _atomic_write_json(path: str, payload: dict) -> None:
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".rebal_state.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


@dataclass
class RebalService:
    daemon: CalendarDaemon
    adapter: object                                  # ExecutionAdapter
    price_fn: Callable[[str, str], float]            # (series, date) -> close
    closes_fn: Callable[[str, str], list]            # (series, date) -> closes through date
    equity_fn: Callable[[], float]
    clock: Clock = field(default_factory=SystemClock)
    series: tuple = ("es_daily", "ym_daily", "rty_daily")
    state_path: str = DEFAULT_STATE_PATH
    log_path: str = DEFAULT_LOG_PATH
    z_cap: float = 2.0
    vol_target: float = 0.10
    sentinel: Sentinel = field(default_factory=Sentinel)
    state: dict = field(default_factory=dict)
    events: list = field(default_factory=list)

    # ------------------------------------------------------------------ state
    def __post_init__(self) -> None:
        self.state = self._load_state()
        if self.state.get("sentinel"):
            self.sentinel = Sentinel.from_state(self.state["sentinel"])

    def _blank(self) -> dict:
        return {"version": STATE_VERSION, "month": None, "phase": IDLE,
                "plan": None, "formation": None, "sizing": None,
                "pending_dispatch": None, "fills": [], "positions": {},
                "contaminated": False, "sentinel": self.sentinel.state(),
                "history": []}

    def _load_state(self) -> dict:
        if not os.path.exists(self.state_path):
            return self._blank()
        try:
            with open(self.state_path, encoding="utf-8") as fh:
                s = json.load(fh)
        except (json.JSONDecodeError, OSError) as e:
            # An unparseable state file with a possibly-open position is the one
            # case where refusing to start is safer than guessing.
            raise RuntimeError(
                f"{self.state_path} is unreadable ({e}). Refusing to start: a live "
                f"position may exist. Inspect the broker, then repair or remove the "
                f"file deliberately.") from e
        if s.get("version") != STATE_VERSION:
            s.setdefault("history", [])
            s["version"] = STATE_VERSION
        return s

    def _persist(self) -> None:
        self.state["sentinel"] = self.sentinel.state()
        self.state["updated_at"] = self.clock.now().isoformat()
        _atomic_write_json(self.state_path, self.state)

    def _emit(self, kind: str, detail: dict) -> None:
        rec = {"ts": self.clock.now().isoformat(), "kind": kind, **detail}
        self.events.append(rec)
        os.makedirs(os.path.dirname(self.log_path) or ".", exist_ok=True)
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    # ------------------------------------------------------------ recovery
    def recover(self) -> dict:
        """Reconcile a mid-dispatch crash against the broker's actual positions."""
        pend = self.state.get("pending_dispatch")
        if not pend:
            return {"recovered": False}

        broker = dict(self.adapter.positions())
        intended = {o["symbol"]: o["side"] * o["contracts"] for o in pend["orders"]}
        step = pend["step"]

        if step == ENTRY:
            missing = {s: q for s, q in intended.items() if broker.get(s, 0) != q}
            if not missing:
                outcome = "entry fully filled before the crash; advancing to IN_TRADE"
                self.state["phase"] = IN_TRADE
                self.state["positions"] = broker
            elif not broker:
                outcome = "no position at the broker; entry never landed. Re-arming."
                self.state["phase"] = ARMED
            else:
                outcome = (f"PARTIAL entry detected {broker} vs intended {intended}. "
                           f"Flattening to a known-safe state rather than guessing.")
                self._flatten(reason="partial-entry recovery")
                self.state["phase"] = SETTLED
                self.state["contaminated"] = True
        else:  # EXIT
            if not broker:
                outcome = "exit completed before the crash; flat"
                self.state["phase"] = SETTLED
                self.state["positions"] = {}
            else:
                outcome = f"exit incomplete, still holding {broker}. Flattening now."
                self._flatten(reason="incomplete-exit recovery")
                self.state["phase"] = SETTLED
                self.state["contaminated"] = True

        self.state["pending_dispatch"] = None
        self._emit("RECOVERY", {"step": step, "intended": intended,
                                "broker": broker, "outcome": outcome})
        self._persist()
        return {"recovered": True, "step": step, "outcome": outcome,
                "phase": self.state["phase"]}

    # ------------------------------------------------------------- dispatch
    def _dispatch(self, step: str, orders: list, prices: dict, flip: bool) -> list:
        """Write-ahead the intent, then send. NEVER send before persisting."""
        intent = [{"symbol": o.symbol, "series": o.series, "contracts": o.contracts,
                   "side": (-o.side if flip else o.side)} for o in orders]
        self.state["pending_dispatch"] = {
            "step": step, "orders": intent,
            "started_at": self.clock.now().isoformat()}
        self._persist()

        from ief.adapters.paper import MARKET_ON_OPEN, TIME_SLICED
        otype = MARKET_ON_OPEN if step == ENTRY else TIME_SLICED
        fills = []
        for o in orders:
            series, sym = o.series, o.symbol
            px = prices[series]
            tick = getattr(self.adapter, "tick_size", {}).get(sym, 0.25)
            quote = {"bid": px - tick / 2, "ask": px + tick / 2}
            side = -o.side if flip else o.side
            f = self.adapter.submit(sym, o.contracts, side, otype, quote,
                                    note=f"{self.state['month']}:{step}")
            fills.append(f.as_dict() if hasattr(f, "as_dict") else dict(f))

        self.state["fills"] = self.state.get("fills", []) + fills
        self.state["positions"] = dict(self.adapter.positions())
        self.state["pending_dispatch"] = None
        self._persist()
        self._emit(step, {"fills": len(fills), "positions": self.state["positions"]})
        return fills

    def _flatten(self, reason: str) -> None:
        from ief.adapters.paper import TIME_SLICED
        pos = dict(self.adapter.positions())
        if not pos:
            return
        sz = self.state.get("sizing") or {}
        by_sym = {o["symbol"]: o for o in sz.get("orders", [])}
        for sym, q in pos.items():
            series = by_sym.get(sym, {}).get("series", "es_daily")
            px = by_sym.get(sym, {}).get("price") or self.price_fn(
                series, self.state["plan"]["exit"])
            tick = getattr(self.adapter, "tick_size", {}).get(sym, 0.25)
            self.adapter.submit(sym, abs(q), -1 if q > 0 else 1, TIME_SLICED,
                                {"bid": px - tick / 2, "ask": px + tick / 2},
                                note=f"{self.state['month']}:FLATTEN:{reason}")
        self.state["positions"] = dict(self.adapter.positions())
        self._emit("FLATTEN", {"reason": reason, "positions": self.state["positions"]})

    # ------------------------------------------------------------ transitions
    def _begin_month(self, plan: MonthPlan) -> None:
        if self.state.get("month") and self.state.get("phase") == SETTLED:
            self.state["history"] = (self.state.get("history", []) + [{
                "month": self.state["month"],
                "contaminated": self.state.get("contaminated", False),
                "fills": len(self.state.get("fills", []))}])[-24:]
        hist = self.state.get("history", [])
        self.state.update(self._blank())
        self.state["history"] = hist
        self.state["month"] = plan.month
        self.state["plan"] = plan.as_dict()
        self.state["phase"] = IDLE

    def _do_formation(self) -> dict:
        import math
        plan = self.state["plan"]
        zs, sig = {}, {}
        for s in self.series:
            closes = self.closes_fn(s, plan["formation"])
            if len(closes) < 62:
                continue
            # The research harness calculates rolling(60).std().shift(1): the 60-session
            # volatility window ends the session before formation (excluding formation-day return).
            sd_ann = SZ.trailing_vol_annualised(closes[:-1], 60)
            sd_d = sd_ann / math.sqrt(252.0)
            p0 = self.price_fn(s, plan["prior_close"])
            p1 = self.price_fn(s, plan["formation"])
            L = self._sessions_between(plan["prior_close"], plan["formation"])
            z = math.log(p1 / p0) / (sd_d * math.sqrt(max(L, 1)))
            zs[s], sig[s] = z, sd_d
        n = max(len(zs), 1)
        w = {s: -max(-self.z_cap, min(self.z_cap, z)) / self.z_cap * (1.0 / n)
                * (self.vol_target / (sig[s] * math.sqrt(252.0)))
             for s, z in zs.items()}
        gross = sum(abs(v) for v in w.values())
        if gross > 3.0:
            w = {k: v * 3.0 / gross for k, v in w.items()}
        self.state["formation"] = {
            "z": zs, "sigma_d": sig, "weights": w,
            "sessions_elapsed": self._sessions_between(plan["prior_close"],
                                                       plan["formation"]),
            "computed_at": self.clock.now().isoformat()}
        self.state["phase"] = PH_FORMATION
        self._persist()
        self._emit(FORMATION, {"z": zs})
        return self.state["formation"]

    def _sessions_between(self, a: str, b: str) -> int:
        d0, d1 = dt.date.fromisoformat(a), dt.date.fromisoformat(b)
        n, d = 0, d0 + dt.timedelta(days=1)
        while d <= d1:
            if self.daemon.is_session(d):
                n += 1
            d += dt.timedelta(days=1)
        return n

    def _do_sizing(self) -> dict:
        plan = self.state["plan"]
        w = self.state["formation"]["weights"]
        prices = {s: self.price_fn(s, plan["formation"]) for s in w}
        sp = SZ.build_plan(w, prices, self.equity_fn())
        self.state["sizing"] = {
            "mode": sp.mode, "equity": sp.equity, "leverage_cap": sp.leverage_cap,
            "k_effective": sp.k_effective, "governor_active": sp.governor_binding,
            "gross_leverage": sp.gross_leverage, "warnings": sp.warnings,
            "orders": [{"symbol": o.symbol, "series": o.series,
                        "contracts": o.contracts, "side": o.side,
                        "price": o.price, "target_notional": o.target_notional,
                        "actual_notional": o.actual_notional,
                        "quantisation_error": o.quantisation_error,
                        "in_toll_band": o.in_toll_band} for o in sp.orders]}
        self.state["phase"] = ARMED
        self._persist()
        self._emit("SIZED", {"mode": sp.mode, "k": sp.k_effective,
                             "contracts": {o.symbol: o.contracts for o in sp.orders},
                             "governor": sp.governor_binding})
        return self.state["sizing"]

    def _rebuild_orders(self) -> list:
        from ief.sizing import Order
        return [Order(symbol=o["symbol"], series=o["series"],
                      contracts=o["contracts"], side=o["side"],
                      target_weight=0.0, target_notional=o["target_notional"],
                      actual_notional=o["actual_notional"], price=o["price"],
                      quantisation_error=o["quantisation_error"],
                      in_toll_band=o["in_toll_band"])
                for o in self.state["sizing"]["orders"]]

    def _do_entry(self) -> dict:
        plan = self.state["plan"]
        if not self.daemon.confirm_open(plan["entry"]):
            self._emit("ABORT", {"step": ENTRY, "reason":
                                 f"{plan['entry']} is not a session; exchange closed"})
            self.state["phase"] = SETTLED
            self._persist()
            return {"aborted": True}
        orders = self._rebuild_orders()
        prices = {o.series: self.price_fn(o.series, plan["entry"]) for o in orders}
        self._dispatch(ENTRY, orders, prices, flip=False)
        self.sentinel.reset_for_new_trade(self.equity_fn())
        self.state["phase"] = IN_TRADE
        self._persist()
        return {"entered": True, "positions": self.state["positions"]}

    def _do_exit(self, reason: str = "scheduled") -> dict:
        plan = self.state["plan"]
        orders = self._rebuild_orders()
        prices = {o.series: self.price_fn(o.series, plan["exit"]) for o in orders}
        self._dispatch(EXIT, orders, prices, flip=True)
        self.state["phase"] = SETTLED
        self._persist()
        return {"exited": True, "reason": reason}

    # ------------------------------------------------------------------ tick
    def tick(self) -> dict:
        """One decision step. Returns what happened. Safe to call repeatedly."""
        if self.state.get("pending_dispatch"):
            return {"action": "RECOVER", **self.recover()}

        now = self.clock.now()
        today = now.date().isoformat()
        t = now.timetz().replace(tzinfo=None)

        try:
            plan = self.daemon.month_plan(f"{now.year:04d}-{now.month:02d}")
        except Exception as e:
            return {"action": "NONE", "error": str(e)}
        if plan is None:
            return {"action": "NONE", "reason": "month not tradable"}

        if self.state.get("month") != plan.month:
            # A SETTLED prior month rolls into history; an OPEN one must not be
            # abandoned just because the calendar turned.
            if self.state.get("phase") == IN_TRADE:
                return {"action": "HOLD", "reason":
                        "prior month still IN_TRADE; refusing to roll the month"}
            self._begin_month(plan)
            self._persist()

        phase = self.state["phase"]

        if phase == IN_TRADE:
            d = self.sentinel.observe(self.equity_fn())
            if d.action == FLATTEN:
                self._flatten(reason="sentinel")
                self.state["contaminated"] = True
                self.state["phase"] = SETTLED
                self._persist()
                self._emit("SENTINEL", {"action": FLATTEN, "reason": d.reason})
                return {"action": "SENTINEL_FLATTEN", "drawdown": d.drawdown}
            if d.action == SCALE_DOWN and not self.state.get("scaled_down"):
                self.state["scaled_down"] = True
                self.state["contaminated"] = True
                self._persist()
                self._emit("SENTINEL", {"action": SCALE_DOWN, "reason": d.reason})
                return {"action": "SENTINEL_SCALE_DOWN", "drawdown": d.drawdown}

        if today == plan.formation and t >= T_FORMATION and phase == IDLE:
            return {"action": FORMATION, **self._do_formation()}
        if today == plan.entry and t >= T_SIZING and phase == PH_FORMATION:
            return {"action": "SIZED", **self._do_sizing()}
        if today == plan.entry and t >= T_ENTRY and phase == ARMED:
            return {"action": ENTRY, **self._do_entry()}
        if today == plan.exit and t >= T_EXIT and phase == IN_TRADE:
            return {"action": EXIT, **self._do_exit()}

        return {"action": "NONE", "phase": phase, "month": plan.month}

    # ------------------------------------------------------------- scheduling
    def next_event(self) -> dict | None:
        now = self.clock.now()
        try:
            plan = self.daemon.month_plan(f"{now.year:04d}-{now.month:02d}")
        except Exception:
            return None
        if plan is None:
            return None
        phase = self.state.get("phase", IDLE)
        sched = [(IDLE, plan.formation, T_FORMATION, "T-5", "CALCULATE_FORMATION"),
                 (PH_FORMATION, plan.entry, T_SIZING, "T-4", "COMPUTE_SIZING"),
                 (ARMED, plan.entry, T_ENTRY, "T-4", "DISPATCH_ENTRY"),
                 (IN_TRADE, plan.exit, T_EXIT, "T", "DISPATCH_EXIT")]
        for ph, date, tm, label, action in sched:
            if ph != phase:
                continue
            when = dt.datetime.combine(dt.date.fromisoformat(date), tm, tzinfo=ET)
            return {"session": label, "date": date, "action": action,
                    "at": when.isoformat(),
                    "seconds_until": max(0.0, (when - now).total_seconds())}
        return None

    def seconds_to_sleep(self, cap: float = 900.0) -> float:
        nxt = self.next_event()
        if not nxt:
            return cap
        return max(1.0, min(cap, nxt["seconds_until"]))

    def run_forever(self, sleep_fn=None, max_iterations: int | None = None) -> None:
        import time
        sleep_fn = sleep_fn or time.sleep
        i = 0
        while max_iterations is None or i < max_iterations:
            r = self.tick()
            if r.get("action") not in (None, "NONE"):
                self._emit("TICK", {"result_action": r.get("action")})
            sleep_fn(self.seconds_to_sleep())
            i += 1

    # ----------------------------------------------------------- telemetry
    def telemetry(self) -> dict:
        sz = self.state.get("sizing") or {}
        form = self.state.get("formation") or {}
        fills = self.state.get("fills", [])
        audit = self.adapter.audit() if hasattr(self.adapter, "audit") else {}
        last_m = fills[-1].get("m_realised") if fills else None
        sym = {"es_daily": "ES", "ym_daily": "YM", "rty_daily": "RTY"}
        zs = {sym.get(k, k): round(v, 4) for k, v in (form.get("z") or {}).items()}
        w = form.get("weights") or {}
        direction = None
        if w:
            direction = "LONG" if sum(w.values()) > 0 else "SHORT"
        return {
            "module": "cme_rebal_flow",
            "status": "CANDIDATE",
            "arm_mode": "EXPERIMENT",
            "phase": self.state.get("phase", IDLE),
            "month": self.state.get("month"),
            "next_event": self.next_event(),
            "formation_z": zs,
            "active_direction": direction,
            "sizing": {
                "equity": sz.get("equity"),
                "mode": sz.get("mode"),
                "governor_active": sz.get("governor_active"),
                "governed_multiple": (round(sz["k_effective"], 4)
                                      if sz.get("k_effective") is not None else None),
                "gross_leverage": (round(sz["gross_leverage"], 4)
                                   if sz.get("gross_leverage") is not None else None),
                "contracts": {o["symbol"]: o["contracts"]
                              for o in sz.get("orders", [])},
                "warnings": sz.get("warnings", []),
            },
            "positions": self.state.get("positions", {}),
            "execution_audit": {
                "fills": len(fills),
                "last_fill_M": round(last_m, 4) if last_m is not None else None,
                "mean_M": (round(audit["m_realised_mean"], 4)
                           if audit.get("m_realised_mean") is not None else None),
                "m_measured": audit.get("m_measured"),
                "tracking_error_bp": (round(audit["slippage_bp_mean"], 4)
                                      if audit.get("slippage_bp_mean") is not None else None),
            },
            "sentinel": self.sentinel.state(),
            "contaminated": self.state.get("contaminated", False),
            "history": self.state.get("history", [])[-6:],
        }
