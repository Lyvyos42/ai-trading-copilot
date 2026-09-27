"""IEB -> Copilot bridge: signed requests, idempotency, validation, outcomes, status and the lab views."""
import asyncio
import base64
import json
import time
import uuid
from datetime import datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models.user  # noqa: F401  (signals.user_id -> users.id)
from app.db.database import Base, get_db
from app.ieb import auth, research
from app.ieb import models as ieb_models
from app.ieb.routes import connection_state, lab_router, router
from app.models.signal import Signal

INSTANCE = "ieb-test-1"
KEY = Ed25519PrivateKey.generate()


@pytest.fixture()
def client(monkeypatch):
    pub = base64.b64encode(KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)).decode()
    monkeypatch.setitem(auth.TRUSTED_KEYS, INSTANCE, pub)
    auth._seen_nonces.clear()
    engine = create_async_engine("sqlite+aiosqlite://", connect_args={"check_same_thread": False},
                                 poolclass=StaticPool)

    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    asyncio.run(_init())
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _db():
        async with maker() as s:
            yield s

    app = FastAPI()
    app.include_router(router)
    app.include_router(lab_router)
    app.dependency_overrides[get_db] = _db
    with TestClient(app) as c:
        c.maker = maker
        yield c


def signed(client, path, payload, *, instance=INSTANCE, key=KEY, ts=None, nonce=None, tamper=False):
    body = json.dumps(payload).encode()
    ts = str(int(time.time())) if ts is None else ts
    nonce = nonce or uuid.uuid4().hex
    sig = base64.b64encode(key.sign(auth.canonical("POST", path, ts, nonce, body))).decode()
    if tamper:
        body = body.replace(b"LONG", b"SHORT")
    return client.post(path, content=body, headers={
        "content-type": "application/json", "x-ieb-instance": instance, "x-ieb-timestamp": ts,
        "x-ieb-nonce": nonce, "x-ieb-signature": sig})


def sig_payload(sid="sig_000000000001", **over):
    d = {"signal_id": sid, "module_id": "prim_fvg_h1", "module_version": "v-abc123", "signal_version": "v-abc123",
         "generated_at": "2026-09-25T13:00:00+00:00", "symbol": "EURUSD", "timeframe": "H1", "direction": "LONG",
         "entry_reference": 1.1000, "stop_reference": 1.0980, "tp1": 1.1040, "source": "ieb_live_demo",
         "consensus_score": None, "historical_outcome_rate": None, "session": "london"}
    d.update(over)
    return d


def test_signal_accepted_then_duplicate(client):
    r = signed(client, "/api/v1/ieb/signals", {"signals": [sig_payload()]})
    assert r.status_code == 200 and r.json()["results"][0]["status"] == "accepted"
    r = signed(client, "/api/v1/ieb/signals", {"signals": [sig_payload()]})
    assert r.json()["results"][0] == {"signal_id": "sig_000000000001", "status": "duplicate"}
    r = signed(client, "/api/v1/ieb/signals", {"signals": [sig_payload(entry_reference=1.2)]})
    assert r.json()["results"][0]["status"] == "duplicate" and "conflict" in r.json()["results"][0]
    recent = client.get("/api/v1/ieb/signals/recent").json()["signals"]
    assert len(recent) == 1 and recent[0]["module_version"] == "v-abc123" and recent[0]["entry_reference"] == 1.1


def test_invalid_items_are_reported_per_item(client):
    items = [sig_payload("bad id!"), sig_payload("sig_000000000002", direction="UP"),
             sig_payload("sig_000000000003", generated_at="2026-09-25T13:00:00"),
             sig_payload("sig_000000000004", entry_reference=float("nan")),
             sig_payload("sig_000000000005", direction="SELL")]
    body = json.loads(json.dumps({"signals": items}).replace("NaN", "null"))
    res = signed(client, "/api/v1/ieb/signals", body).json()["results"]
    assert [x["status"] for x in res] == ["invalid"] * 4 + ["accepted"]
    assert client.get("/api/v1/ieb/signals/recent").json()["signals"][0]["direction"] == "SHORT"


