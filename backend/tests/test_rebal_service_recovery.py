"""
State persistence and crash recovery — ief/service.py
=====================================================
The property under test is the one that matters in production: a process killed
at any point must not, on restart, produce a duplicate position or abandon a live
one.

Every "crash" here is a hard drop of the service object with only the on-disk
state surviving, then a fresh construction from that file. The broker adapter
persists across the restart because a real broker does: the exchange does not
forget your position because your daemon died.

Run:  python tests/test_rebal_service_recovery.py
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import shutil
import sys
import tempfile

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ief.calendar_daemon import CalendarDaemon, ENTRY, EXIT
from ief.service import (RebalService, FakeClock, IDLE, PH_FORMATION, ARMED,
                         IN_TRADE, SETTLED)
from ief.adapters.paper import PaperAdapter
from ief.core.sentinel import Sentinel

SCHEDULE = "ief/data/exchange_holidays.csv"
SERIES = ("es_daily", "ym_daily", "rty_daily")
MONTH = "2023-12"
TICK = {"MES": 0.25, "MYM": 1.00, "M2K": 0.10}
MULT = {"MES": 5.0, "MYM": 0.5, "M2K": 5.0}

_CLOSES: dict[str, pd.Series] = {}


def closes(series: str) -> pd.Series:
    if series not in _CLOSES:
        d = pd.read_parquet(f"app/data/{series}.parquet")
        d["ts"] = pd.to_datetime(d["ts"], utc=True)
        d = d[d["ts"] < pd.Timestamp("2024-01-01", tz="UTC")].sort_values("ts")
        _CLOSES[series] = pd.Series(
            d["close"].values, index=d["ts"].dt.strftime("%Y-%m-%d").values)
    return _CLOSES[series]


def price_fn(series: str, date: str) -> float:
    s = closes(series)
    if date in s.index:
        return float(s[date])
    prior = s[s.index <= date]
    if len(prior) == 0:
        raise KeyError(f"{series}: no price at or before {date}")
    return float(prior.iloc[-1])


def closes_fn(series: str, date: str) -> list:
    s = closes(series)
    return [float(x) for x in s[s.index <= date].values]


class Harness:
    """Owns the temp state dir and can rebuild the service as a 'restart'."""

    def __init__(self, equity: float = 190_000.0):
        self.dir = tempfile.mkdtemp(prefix="ief_recovery_")
        self.state_path = os.path.join(self.dir, "rebal_state.json")
        self.log_path = os.path.join(self.dir, "exec.log")
        self.adapter = PaperAdapter(tick_size=TICK, multiplier=MULT,
                                    log_path=self.log_path,
                                    starting_equity=equity)
        self.marks: dict[str, float] = {}
        self.clock = FakeClock(dt.datetime(2023, 12, 22, 16, 20))
        self.svc = self._build()

    def _build(self) -> RebalService:
        return RebalService(
            daemon=CalendarDaemon(SCHEDULE),
            adapter=self.adapter,
            price_fn=price_fn, closes_fn=closes_fn,
            equity_fn=lambda: self.adapter.equity(self.marks),
            clock=self.clock, series=SERIES,
            state_path=self.state_path, log_path=self.log_path)

    def crash_and_restart(self) -> RebalService:
        """Drop the service object. Only the state file and the broker survive."""
        self.svc = None
        self.svc = self._build()
        return self.svc

    def at(self, iso: str) -> None:
        self.clock.set(iso)

    def raw_state(self) -> dict:
        with open(self.state_path, encoding="utf-8") as fh:
            return json.load(fh)

    def cleanup(self) -> None:
        shutil.rmtree(self.dir, ignore_errors=True)


def run_to_armed(h: Harness) -> None:
    h.at("2023-12-22T16:20:00")
    assert h.svc.tick()["action"] == "FORMATION"
    h.at("2023-12-26T09:21:00")
    assert h.svc.tick()["action"] == "SIZED"


# ---------------------------------------------------------------------------
def test_state_file_is_atomic_and_parseable_at_every_phase():
    h = Harness()
    try:
        phases = []
        h.at("2023-12-22T16:20:00"); h.svc.tick(); phases.append(h.raw_state()["phase"])
        h.at("2023-12-26T09:21:00"); h.svc.tick(); phases.append(h.raw_state()["phase"])
        h.at("2023-12-26T09:29:56"); h.svc.tick(); phases.append(h.raw_state()["phase"])
        h.at("2023-12-29T15:59:31"); h.svc.tick(); phases.append(h.raw_state()["phase"])
        assert phases == [PH_FORMATION, ARMED, IN_TRADE, SETTLED], phases
        assert not os.path.exists(h.state_path + ".tmp")
        leftovers = [f for f in os.listdir(h.dir) if f.startswith(".rebal_state.")]
        assert not leftovers, leftovers
    finally:
        h.cleanup()


def test_restart_between_phases_resumes_without_duplicating():
    h = Harness()
    try:
        run_to_armed(h)
        assert h.raw_state()["phase"] == ARMED
        h.crash_and_restart()
        assert h.svc.state["phase"] == ARMED
        assert h.svc.state["formation"]["z"], "formation survived the restart"
        h.at("2023-12-26T09:29:56")
        r = h.svc.tick()
        assert r["action"] == ENTRY
        pos_after_first = dict(h.adapter.positions())
        assert pos_after_first

        # restart again, then tick repeatedly: must NOT re-enter
        h.crash_and_restart()
        for _ in range(4):
            h.svc.tick()
        assert dict(h.adapter.positions()) == pos_after_first, "duplicate entry"
        assert h.svc.state["phase"] == IN_TRADE
    finally:
        h.cleanup()


def test_crash_after_intent_write_but_before_any_fill_re_arms():
    """Simulates dying between the write-ahead intent and the first order."""
    h = Harness()
    try:
        run_to_armed(h)
        st = h.raw_state()
        st["pending_dispatch"] = {
            "step": ENTRY,
            "orders": [{"symbol": o["symbol"], "series": o["series"],
                        "contracts": o["contracts"], "side": o["side"]}
                       for o in st["sizing"]["orders"]],
            "started_at": "2023-12-26T09:29:55"}
        with open(h.state_path, "w", encoding="utf-8") as fh:
            json.dump(st, fh)

        h.crash_and_restart()
        assert not h.adapter.positions(), "no orders reached the broker"
        r = h.svc.tick()
        assert r["action"] == "RECOVER"
        assert r["phase"] == ARMED, r
        assert "never landed" in r["outcome"], r["outcome"]
        assert h.raw_state()["pending_dispatch"] is None

        h.at("2023-12-26T09:29:56")
        assert h.svc.tick()["action"] == ENTRY
        assert h.adapter.positions()
    finally:
        h.cleanup()


def test_crash_mid_dispatch_with_partial_fill_flattens_and_marks_contaminated():
    """A partial multi-leg entry is reconciled to flat, not guessed at."""
    h = Harness()
    try:
        run_to_armed(h)
        st = h.raw_state()
        orders = [{"symbol": o["symbol"], "series": o["series"],
                   "contracts": o["contracts"], "side": o["side"]}
                  for o in st["sizing"]["orders"]]
        # one leg landed at the broker, the others did not
        first = orders[0]
        h.adapter.submit(first["symbol"], first["contracts"], first["side"], "MOO",
                         {"bid": 4000.0, "ask": 4000.25}, note="partial")
        st["pending_dispatch"] = {"step": ENTRY, "orders": orders,
                                  "started_at": "2023-12-26T09:29:55"}
        with open(h.state_path, "w", encoding="utf-8") as fh:
            json.dump(st, fh)

        h.crash_and_restart()
        r = h.svc.tick()
        assert r["action"] == "RECOVER"
        assert "PARTIAL" in r["outcome"], r["outcome"]
        assert not h.adapter.positions(), "partial position was not flattened"
        assert h.raw_state()["contaminated"] is True
        assert h.raw_state()["phase"] == SETTLED
    finally:
        h.cleanup()


def test_crash_during_exit_leaves_no_open_position():
    h = Harness()
    try:
        run_to_armed(h)
        h.at("2023-12-26T09:29:56")
        h.svc.tick()
        assert h.adapter.positions()

        st = h.raw_state()
        st["pending_dispatch"] = {
            "step": EXIT,
            "orders": [{"symbol": o["symbol"], "series": o["series"],
                        "contracts": o["contracts"], "side": -o["side"]}
                       for o in st["sizing"]["orders"]],
            "started_at": "2023-12-29T15:59:30"}
        with open(h.state_path, "w", encoding="utf-8") as fh:
            json.dump(st, fh)

        h.crash_and_restart()
        r = h.svc.tick()
        assert r["action"] == "RECOVER"
        assert "incomplete" in r["outcome"], r["outcome"]
        assert not h.adapter.positions(), "exit recovery left a position open"
        assert h.raw_state()["phase"] == SETTLED
        assert h.raw_state()["contaminated"] is True
    finally:
        h.cleanup()


def test_unparseable_state_refuses_to_start():
    h = Harness()
    try:
        run_to_armed(h)
        with open(h.state_path, "w", encoding="utf-8") as fh:
            fh.write('{"phase": "ARM')          # truncated, as a mid-write crash
        try:
            h.crash_and_restart()
            assert False, "expected a refusal to start on unreadable state"
        except RuntimeError as e:
            assert "Refusing to start" in str(e)
    finally:
        h.cleanup()


def test_sentinel_flatten_marks_contaminated_and_settles():
    h = Harness()
    try:
        run_to_armed(h)
        h.at("2023-12-26T09:29:56")
        h.svc.tick()
        assert h.svc.state["phase"] == IN_TRADE
        entry_eq = h.adapter.equity(h.marks)

        # Drive marks ADVERSELY. December 2023 signals are all SHORT (z > 0), and
        # the adverse direction for a short is price UP, not down.
        pos = h.adapter.positions()
        assert all(q < 0 for q in pos.values()), pos
        for sym, q in pos.items():
            px = next(o["price"] for o in h.svc.state["sizing"]["orders"]
                      if o["symbol"] == sym)
            h.marks[sym] = px * (0.70 if q > 0 else 1.30)
        dd = h.adapter.equity(h.marks) / entry_eq - 1.0
        assert dd < -0.10, dd

        r = h.svc.tick()
        assert r["action"] == "SENTINEL_FLATTEN", r
        assert not h.adapter.positions()
        assert h.raw_state()["contaminated"] is True
        assert h.raw_state()["phase"] == SETTLED
    finally:
        h.cleanup()


def test_entry_aborts_if_session_turns_out_closed():
    """confirm_open() must stop an order going into a shut market."""
    h = Harness()
    try:
        run_to_armed(h)
        h.svc.state["plan"]["entry"] = "2012-10-29"     # Hurricane Sandy closure
        h.svc._persist()
        h.at("2023-12-26T09:29:56")
        h.svc.state["plan"]["exit"] = "2023-12-29"
        r = h.svc._do_entry()
        assert r.get("aborted") is True
        assert not h.adapter.positions()
    finally:
        h.cleanup()


def test_month_does_not_roll_while_in_trade():
    h = Harness()
    try:
        run_to_armed(h)
        h.at("2023-12-26T09:29:56")
        h.svc.tick()
        assert h.svc.state["phase"] == IN_TRADE
        h.at("2024-01-15T12:00:00")      # calendar turns while still holding
        r = h.svc.tick()
        assert r["action"] == "HOLD", r
        assert h.svc.state["month"] == MONTH
        assert h.adapter.positions()
    finally:
        h.cleanup()


def test_telemetry_shape_matches_contract():
    h = Harness()
    try:
        run_to_armed(h)
        h.at("2023-12-26T09:29:56")
        h.svc.tick()
        t = h.svc.telemetry()
        for k in ("module", "status", "phase", "next_event", "formation_z",
                  "active_direction", "sizing", "execution_audit"):
            assert k in t, k
        assert t["module"] == "cme_rebal_flow"
        assert t["status"] == "CANDIDATE"
        assert t["arm_mode"] == "EXPERIMENT"
        assert set(t["formation_z"]) <= {"ES", "YM", "RTY"}
        for k in ("equity", "governor_active", "governed_multiple", "contracts"):
            assert k in t["sizing"], k
        for k in ("last_fill_M", "tracking_error_bp"):
            assert k in t["execution_audit"], k
        assert t["phase"] == IN_TRADE
    finally:
        h.cleanup()


def test_api_status_degrades_when_daemon_never_ran():
    from app.api.routes import rebal as R
    old = R.STATE_PATH
    R.STATE_PATH = os.path.join(tempfile.mkdtemp(), "absent.json")
    try:
        s = R.build_status()
        assert s["healthy"] is False
        assert s["phase"] == "UNKNOWN", "a dead daemon must not report IDLE"
        assert s["status"] == "CANDIDATE"
    finally:
        R.STATE_PATH = old


def test_next_event_and_sleep_are_bounded():
    h = Harness()
    try:
        h.at("2023-12-22T16:20:00")
        h.svc.tick()
        n = h.svc.next_event()
        assert n and n["action"] == "COMPUTE_SIZING", n
        s = h.svc.seconds_to_sleep(cap=900.0)
        assert 1.0 <= s <= 900.0, s
    finally:
        h.cleanup()


def test_zero_holdout_reads():
    n = sum(1 for _ in open("prereg/HOLDOUT_ACCESS.log", encoding="utf-8"))
    assert n == 2, f"HOLDOUT_ACCESS.log grew to {n} lines"


if __name__ == "__main__":
    import contextlib, io, traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = failed = 0
    for t in tests:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {type(e).__name__}: {e}")
            traceback.print_exc(limit=2)
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
