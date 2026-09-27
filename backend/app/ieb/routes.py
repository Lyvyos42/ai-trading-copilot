"""
IEB <-> Copilot bridge API and Signal Lab views.

Signed (Ed25519, app/ieb/auth.py) - only an IEB installation can write:
    POST /api/v1/ieb/signals     batch of signals      -> per item: accepted | duplicate | invalid
    POST /api/v1/ieb/outcomes    batch of outcomes     -> accepted | duplicate | invalid
    POST /api/v1/ieb/executions  batch of executions   -> accepted | duplicate | invalid
    POST /api/v1/ieb/modules     module registry rows  -> created | unchanged | updated
    POST /api/v1/ieb/telegram    Telegram message ids for signals / outcomes (public-record traceability)
    POST /api/v1/ieb/heartbeat   health; the response carries the configuration for that instance
                                 (the Copilot -> IEB path: IEB polls, nothing connects into the PC)
    A bad or missing signature answers 401 {"status": "unauthorized"}.

Public, read-only (aggregates and the signal records the public channel already shows):
    GET /api/v1/ieb/status            CONNECTED | DEGRADED | OFFLINE | PAUSED | UNAUTHENTICATED per instance
    GET /api/v1/ieb/signals/recent    newest IEB signals with module, version and outcome
    GET /api/v1/lab/modules           registry + research card per module version (IEB and Copilot)
    GET /api/v1/lab/score             Consensus Score research for the Copilot signal generators
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.ieb import research as R
from app.ieb.auth import verify
from app.ieb.models import IebExecution, IebInstance, IebSignal, SignalModule
from app.models.signal import Signal

router = APIRouter(prefix="/api/v1/ieb", tags=["ieb-bridge"])
lab_router = APIRouter(prefix="/api/v1/lab", tags=["signal-lab"])

MODULE_STATUSES = {"LIVE", "BETA", "SHADOW", "RESEARCH", "PAUSED", "DISABLED", "RETIRED"}
ID_RE = re.compile(r"^[A-Za-z0-9:_.\-]{8,80}$")
HEARTBEAT_OK_SECONDS = 180
DEFAULT_CONFIG = {
    "automation_enabled": False,
    "selected_modules": None,
    "selected_symbols": None,
    "risk_profile": None,
    "execution_profile": None,
    "prop_profile": None,
    "max_risk": None,
    "_note": "Prepared for Copilot -> IEB control. IEB records this and acts on none of it yet; "
             "the local instance remains the execution authority for MT5.",
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _utc(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None                                  # a naive time is ambiguous: refused
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _num(value: Any, required: bool = False) -> float | None:
    if value is None:
        if required:
            raise ValueError("missing number")
        return None
    x = float(value)
    if not math.isfinite(x):
        raise ValueError("not a finite number")
    return x


async def _instance(db: AsyncSession, instance_id: str) -> IebInstance:
    inst = await db.get(IebInstance, instance_id)
    if inst is None:
        inst = IebInstance(instance_id=instance_id, backlog={}, modules_active=[], config=dict(DEFAULT_CONFIG))
        db.add(inst)
    return inst


async def _authenticate(request: Request, db: AsyncSession) -> str:
    body = await request.body()
    res = verify(request.method, request.url.path, {k.lower(): v for k, v in request.headers.items()}, body)
    if not res.ok:
        if res.instance_id and res.reason != "unknown instance":
            inst = await _instance(db, res.instance_id)
            inst.last_auth_failure_at = _now()
            inst.last_error, inst.last_error_at = f"auth: {res.reason}", _now()
            await db.commit()
        raise HTTPException(status_code=401, detail={"status": "unauthorized", "reason": res.reason})
    return res.instance_id


async def _mark_ok(db: AsyncSession, instance_id: str, signal: bool = False) -> None:
    inst = await _instance(db, instance_id)
    inst.last_request_ok_at = _now()
    if signal:
        inst.last_signal_at = _now()


# ── ingestion ─────────────────────────────────────────────────────────────────
CORE_FIELDS = ("module_id", "module_version", "signal_version", "generated_at", "symbol", "direction",
               "entry_reference", "stop_reference", "tp1")


def _signal_row(item: dict, instance_id: str) -> IebSignal:
    sid = str(item.get("signal_id") or "")
    if not ID_RE.match(sid):
        raise ValueError("signal_id missing or malformed")
    for f in ("module_id", "module_version", "signal_version", "symbol", "source"):
        if not item.get(f) or len(str(item[f])) > 80:
            raise ValueError(f"{f} missing or too long")
    direction = str(item.get("direction", "")).upper()
    direction = {"BUY": "LONG", "SELL": "SHORT"}.get(direction, direction)
    if direction not in ("LONG", "SHORT"):
        raise ValueError("direction must be LONG/SHORT (or BUY/SELL)")
    generated = _utc(item.get("generated_at"))
    if generated is None:
        raise ValueError("generated_at must be an ISO time with a UTC offset")
    score = _num(item.get("consensus_score"))
    if score is not None and not 0 <= score <= 100:
        raise ValueError("consensus_score must be 0-100")
    return IebSignal(
        signal_id=sid, instance_id=instance_id,
        module_id=str(item["module_id"]), module_version=str(item["module_version"]),
        signal_version=str(item["signal_version"]), generated_at=generated,
        symbol=str(item["symbol"])[:32], timeframe=(str(item["timeframe"])[:16] if item.get("timeframe") else None),
        direction=direction, consensus_score=score, score_definition=item.get("score_definition"),
        historical_outcome_rate=_num(item.get("historical_outcome_rate")),
        outcome_rate_sample=int(item["outcome_rate_sample"]) if item.get("outcome_rate_sample") is not None else None,
        outcome_rate_definition=item.get("outcome_rate_definition"),
        entry_reference=_num(item.get("entry_reference"), required=True), entry_basis=item.get("entry_basis"),
        stop_reference=_num(item.get("stop_reference")), tp1=_num(item.get("tp1")), tp2=_num(item.get("tp2")),
        expected_horizon=(str(item["expected_horizon"])[:160] if item.get("expected_horizon") else None),
        market_state=item.get("market_state"), session=item.get("session"),
        context=item.get("context") if isinstance(item.get("context"), dict) else {},
        invalidation=_num(item.get("invalidation")), source=str(item["source"])[:40],
        extras=item.get("extras") if isinstance(item.get("extras"), dict) else {},
    )


def _same_core(row: IebSignal, new: IebSignal) -> bool:
    return all(getattr(row, f) == getattr(new, f) for f in CORE_FIELDS)


@router.post("/signals")
async def ingest_signals(request: Request, db: AsyncSession = Depends(get_db)):
    instance_id = await _authenticate(request, db)
    items = (await request.json()).get("signals") or []
    results, accepted = [], 0
    for item in items[:500]:
        sid = str(item.get("signal_id") or "")
        try:
            new = _signal_row(item, instance_id)
        except (ValueError, TypeError, KeyError) as exc:
            results.append({"signal_id": sid, "status": "invalid", "reason": str(exc)})
            continue
        existing = await db.get(IebSignal, new.signal_id)
        if existing is not None:
            results.append({"signal_id": sid, "status": "duplicate",
                            **({} if _same_core(existing, new) else {"conflict": "stored record differs; the first one is kept"})})
            continue
        db.add(new)
        await db.flush()
        accepted += 1
        results.append({"signal_id": sid, "status": "accepted"})
    await _mark_ok(db, instance_id, signal=accepted > 0)
    await db.commit()
    return {"results": results}


@router.post("/outcomes")
async def ingest_outcomes(request: Request, db: AsyncSession = Depends(get_db)):
    instance_id = await _authenticate(request, db)
    items = (await request.json()).get("outcomes") or []
    results = []
    for item in items[:500]:
        sid = str(item.get("signal_id") or "")
        row = await db.get(IebSignal, sid) if sid else None
        if row is None:
            results.append({"signal_id": sid, "status": "invalid", "reason": "unknown signal_id"})
            continue
        try:
            reason = str(item.get("exit_reason") or "")
            if reason not in ("target", "stop", "other", "unknown", "no_stop"):
                raise ValueError("exit_reason must be target/stop/other/unknown/no_stop")
            fields = dict(
                exit_reason=reason, exit_reference=_num(item.get("exit_reference")),
                exit_timestamp=_utc(item.get("exit_timestamp")), r_multiple=_num(item.get("r_multiple")),
                mfe_r=_num(item.get("mfe_r")), mae_r=_num(item.get("mae_r")),
                holding_minutes=_num(item.get("holding_minutes")),
                target_hit=item.get("target_hit"), stop_hit=item.get("stop_hit"),
                direction_correct=item.get("direction_correct"))
        except (ValueError, TypeError) as exc:
            results.append({"signal_id": sid, "status": "invalid", "reason": str(exc)})
            continue
        if row.resolved:
            same = row.exit_reason == fields["exit_reason"] and row.r_multiple == fields["r_multiple"]
            results.append({"signal_id": sid, "status": "duplicate",
                            **({} if same else {"conflict": "outcome already recorded; the first one is kept"})})
            continue
        for k, v in fields.items():
            setattr(row, k, v)
        row.resolved, row.outcome_received_at = True, _now()
        results.append({"signal_id": sid, "status": "accepted"})
    await _mark_ok(db, instance_id)
    await db.commit()
    return {"results": results}


@router.post("/executions")
async def ingest_executions(request: Request, db: AsyncSession = Depends(get_db)):
    instance_id = await _authenticate(request, db)
    items = (await request.json()).get("executions") or []
    results = []
    for item in items[:500]:
        eid = str(item.get("execution_id") or "")
        sid = str(item.get("signal_id") or "")
        if not ID_RE.match(eid) or await db.get(IebSignal, sid) is None:
            results.append({"execution_id": eid, "status": "invalid", "reason": "bad execution_id or unknown signal_id"})
            continue
        if await db.get(IebExecution, eid) is not None:
            results.append({"execution_id": eid, "status": "duplicate"})
            continue
        try:
            db.add(IebExecution(
                execution_id=eid, signal_id=sid, instance_id=instance_id,
                execution_mode=str(item.get("execution_mode") or "unknown")[:32],
                account_ref=(str(item["account_ref"])[:64] if item.get("account_ref") else None),
                entry=_num(item.get("entry")), exit=_num(item.get("exit")), stop=_num(item.get("stop")),
                target=_num(item.get("target")), volume=_num(item.get("volume")), pnl=_num(item.get("pnl")),
                r_multiple=_num(item.get("r_multiple")), mae=_num(item.get("mae")), mfe=_num(item.get("mfe")),
                exit_reason=(str(item["exit_reason"])[:32] if item.get("exit_reason") else None),
                timestamp=_utc(item.get("timestamp")),
                execution_profile=(str(item["execution_profile"])[:64] if item.get("execution_profile") else None)))
            await db.flush()
        except (ValueError, TypeError) as exc:
            results.append({"execution_id": eid, "status": "invalid", "reason": str(exc)})
            continue
        results.append({"execution_id": eid, "status": "accepted"})
    await _mark_ok(db, instance_id)
    await db.commit()
    return {"results": results}


@router.post("/modules")
async def upsert_modules(request: Request, db: AsyncSession = Depends(get_db)):
    instance_id = await _authenticate(request, db)
    items = (await request.json()).get("modules") or []
    results = []
    for m in items[:200]:
        mid, ver = str(m.get("module_id") or ""), str(m.get("version") or "")
        status = str(m.get("status") or "").upper()
        if not mid or not ver or status not in MODULE_STATUSES:
            results.append({"module_id": mid, "version": ver, "status": "invalid"})
            continue
        row = await db.get(SignalModule, (mid, ver))
        vals = dict(source="ieb", module_name=str(m.get("module_name") or mid)[:120],
                    module_type=str(m.get("module_type") or "rule_based")[:40], status=status,
                    description=m.get("description"), timeframes=m.get("timeframes") or [],
                    symbols=m.get("symbols") or [], signal_logic_reference=m.get("signal_logic_reference"),
                    score_definition=m.get("score_definition"), outcome_definition=m.get("outcome_definition"),
                    parameters=m.get("parameters") or {})
        if row is None:
            db.add(SignalModule(module_id=mid, version=ver, **vals))
            results.append({"module_id": mid, "version": ver, "status": "created"})
        else:
            changed = any(getattr(row, k) != v for k, v in vals.items())
            for k, v in vals.items():
                setattr(row, k, v)
            results.append({"module_id": mid, "version": ver, "status": "updated" if changed else "unchanged"})
    await _mark_ok(db, instance_id)
    await db.commit()
    return {"results": results}


@router.post("/telegram")
async def record_telegram(request: Request, db: AsyncSession = Depends(get_db)):
    instance_id = await _authenticate(request, db)
    items = (await request.json()).get("items") or []
    results = []
    for it in items[:500]:
        row = await db.get(IebSignal, str(it.get("signal_id") or ""))
        if row is None or it.get("kind") not in ("signal", "outcome"):
            results.append({"signal_id": it.get("signal_id"), "status": "invalid"})
            continue
        attr = "telegram_message_id" if it["kind"] == "signal" else "telegram_outcome_message_id"
        if getattr(row, attr) is not None:
            results.append({"signal_id": row.signal_id, "status": "duplicate"})
            continue
        setattr(row, attr, int(it["message_id"]))
        results.append({"signal_id": row.signal_id, "status": "accepted"})
    await _mark_ok(db, instance_id)
    await db.commit()
    return {"results": results}


@router.post("/heartbeat")
async def heartbeat(request: Request, db: AsyncSession = Depends(get_db)):
    instance_id = await _authenticate(request, db)
    body = await request.json()
    inst = await _instance(db, instance_id)
    inst.last_heartbeat = inst.last_request_ok_at = _now()
    inst.paused = bool(body.get("paused"))
    inst.version = str(body.get("version") or "")[:64] or None
    inst.backlog = body.get("backlog") if isinstance(body.get("backlog"), dict) else {}
    inst.modules_active = body.get("modules_active") if isinstance(body.get("modules_active"), list) else []
    if body.get("last_error"):
        inst.last_error, inst.last_error_at = str(body["last_error"])[:500], _now()
    if not inst.config:
        inst.config = dict(DEFAULT_CONFIG)
    await db.commit()
    return {"status": "ok", "config": inst.config, "server_time": _now().isoformat() + "Z"}


# ── read side ────────────────────────────────────────────────────────────────
def connection_state(inst: IebInstance, now: datetime | None = None) -> str:
    now = now or _now()
    if inst.last_auth_failure_at and (inst.last_request_ok_at is None or inst.last_auth_failure_at > inst.last_request_ok_at):
        return "UNAUTHENTICATED"
    if inst.paused:
        return "PAUSED"                              # switched off in IEB on purpose
    if inst.last_heartbeat is None or now - inst.last_heartbeat > timedelta(seconds=HEARTBEAT_OK_SECONDS):
        return "OFFLINE"
    pending = sum(int(v) for v in (inst.backlog or {}).values() if isinstance(v, (int, float)))
    # errors the instance itself reported in the last 10 minutes; a rejected (unauthenticated) request
    # shows as UNAUTHENTICATED above until the next good one - anyone can put an instance id on a request
    recent_error = bool(inst.last_error_at and now - inst.last_error_at < timedelta(minutes=10)
                        and not (inst.last_error or "").startswith("auth:"))
    if pending > 50 or recent_error:
        return "DEGRADED"
    return "CONNECTED"


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() + "Z" if dt else None


@router.get("/status")
async def status(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(IebInstance))).scalars().all()
    return {"instances": [{
        "instance_id": i.instance_id, "state": connection_state(i), "version": i.version,
        "last_heartbeat": _iso(i.last_heartbeat), "last_signal_received": _iso(i.last_signal_at),
        "last_successful_request": _iso(i.last_request_ok_at), "last_error": i.last_error,
        "last_error_at": _iso(i.last_error_at), "backlog": i.backlog, "modules_active": i.modules_active,
    } for i in rows], "server_time": _now().isoformat() + "Z"}


def _public_signal(s: IebSignal) -> dict:
    return {
        "signal_id": s.signal_id, "module_id": s.module_id, "module_version": s.module_version,
        "signal_version": s.signal_version, "generated_at": _iso(s.generated_at), "symbol": s.symbol,
        "timeframe": s.timeframe, "direction": s.direction, "consensus_score": s.consensus_score,
        "historical_outcome_rate": s.historical_outcome_rate, "outcome_rate_sample": s.outcome_rate_sample,
        "entry_reference": s.entry_reference, "stop_reference": s.stop_reference, "tp1": s.tp1, "tp2": s.tp2,
        "expected_horizon": s.expected_horizon, "session": s.session, "source": s.source,
        "resolved": s.resolved, "exit_reason": s.exit_reason, "r_multiple": s.r_multiple,
        "exit_timestamp": _iso(s.exit_timestamp), "on_telegram": s.telegram_message_id is not None,
    }


@router.get("/signals/recent")
async def recent_signals(limit: int = 50, source: str | None = None, db: AsyncSession = Depends(get_db)):
    q = select(IebSignal).order_by(IebSignal.generated_at.desc()).limit(max(1, min(limit, 200)))
    if source:
        q = q.where(IebSignal.source == source)
    rows = (await db.execute(q)).scalars().all()
    return {"signals": [_public_signal(s) for s in rows]}


# ── Signal Lab ───────────────────────────────────────────────────────────────
_UNSCORED = ("FILTERED", "VOID", "RISK_GATE_BLOCKED", "MARKET_CLOSED")
COPILOT_MODULES = {
    "AI": ("copilot_ai", "Copilot multi-agent signal", "BETA"),
    "AUTOMATED": ("copilot_automated", "Copilot deterministic fallback (no LLM layer)", "BETA"),
    "AUTO_SCAN": ("copilot_auto_scan", "Copilot auto-scanner", "BETA"),
}
COPILOT_SCORE_DEF = ("Consensus Score: share of the analysts' weighted votes on the signal's side "
                     "(probability_score in app/agents/trader.py). Not a probability.")
COPILOT_OUTCOME_DEF = ("TP1 reached before the stop within the analytical window, resolved on real price bars "
                       "(app/services/signal_resolver.py); R = signed move entry->exit / entry->stop.")


def _ieb_rec(s: IebSignal) -> dict:
    return {"resolved": s.resolved, "exit_reason": s.exit_reason, "r_multiple": s.r_multiple,
            "direction_correct": s.direction_correct, "mfe_r": s.mfe_r, "mae_r": s.mae_r,
            "holding_minutes": s.holding_minutes, "consensus_score": s.consensus_score, "symbol": s.symbol,
            "session": s.session, "timeframe": s.timeframe, "module_version": s.module_version,
            "weekday": s.generated_at.strftime("%a") if s.generated_at else None, "source": s.source}


def _copilot_rec(s: Signal) -> dict:
    d = (s.direction or "").upper()
    sgn = 1 if d in ("LONG", "BUY", "BULLISH") else -1 if d in ("SHORT", "SELL", "BEARISH") else 0
    vs = None
    if s.probability_score is not None and sgn:
        vs = float(s.probability_score) if sgn > 0 else 100.0 - float(s.probability_score)
    outcome = s.outcome
    reason = {"WIN": "target", "LOSS": "stop", "EXPIRED": "other"}.get(outcome or "", None)
    r = None
    if reason and s.exit_price is not None and s.stop_loss and sgn and abs(s.entry_price - s.stop_loss) > 0:
        r = sgn * (s.exit_price - s.entry_price) / abs(s.entry_price - s.stop_loss)
    hold = ((s.resolved_at - s.created_at).total_seconds() / 60.0) if (s.resolved_at and s.created_at) else None
    return {"resolved": reason is not None, "exit_reason": reason, "r_multiple": r,
            "direction_correct": (r > 0) if r is not None else None, "mfe_r": None, "mae_r": None,
            "holding_minutes": hold, "consensus_score": vs, "symbol": s.ticker, "session": None,
            "timeframe": s.timeframe, "module_version": s.signal_version or "unversioned (before 2026-09-27)",
            "weekday": s.created_at.strftime("%a") if s.created_at else None,
            "direction_vs_votes": ("disagrees" if vs is not None and vs < 50 else "agrees" if vs is not None else None)}


def _population(recs: list[dict]) -> dict:
    c = R.card(recs)
    dims = {"symbol": R.breakdown(recs, "symbol"), "session": R.breakdown(recs, "session"),
            "timeframe": R.breakdown(recs, "timeframe"), "weekday": R.breakdown(recs, "weekday")}
    return {"card": c, "breakdowns": dims, "finding": R.finding(c, {k: v for k, v in dims.items() if k != "weekday"})}


@lab_router.get("/modules")
async def lab_modules(db: AsyncSession = Depends(get_db)):
    registry = (await db.execute(select(SignalModule))).scalars().all()
    ieb_rows = (await db.execute(select(IebSignal))).scalars().all()
    cop_rows = (await db.execute(select(Signal).where(Signal.status.notin_(_UNSCORED)))).scalars().all()

    pops: dict[tuple[str, str], list[dict]] = {}
    for s in ieb_rows:
        pops.setdefault((s.module_id, s.module_version), []).append(_ieb_rec(s))
    cop_version_counts: dict[str, dict[str, int]] = {}
    for s in cop_rows:
        mode = s.signal_mode or "AI"
        mid = COPILOT_MODULES.get(mode, (f"copilot_{mode.lower()}",))[0]
        rec = _copilot_rec(s)
        pops.setdefault((mid, rec["module_version"]), []).append(rec)

    reg_by_key = {(m.module_id, m.version): m for m in registry}
    modules: dict[str, dict] = {}
    for m in registry:
        modules.setdefault(m.module_id, {"module_id": m.module_id, "source": m.source, "versions": {}})
    for mode, (mid, name, status_) in COPILOT_MODULES.items():
        modules.setdefault(mid, {"module_id": mid, "source": "copilot", "versions": {}})
    for (mid, ver), recs in pops.items():
        modules.setdefault(mid, {"module_id": mid, "source": "ieb", "versions": {}})
    for mid, mod in modules.items():
        keys = {v for (m_, v) in reg_by_key if m_ == mid} | {v for (m_, v) in pops if m_ == mid}
        for ver in sorted(keys):
            reg = reg_by_key.get((mid, ver))
            recs = pops.get((mid, ver), [])
            copilot_meta = next((c for c in COPILOT_MODULES.values() if c[0] == mid), None)
            entry = {
                "version": ver,
                "registry": ({"module_name": reg.module_name, "module_type": reg.module_type, "status": reg.status,
                              "description": reg.description, "timeframes": reg.timeframes, "symbols": reg.symbols,
                              "signal_logic_reference": reg.signal_logic_reference,
                              "score_definition": reg.score_definition, "outcome_definition": reg.outcome_definition}
                             if reg else ({"module_name": copilot_meta[1], "module_type": "multi_agent_consensus",
                                           "status": copilot_meta[2], "score_definition": COPILOT_SCORE_DEF,
                                           "outcome_definition": COPILOT_OUTCOME_DEF} if copilot_meta else None)),
                **_population(recs),
            }
            status_ = (entry["registry"] or {}).get("status")
            if ver == "unknown_at_backfill":
                fwd, why = False, "rebuilt from paper history - informative, not a forward record of one version"
            elif ver.startswith("unversioned"):
                fwd, why = False, "made before versioning - the code version that produced these is not known"
            else:
                fwd, why = True, None
            entry["promotion"] = R.promotion(status_, entry["card"], fwd, why)
            if mid.startswith("copilot_"):
                entry["direction_disagrees_with_votes"] = sum(1 for r in recs if r.get("direction_vs_votes") == "disagrees")
            mod["versions"][ver] = entry
    comparison = []
    for mid, mod in sorted(modules.items()):
        for ver, e in mod["versions"].items():
            c = e["card"]
            comparison.append({
                "module_id": mid, "version": ver, "status": (e["registry"] or {}).get("status"),
                "signals": c["signals"], "resolved": c["resolved"],
                "tp1_before_stop": c["tp1_before_stop"]["rate"], "tp1_n": c["tp1_before_stop"]["n"],
                "mean_r": c["r"]["mean"], "r_lo": c["r"]["lo"], "r_hi": c["r"]["hi"], "r_n": c["r"]["n"],
                "finding": e["finding"]["label"], "next_step": e["promotion"]["next"],
                "score": "none" if not c["score_distribution"]["n"] else "consensus score recorded",
            })
    return {"generated_at": _now().isoformat() + "Z", "definitions": R.__doc__, "modules": modules,
            "comparison": comparison, "pipeline": R.PIPELINE, "pipeline_rules": R.PIPELINE_RULES,
            "sample_rules": {"rate_half_width": R.RATE_HALF_WIDTH,
                                                        "mean_r_half_width": R.R_HALF_WIDTH,
                                                        "n_for_10pt_rate_at_p_0_5": R.n_for_rate_precision()}}


@lab_router.get("/score")
async def lab_score(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Signal).where(Signal.status.notin_(_UNSCORED)))).scalars().all()
    out = {}
    for mode, (mid, name, _) in COPILOT_MODULES.items():
        by_version: dict[str, list] = {}
        excluded = 0
        for s in rows:
            if (s.signal_mode or "AI") != mode:
                continue
            rec = _copilot_rec(s)
            if rec["exit_reason"] not in ("target", "stop") or rec["consensus_score"] is None:
                continue
            if rec["direction_vs_votes"] == "disagrees":
                excluded += 1
                continue
            by_version.setdefault(rec["module_version"], []).append((rec["consensus_score"], rec["exit_reason"] == "target"))
        out[mid] = {"name": name, "excluded_direction_against_votes": excluded,
                    "versions": {v: R.score_research(p) for v, p in by_version.items()}}
    return {"generated_at": _now().isoformat() + "Z", "score_definition": COPILOT_SCORE_DEF,
            "outcome_definition": "TP1 reached before the stop", "modules": out}