@pytest.mark.parametrize("kw,reason", [
    ({"tamper": True}, "invalid signature"),
    ({"ts": str(int(time.time()) - 1000)}, "timestamp outside the allowed window"),
    ({"instance": "someone-else"}, "unknown instance"),
    ({"key": Ed25519PrivateKey.generate()}, "invalid signature"),
])
def test_unauthorized_requests_are_rejected(client, kw, reason):
    r = signed(client, "/api/v1/ieb/signals", {"signals": [sig_payload()]}, **kw)
    assert r.status_code == 401 and r.json()["detail"]["reason"] == reason
    assert client.get("/api/v1/ieb/signals/recent").json()["signals"] == []


def test_replayed_nonce_is_rejected(client):
    n = uuid.uuid4().hex
    assert signed(client, "/api/v1/ieb/heartbeat", {}, nonce=n).status_code == 200
    r = signed(client, "/api/v1/ieb/heartbeat", {}, nonce=n)
    assert r.status_code == 401 and r.json()["detail"]["reason"] == "replayed request"


def test_outcome_attaches_once(client):
    signed(client, "/api/v1/ieb/signals", {"signals": [sig_payload()]})
    out = {"signal_id": "sig_000000000001", "exit_reason": "target", "exit_reference": 1.104, "r_multiple": 2.0,
           "exit_timestamp": "2026-09-25T15:00:00+00:00", "target_hit": True, "stop_hit": False,
           "direction_correct": True, "holding_minutes": 120}
    assert signed(client, "/api/v1/ieb/outcomes", {"outcomes": [out]}).json()["results"][0]["status"] == "accepted"
    again = signed(client, "/api/v1/ieb/outcomes", {"outcomes": [{**out, "r_multiple": -1.0}]}).json()["results"][0]
    assert again["status"] == "duplicate" and "conflict" in again
    unknown = signed(client, "/api/v1/ieb/outcomes", {"outcomes": [{**out, "signal_id": "sig_nope_00000"}]})
    assert unknown.json()["results"][0]["status"] == "invalid"
    s = client.get("/api/v1/ieb/signals/recent").json()["signals"][0]
    assert s["resolved"] and s["r_multiple"] == 2.0 and s["exit_reason"] == "target"


def test_telegram_ids_and_executions(client):
    signed(client, "/api/v1/ieb/signals", {"signals": [sig_payload()]})
    r = signed(client, "/api/v1/ieb/telegram", {"items": [{"signal_id": "sig_000000000001", "kind": "signal", "message_id": 42}]})
    assert r.json()["results"][0]["status"] == "accepted"
    assert client.get("/api/v1/ieb/signals/recent").json()["signals"][0]["on_telegram"] is True
    ex = {"execution_id": "exec_sig_000000000001", "signal_id": "sig_000000000001", "execution_mode": "ieb_paper",
          "entry": 1.1001, "exit": 1.1039, "pnl": None}
    assert signed(client, "/api/v1/ieb/executions", {"executions": [ex]}).json()["results"][0]["status"] == "accepted"
    assert signed(client, "/api/v1/ieb/executions", {"executions": [ex]}).json()["results"][0]["status"] == "duplicate"


def test_heartbeat_status_and_config(client):
    r = signed(client, "/api/v1/ieb/heartbeat", {"version": "ieb-test", "backlog": {"signals": 0}, "modules_active": ["a"]})
    assert r.status_code == 200 and r.json()["config"]["automation_enabled"] is False
    st = client.get("/api/v1/ieb/status").json()["instances"][0]
    assert st["instance_id"] == INSTANCE and st["state"] == "CONNECTED"
    signed(client, "/api/v1/ieb/heartbeat", {}, tamper=False, key=Ed25519PrivateKey.generate())
    assert client.get("/api/v1/ieb/status").json()["instances"][0]["state"] == "UNAUTHENTICATED"


