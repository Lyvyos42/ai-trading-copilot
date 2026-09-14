"""
GET /api/rebal/status  and  WS /api/rebal/stream — IEF month-end daemon telemetry.

Read-only. This endpoint reports what the daemon is doing; it never places,
cancels or resizes an order. Trading decisions belong to ief/service.py alone,
and an HTTP surface that could trigger them would put order dispatch one
misrouted request away.

EVERY PAYLOAD CARRIES status AND arm_mode.
`cme_rebal_flow` is CANDIDATE, not VALIDATED: measured edge +30.06 bp with a 95%
CI of [+1.89, +58.23], Gates 1/2/3A/3B/3C and Control C pass, Gate 4 fails on one
era. The UI must not render a P&L figure without the CANDIDATE label attached,
which is the specific failure core/evidence.py was written to prevent.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/api/rebal", tags=["rebal"])

STATE_PATH = os.environ.get("IEF_REBAL_STATE", "data/rebal_state.json")
LOG_PATH = os.environ.get("IEF_REBAL_LOG", "logs/ief_rebal_execution.log")
SCHEDULE = os.environ.get("IEF_SCHEDULE", "ief/data/exchange_holidays.csv")

_SYM = {"es_daily": "ES", "ym_daily": "YM", "rty_daily": "RTY"}


def _degraded(reason: str) -> dict:
    """A daemon that has never run is reported as UNKNOWN, never as IDLE.

    IDLE means "running, waiting for the next window". Reporting a dead or
    never-started daemon as IDLE would make a stopped service indistinguishable
    from a healthy one on the dashboard.
    """
    return {
        "module": "cme_rebal_flow", "status": "CANDIDATE", "arm_mode": "EXPERIMENT",
        "phase": "UNKNOWN", "healthy": False, "reason": reason,
        "month": None, "next_event": None, "formation_z": {},
        "active_direction": None,
        "sizing": {"equity": None, "governor_active": None,
                   "governed_multiple": None, "contracts": {}},
        "positions": {}, "execution_audit": {"fills": 0, "last_fill_M": None,
                                             "tracking_error_bp": None},
        "contaminated": False,
        "served_at": datetime.now(timezone.utc).isoformat(),
    }


def _next_event_from_state(state: dict) -> dict | None:
    """Recompute the next window from the schedule without importing the service,
    so the API stays readable even if the daemon process is down."""
    try:
        from ief.calendar_daemon import CalendarDaemon
        from ief.service import (IDLE, PH_FORMATION, ARMED, IN_TRADE,
                                 T_FORMATION, T_SIZING, T_ENTRY, T_EXIT, ET)
        import datetime as dt
        plan = state.get("plan")
        if not plan:
            return None
        phase = state.get("phase", IDLE)
        table = {
            IDLE: (plan["formation"], T_FORMATION, "T-5", "CALCULATE_FORMATION"),
            PH_FORMATION: (plan["entry"], T_SIZING, "T-4", "COMPUTE_SIZING"),
            ARMED: (plan["entry"], T_ENTRY, "T-4", "DISPATCH_ENTRY"),
            IN_TRADE: (plan["exit"], T_EXIT, "T", "DISPATCH_EXIT"),
        }
        if phase not in table:
            return None
        date, tm, label, action = table[phase]
        when = dt.datetime.combine(dt.date.fromisoformat(date), tm, tzinfo=ET)
        now = dt.datetime.now(tz=ET)
        return {"session": label, "date": date, "action": action,
                "at": when.isoformat(),
                "seconds_until": max(0.0, (when - now).total_seconds())}
    except Exception:
        return None


def _audit_from_log(limit: int = 400) -> dict:
    """Slippage audit read from the execution log, so telemetry survives a daemon
    restart that cleared in-memory fills."""
    if not os.path.exists(LOG_PATH):
        return {"fills": 0, "last_fill_M": None, "mean_M": None,
                "m_measured": 1.0829, "tracking_error_bp": None}
    ms, bps = [], []
    try:
        with open(LOG_PATH, encoding="utf-8") as fh:
            rows = fh.readlines()[-limit:]
        for line in rows:
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "m_realised" in r:
                ms.append(float(r["m_realised"]))
                bps.append(float(r.get("slippage_bp", 0.0)))
    except OSError:
        return {"fills": 0, "last_fill_M": None, "mean_M": None,
                "m_measured": 1.0829, "tracking_error_bp": None}
    if not ms:
        return {"fills": 0, "last_fill_M": None, "mean_M": None,
                "m_measured": 1.0829, "tracking_error_bp": None}
    return {"fills": len(ms), "last_fill_M": round(ms[-1], 4),
            "mean_M": round(sum(ms) / len(ms), 4), "m_measured": 1.0829,
            "m_excess": round(sum(ms) / len(ms) - 1.0829, 4),
            "tracking_error_bp": round(sum(bps) / len(bps), 4)}


def build_status() -> dict:
    if not os.path.exists(STATE_PATH):
        return _degraded(f"no daemon state at {STATE_PATH}; service has never run")
    try:
        with open(STATE_PATH, encoding="utf-8") as fh:
            state = json.load(fh)
    except (json.JSONDecodeError, OSError) as e:
        return _degraded(f"state file unreadable: {e}")

    sz = state.get("sizing") or {}
    form = state.get("formation") or {}
    weights = form.get("weights") or {}
    direction = None
    if weights:
        direction = "LONG" if sum(weights.values()) > 0 else "SHORT"

    stale = None
    if state.get("updated_at"):
        try:
            age = (datetime.now(timezone.utc)
                   - datetime.fromisoformat(state["updated_at"]).astimezone(timezone.utc))
            stale = round(age.total_seconds(), 1)
        except ValueError:
            stale = None

    return {
        "module": "cme_rebal_flow",
        "status": "CANDIDATE",
        "arm_mode": "EXPERIMENT",
        "healthy": True,
        "phase": state.get("phase", "UNKNOWN"),
        "month": state.get("month"),
        "next_event": _next_event_from_state(state),
        "formation_z": {_SYM.get(k, k): round(v, 4)
                        for k, v in (form.get("z") or {}).items()},
        "active_direction": direction,
        "sizing": {
            "equity": sz.get("equity"),
            "mode": sz.get("mode"),
            "governor_active": sz.get("governor_active"),
            "governed_multiple": (round(sz["k_effective"], 4)
                                  if sz.get("k_effective") is not None else None),
            "gross_leverage": (round(sz["gross_leverage"], 4)
                               if sz.get("gross_leverage") is not None else None),
            "contracts": {o["symbol"]: o["contracts"] for o in sz.get("orders", [])},
            "warnings": sz.get("warnings", []),
        },
        "positions": state.get("positions", {}),
        "execution_audit": _audit_from_log(),
        "sentinel": state.get("sentinel", {}),
        "contaminated": state.get("contaminated", False),
        "pending_dispatch": state.get("pending_dispatch"),
        "history": (state.get("history") or [])[-6:],
        "state_age_seconds": stale,
        "served_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/status")
async def rebal_status() -> dict:
    return build_status()


@router.websocket("/stream")
async def rebal_stream(websocket: WebSocket) -> None:
    """Pushes the status payload on change, plus a keepalive every 30s.

    Diffed on the serialised payload so an idle daemon does not spam the socket
    while a phase transition reaches the UI immediately.
    """
    await websocket.accept()
    last = None
    idle_ticks = 0
    try:
        while True:
            payload = build_status()
            blob = json.dumps(payload, sort_keys=True, default=str)
            if blob != last:
                await websocket.send_json({"type": "status", "data": payload})
                last = blob
                idle_ticks = 0
            else:
                idle_ticks += 1
                if idle_ticks >= 15:
                    await websocket.send_json(
                        {"type": "ping",
                         "ts": datetime.now(timezone.utc).isoformat()})
                    idle_ticks = 0
            await asyncio.sleep(2.0)
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass
