"""
Quantitative strategies -> 9-agent consensus: end-to-end verification.

Hermetic. No network, no broker, no LLM: bars are synthetic and enter through the
pipeline's own injection seam (market_data["bars_by_interval"]), TradingView is
stubbed to refuse, and the trader runs its deterministic path.

What is verified
  1. SPY at month-end: cme_rebal_flow fires with the REGISTERED rule, is counted in
     the consensus, names itself in strategy_sources, sets the 4-SESSION horizon
     and its settlement time exit, and the final signal is clean JSON.
  2. cme_rebal_flow is causal: post-formation bars cannot change the formation z.
  3. EURUSD H4: meanrev fires on an extension composite >= 2.0 - as an OBSERVER,
     never in the vote list (its promotion criterion is unmet).
  4. XAUUSD: institutional_vwap (London anchor) fires on an outer-band
     pierce-and-reject on traded-volume bars, as an observer; the same bars with no
     volume abstain.
  5. ten_am_macro fires and is recorded, and cannot reach the tally.
  6. No bars from TradingView -> strategies abstain; nothing else is substituted.
  7. TradingView loader conversions: naive-local index, daily re-stamping, volume
     semantics and the CME-tape shift onto spot.
  8. No broker, account, lot or margin code in any touched module.

Run:  .venv/Scripts/python.exe tests/test_quantitative_signals_pipeline.py
      (or pytest, where installed)
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import random
import re
import sys
import types
from datetime import date, datetime, time as dtime, timedelta, timezone
from zoneinfo import ZoneInfo

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)

from ief.calendar_daemon import CalendarDaemon                     # noqa: E402
from app.agents import strategy_agent                              # noqa: E402
from app.data import tv_bars                                       # noqa: E402
from app.strategies import cme_rebal_flow as crf                   # noqa: E402
from app.strategies import registry                                # noqa: E402
from app.strategies.base import BarSeries                          # noqa: E402
from app.strategies.session_windows import et_epoch                # noqa: E402

NY = ZoneInfo("America/New_York")
LDN = ZoneInfo("Europe/London")
CAL = CalendarDaemon(crf.DEFAULT_HOLIDAYS)
MONTH = "2026-10"
PLAN = CAL.month_plan(MONTH)
FORM, ENTRY, EXIT = (date.fromisoformat(x) for x in (PLAN.formation, PLAN.entry, PLAN.exit))


class _patch:
    """Minimal attribute patch, restored on exit."""
    def __init__(self, obj, attr, value):
        self.obj, self.attr, self.value = obj, attr, value

    def __enter__(self):
        self.old = getattr(self.obj, self.attr)
        setattr(self.obj, self.attr, self.value)
        return self

    def __exit__(self, *exc):
        setattr(self.obj, self.attr, self.old)


async def _tv_refuses(*a, **k):
    raise tv_bars.TVBarsUnavailable("stubbed: TradingView unavailable in this test")


# ─── synthetic bars ──────────────────────────────────────────────────────────

def _sessions(start: date, end: date) -> list[date]:
    out, d = [], start
    while d <= end:
        if CAL.is_session(d):
            out.append(d)
        d += timedelta(days=1)
    return out


def spy_daily_candles(through: date, rally_bp: float = 90.0, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    days = _sessions(date(2026, 1, 2), through)
    px, out = 560.0, []
    for d in days:
        drift = rally_bp / 1e4 if (d.year, d.month) == (2026, 10) and d <= FORM else 0.0
        o = px
        px = px * math.exp(drift + rng.gauss(0.0, 0.008))
        hi, lo = max(o, px) * 1.003, min(o, px) * 0.997
        out.append({"time": et_epoch(d, dtime(9, 30)), "open": o, "high": hi, "low": lo,
                    "close": px, "volume": 7.5e7})
    return out


def to_series(symbol, interval, candles, volume_kind="traded", source="test", asset_class="stocks"):
    return strategy_agent.bar_series_from_candles(
        symbol, interval, {"candles": candles, "volume_kind": volume_kind, "source": source},
        asset_class)


# ─── 1. SPY month-end -> consensus ───────────────────────────────────────────

def test_spy_month_end_fires_into_consensus():
    from app.pipeline import graph
    from app.agents.trader import TraderAgent

    candles = spy_daily_candles(ENTRY)
    now = et_epoch(ENTRY, dtime(12, 0))
    state = {
        "ticker": "SPY", "asset_class": "stocks", "timeframe": "1D",
        "strategy_profile": "balanced", "reasoning_chain": [],
        "market_data": {"close": candles[-1]["close"], "atr": candles[-1]["close"] * 0.011,
                        "data_source": "tradingview",
                        "bars_by_interval": {"1d": {"candles": candles, "volume_kind": "traded",
                                                    "source": "test:AMEX:SPY"}}},
    }
    with _patch(crf, "CLOCK", lambda: now), _patch(tv_bars, "fetch_bars", _tv_refuses):
        state = asyncio.run(graph.run_quantitative_strategies(state))

    block = state["quantitative_strategies"]
    rebal = [c for c in block["contributions"] if c["registration"] == "cme_rebal_flow"]
    assert rebal, f"cme_rebal_flow did not evaluate: {block['abstentions']}"
    r = rebal[0]
    assert r["counted"] is True and r["direction"] == "SHORT", r
    assert r["evidence"]["phase"] == "IN_WINDOW"
    assert r["evidence"]["z"] > 0 and r["conviction"] == min(abs(r["evidence"]["z"]), 2) / 2
    assert r["stop"] is None and r["target"] is None, "registered rule has no levels"
    assert r["time_exit_utc"] == et_epoch(EXIT, dtime(16, 0))
    assert ("SHORT", r["vote_confidence"]) in block["votes"]
    assert abs(r["vote_confidence"] - r["conviction"] * 0.7) < 1e-9

    atr = state["market_data"]["atr"]
    state.update({
        "technical_analysis": {"direction": "SHORT", "confidence": 62, "atr": atr},
        "order_flow_analysis": {"direction": "SHORT", "confidence": 58},
        "fundamental_analysis": {"abstained": True}, "sentiment_analysis": {"abstained": True},
        "macro_analysis": {"abstained": True}, "regime_change_analysis": {"abstained": True},
        "correlation_analysis": {"abstained": True}, "quant_validation": {},
    })
    final = asyncio.run(TraderAgent().analyze(state))

    assert final["direction"] == "SHORT", final.get("status_reasons")
    assert "CME Rebalance Flow (Mandated)" in final["strategy_sources"], final["strategy_sources"]
    assert final["analytical_window"] == "4-SESSION"
    assert final["strategy_time_exit_utc"] == et_epoch(EXIT, dtime(16, 0))
    assert final["research_target"] < final["entry_price"] < final["invalidation_level"]
    assert 0 < final["confidence_score"] <= 100
    assert any("CME Rebalance Flow" in line and "z +" in line for line in final["reasoning_chain"])
    payload = json.loads(json.dumps(final))
    for k in ("direction", "entry_price", "research_target", "invalidation_level",
              "confidence_score", "strategy_sources"):
        assert payload.get(k) is not None, k


# ─── 2. causality ────────────────────────────────────────────────────────────

def test_cme_rebal_flow_is_causal():
    strat = registry.build("cme_rebal_flow")
    now = et_epoch(EXIT, dtime(11, 0))
    with _patch(crf, "CLOCK", lambda: now):
        full = spy_daily_candles(EXIT)
        base = strat.generate_signals(to_series("SPY", "1d", full))
        bumped = [dict(c) for c in full]
        for c in bumped:
            if datetime.fromtimestamp(c["time"], tz=NY).date() > FORM:
                c["close"] *= 1.03
                c["high"] *= 1.03
        pert = strat.generate_signals(to_series("SPY", "1d", bumped))
        trunc = strat.generate_signals(to_series(
            "SPY", "1d", [c for c in full if datetime.fromtimestamp(c["time"], tz=NY).date() <= FORM]))
    assert not base.abstained, base.reason
    assert base.evidence["z"] == pert.evidence["z"] == trunc.evidence["z"]


# ─── 3. EURUSD H4 meanrev ────────────────────────────────────────────────────

def test_eurusd_h4_meanrev_fires_as_observer():
    rng = random.Random(11)
    t0 = int(datetime(2026, 3, 2, tzinfo=timezone.utc).timestamp())
    px, candles = 1.0800, []
    for i in range(420):
        drift = 0.0016 if i >= 360 else 0.0
        o = px
        px = px * math.exp(drift + rng.gauss(0.0, 0.0012))
        candles.append({"time": t0 + i * 14400, "open": o, "high": max(o, px) * 1.0006,
                        "low": min(o, px) * 0.9994, "close": px, "volume": 0.0})
    bars = to_series("EURUSD", "4h", candles, volume_kind="none", asset_class="fx")
    block = strategy_agent.evaluate_symbol_multi("EURUSD", {"4h": bars})

    mr = [o for o in block["observations"] if o["registration"] == "meanrev"]
    assert mr and not mr[0]["abstained"], mr
    assert mr[0]["direction"] == "SHORT" and abs(mr[0]["evidence"]["score"]) >= 2.0, mr[0]
    assert mr[0]["counted"] is False and mr[0]["consensus_weight"] == 0.0
    assert block["votes"] == [], "an observer must never reach the vote list"


# ─── 4. XAUUSD VWAP, London anchor ───────────────────────────────────────────

def _xau_session(volume_kind: str) -> BarSeries:
    rng = random.Random(3)
    day = date(2026, 10, 7)
    candles = []
    t = datetime.combine(day, dtime(8, 0), tzinfo=LDN)
    while t.time() < dtime(9, 55):
        c = 2400.0 + rng.uniform(-0.2, 0.2)
        candles.append({"time": int(t.timestamp()), "open": c, "high": c + 0.15,
                        "low": c - 0.15, "close": c, "volume": 1000.0})
        t += timedelta(minutes=5)
    candles.append({"time": int(t.timestamp()), "open": 2400.1, "high": 2406.5,
                    "low": 2400.0, "close": 2406.0, "volume": 50.0})          # pierce
    t += timedelta(minutes=5)
    candles.append({"time": int(t.timestamp()), "open": 2406.0, "high": 2405.0,
                    "low": 2400.2, "close": 2400.3, "volume": 50.0})          # reject
    return to_series("XAUUSD", "5m", candles, volume_kind=volume_kind,
                     source="tradingview:COMEX:GC1! shifted onto OANDA:XAUUSD", asset_class="fx")


def test_xauusd_vwap_outer_band_pierce_and_reject():
    block = strategy_agent.evaluate_symbol_multi("XAUUSD", {"5m": _xau_session("traded")})
    v = [o for o in block["observations"] if o["registration"] == "institutional_vwap_london"][0]
    assert not v["abstained"] and v["direction"] == "SHORT", v.get("reason")
    ev = v["evidence"]
    assert ev["anchor"] == "london" and ev["volume_kind"] == "traded"
    assert v["target"] == ev["vwap"] < v["entry"] <= ev["upper_2"] < v["stop"]
    assert v["counted"] is False and block["votes"] == []

    dead = strategy_agent.evaluate_symbol_multi("XAUUSD", {"5m": _xau_session("none")})
    d = [o for o in dead["observations"] if o["registration"] == "institutional_vwap_london"][0]
    assert d["abstained"] and "traded volume" in d["reason"], d


# ─── 5. ten_am_macro observer ────────────────────────────────────────────────

def test_ten_am_macro_is_recorded_and_never_votes():
    day = date(2026, 10, 7)
    rows = []

    def bar(hh, mm, o, h, l, c):
        rows.append({"time": et_epoch(day, dtime(hh, mm)), "open": o, "high": h,
                     "low": l, "close": c, "volume": 1.0e5})

    prev = date(2026, 10, 6)                     # prior session: ATR warm-up history
    for k in range(30):
        t = datetime.combine(prev, dtime(9, 30), tzinfo=NY) + timedelta(minutes=5 * k)
        rows.append({"time": int(t.timestamp()), "open": 500.0, "high": 500.2,
                     "low": 499.8, "close": 500.0, "volume": 1.0e5})
    for k in range(6):
        bar(9, 30 + 5 * k, 500.0, 500.2, 499.8, 500.0)
    bar(10, 0, 500.0, 500.3, 499.9, 500.2)       # anchor, p10 = 500.0
    bar(10, 5, 500.2, 500.5, 500.1, 500.4)       # sweep high
    bar(10, 10, 500.4, 500.45, 500.2, 500.3)
    bar(10, 15, 500.3, 500.35, 500.1, 500.2)
    bar(10, 20, 500.2, 500.25, 500.0, 500.1)
    bar(10, 25, 500.1, 500.1, 499.7, 499.8)       # close below p10 (1)
    bar(10, 30, 499.8, 499.85, 499.6, 499.7)      # close below p10 (2) -> armed short
    bar(10, 35, 499.7, 500.0, 499.65, 499.9)      # retest of p10 -> fires
    bars = to_series("SPY", "5m", rows)

    with _patch(tv_bars, "fetch_bars", _tv_refuses):
        block = strategy_agent.evaluate_symbol_multi("SPY", {"5m": bars})
    t = [o for o in block["observations"] if o["registration"] == "ten_am_macro"][0]
    assert t["direction"] == "SHORT" and t["entry"] == 500.0, t.get("reason")
    assert t["stop"] > 500.5 and t["target"] < 500.0
    assert all(c["registration"] != "ten_am_macro" for c in block["contributions"])


# ─── 6. no TradingView -> abstain, no substitute ─────────────────────────────

def test_missing_tradingview_bars_abstain_without_fallback():
    with _patch(tv_bars, "fetch_bars", _tv_refuses):
        block = asyncio.run(strategy_agent.evaluate_for_pipeline("SPY", "stocks", {}))
    assert block["votes"] == []
    names = {a["strategy"] for a in block["abstentions"]}
    assert {"cme_rebal_flow", "overnight_drift", "institutional_vwap"} <= names, names
    assert block["bar_failures"] and all("TVBarsUnavailable" in f["reason"] for f in block["bar_failures"])


# ─── 7. TradingView loader conversions ───────────────────────────────────────

def test_tradingview_loader_conversions():
    import pandas as pd

    fake_mod = types.ModuleType("tvDatafeed")
    fake_mod.Interval = types.SimpleNamespace(in_daily="D", in_5_minute="5")
    sys.modules["tvDatafeed"] = fake_mod

    # CME daily bar for session 2026-10-07 opens 18:00 ET on 2026-10-06.
    es_open = datetime(2026, 10, 6, 18, 0, tzinfo=NY)
    gc_times = [datetime(2026, 10, 7, 9, 0, tzinfo=LDN) + timedelta(minutes=5 * k) for k in range(3)]

    def naive_local(dt):          # exactly what tvDatafeed builds its index with
        return datetime.fromtimestamp(dt.timestamp())

    class FakeTV:
        def get_hist(self, symbol, exchange, interval, n_bars):
            if symbol == "ES1!":
                idx, px = [naive_local(es_open)], [5000.0]
            elif symbol == "GC1!":
                idx, px = [naive_local(x) for x in gc_times], [2410.0, 2411.0, 2412.0]
            else:                                                    # OANDA spot reference
                idx, px = [naive_local(gc_times[-1])], [2400.0]
            return pd.DataFrame({"open": px, "high": px, "low": px, "close": px,
                                 "volume": [10.0] * len(px)}, index=pd.Index(idx))

    try:
        from app.data import tv_client
        tv_client._reset_for_tests()
        with _patch(tv_client, "_new_client", lambda: FakeTV()):
            es = asyncio.run(tv_bars.fetch_bars("ES", "1d"))
            xau = asyncio.run(tv_bars.fetch_bars("XAUUSD", "5m", want_traded_volume=True))
    finally:
        sys.modules.pop("tvDatafeed", None)

    assert es["volume_kind"] == "traded" and es["source"] == "tradingview:CME_MINI:ES1!", es["source"]
    assert datetime.fromtimestamp(es["candles"][0]["time"], tz=NY) == datetime(2026, 10, 7, 9, 30, tzinfo=NY)
    assert [c["time"] for c in xau["candles"]] == [int(x.timestamp()) for x in gc_times]
    assert xau["volume_kind"] == "traded" and xau["candles"][-1]["close"] == 2400.0
    assert "yahoo" not in (es["source"] + xau["source"]).lower()


# ─── 8. zero broker code ─────────────────────────────────────────────────────

TOUCHED = [
    "app/strategies/cme_rebal_flow.py", "app/strategies/vwap_bands.py",
    "app/strategies/ten_am_macro.py", "app/strategies/meanrev.py",
    "app/strategies/overnight_drift.py", "app/strategies/evidence_snapshot.py",
    "app/strategies/registry.py", "app/agents/strategy_agent.py", "app/agents/trader.py",
    "app/agents/quant.py", "app/data/tv_bars.py", "app/pipeline/graph.py",
    "app/pipeline/state.py", "ief/calendar_daemon.py",
]
BROKER = re.compile(r"^\s*(import|from)\s+(MetaTrader5|mt5|tradovate|ib_insync|alpaca)\b"
                    r"|order_send|account_info\(|lot_size|margin_required", re.M | re.I)


def test_no_broker_code_in_signal_path():
    hits = []
    for rel in TOUCHED:
        src = open(os.path.join(BACKEND, rel), encoding="utf-8").read()
        hits += [f"{rel}: {m.group(0)}" for m in BROKER.finditer(src)]
    assert not hits, hits


def test_registry_deployments():
    live = {k for k, r in registry.REGISTRY.items() if r.deployment is registry.Deployment.LIVE}
    obs = {k for k, r in registry.REGISTRY.items() if r.deployment is registry.Deployment.OBSERVER}
    assert {"cme_rebal_flow", "overnight_drift", "institutional_vwap"} <= live
    assert {"ten_am_macro", "meanrev", "institutional_vwap_london", "cme_rebal_flow_nasdaq"} <= obs
    assert registry.REGISTRY["cme_rebal_flow"].consensus_weight == 0.7
    assert registry.REGISTRY["overnight_drift"].consensus_weight == 0.6
    assert registry.REGISTRY["institutional_vwap"].consensus_weight == 0.5
    assert registry.REGISTRY["ten_am_macro"].consensus_weight == 0.0
    assert registry.check_exclusions() == []


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except Exception as exc:
            failed += 1
            import traceback
            print(f"FAIL  {name}: {type(exc).__name__}: {exc}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