def test_connection_state_rules():
    now = datetime(2026, 9, 27, 12, 0)
    i = ieb_models.IebInstance(instance_id="x", backlog={}, last_heartbeat=now - timedelta(seconds=60),
                               last_request_ok_at=now - timedelta(seconds=60))
    assert connection_state(i, now) == "CONNECTED"
    i.last_error, i.last_error_at = "auth: invalid signature", now - timedelta(seconds=30)
    assert connection_state(i, now) == "CONNECTED"          # a forged request does not degrade the instance
    i.last_error = "network error on /api/v1/ieb/signals"
    assert connection_state(i, now) == "DEGRADED"
    i.last_error, i.last_error_at = None, None
    i.backlog = {"signals": 80}
    assert connection_state(i, now) == "DEGRADED"
    i.backlog, i.last_heartbeat = {}, now - timedelta(minutes=10)
    assert connection_state(i, now) == "OFFLINE"


def test_module_registry_and_lab(client):
    mod = {"module_id": "prim_fvg_h1", "version": "v-abc123", "status": "SHADOW", "module_name": "FVG H1",
           "module_type": "rule_based"}
    assert signed(client, "/api/v1/ieb/modules", {"modules": [mod]}).json()["results"][0]["status"] == "created"
    assert signed(client, "/api/v1/ieb/modules", {"modules": [mod]}).json()["results"][0]["status"] == "unchanged"
    assert signed(client, "/api/v1/ieb/modules", {"modules": [{**mod, "status": "GREAT"}]}).json()["results"][0]["status"] == "invalid"
    signed(client, "/api/v1/ieb/signals", {"signals": [sig_payload()]})

    async def _add_copilot():
        async with client.maker() as s:
            s.add(Signal(ticker="AAPL", timeframe="1D", direction="LONG", entry_price=100, stop_loss=95, take_profit_1=110, take_profit_2=115, take_profit_3=120, confidence_score=60,
                         status="CLOSED", outcome="WIN", exit_price=110, probability_score=72,
                         signal_mode="AI", signal_version="copilot-abc1234",
                         created_at=datetime(2026, 9, 27, 10), resolved_at=datetime(2026, 9, 27, 14),
                         expiry_time=datetime(2026, 9, 28, 10)))
            await s.commit()
    asyncio.run(_add_copilot())

    lab = client.get("/api/v1/lab/modules").json()
    v = lab["modules"]["prim_fvg_h1"]["versions"]["v-abc123"]
    assert v["registry"]["status"] == "SHADOW" and v["card"]["signals"] == 1 and v["card"]["resolved"] == 0
    assert v["finding"]["label"] == "INSUFFICIENT_SAMPLE"
    cop = lab["modules"]["copilot_ai"]["versions"]["copilot-abc1234"]
    assert cop["card"]["r"]["mean"] == pytest.approx(2.0) and cop["registry"]["status"] == "BETA"
    score = client.get("/api/v1/lab/score").json()["modules"]["copilot_ai"]["versions"]["copilot-abc1234"]
    assert score["bands"][2]["band"] == "70-79" and score["bands"][2]["n"] == 1


def test_research_numbers():
    assert research.n_for_rate_precision() == 97
    lo, hi = research.wilson(5, 10)
    assert lo == pytest.approx(0.2366, abs=1e-3) and hi == pytest.approx(0.7634, abs=1e-3)
    assert research.auc([(80, True), (60, False)])["auc"] == 1.0
    assert research.auc([(80, True)])["auc"] is None
    neg = [{"resolved": True, "exit_reason": "stop", "r_multiple": -1.0 + 0.01 * i} for i in range(12)]
    assert research.finding(research.card(neg))["label"] == "NEGATIVE"
