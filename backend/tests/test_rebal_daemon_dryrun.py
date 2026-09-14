"""
End-to-end dry run — IEF month-end rebalance daemon
===================================================
Exercises the full chain on the next scheduled month-end window:
    calendar plan -> formation signal -> vol estimate -> sizing -> order dispatch
                  -> exit -> execution audit

Run:  python -m pytest tests/test_rebal_daemon_dryrun.py -v
      python tests/test_rebal_daemon_dryrun.py          (prints a full dry-run)

NOTHING HERE TOUCHES THE HOLDOUT. Prices come from discovery data only, and the
dry run is a wiring and arithmetic test, not an evaluation.
"""
from __future__ import annotations

import datetime as dt
import math
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ief.calendar_daemon import CalendarDaemon, HolidayHorizonError, FORMATION, ENTRY, EXIT
from ief import sizing as SZ
from ief.adapters.paper import PaperAdapter, MARKET_ON_OPEN, TIME_SLICED

SCHEDULE = "ief/data/exchange_holidays.csv"
SERIES = ["es_daily", "ym_daily", "rty_daily"]
Z_CAP = 2.0
VOL_TARGET = 0.10
LOG = "logs/ief_rebal_execution.log"


# ---------------------------------------------------------------------------
# data helpers (discovery only)
# ---------------------------------------------------------------------------
def load_closes(series: str) -> pd.Series:
    d = pd.read_parquet(f"app/data/{series}.parquet")
    d["ts"] = pd.to_datetime(d["ts"], utc=True)
    d = d[d["ts"] < pd.Timestamp("2024-01-01", tz="UTC")].sort_values("ts")
    return pd.Series(d["close"].values,
                     index=d["ts"].dt.strftime("%Y-%m-%d").values)


def formation_signal(closes: pd.Series, prior_close_date: str,
                     formation_date: str, sessions_elapsed: int) -> tuple:
    """z = intra-month return / (daily sd * sqrt(L)). Causal at the formation close."""
    # Exclude formation session to match research harness rolling(60).std().shift(1)
    hist = closes[closes.index < formation_date]
    sigma_d = SZ.trailing_vol_annualised(list(hist.values), 60) / math.sqrt(252.0)
    S = math.log(closes[formation_date] / closes[prior_close_date])
    z = S / (sigma_d * math.sqrt(sessions_elapsed))
    return S, sigma_d, z


def target_weights(zs: dict[str, float], sigmas_d: dict[str, float]) -> dict[str, float]:
    """The pre-registered weight formula. Position is OPPOSITE the intra-month move."""
    n = len(zs)
    w = {}
    for s, z in zs.items():
        ann = sigmas_d[s] * math.sqrt(252.0)
        w[s] = -max(-Z_CAP, min(Z_CAP, z)) / Z_CAP * (1.0 / n) * (VOL_TARGET / ann)
    gross = sum(abs(v) for v in w.values())
    if gross > 3.0:
        w = {k: v * 3.0 / gross for k, v in w.items()}
    return w


def quote_from_close(px: float, tick: float) -> dict:
    return {"bid": px - tick / 2, "ask": px + tick / 2}


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------
def test_schedule_covers_2030():
    d = CalendarDaemon(SCHEDULE)
    assert d.coverage_end >= dt.date(2030, 12, 1), d.coverage_end
    assert d.month_plan("2030-06") is not None


def test_horizon_assertion_fires_beyond_coverage():
    d = CalendarDaemon(SCHEDULE)
    try:
        d.month_plan("2031-06")
        assert False, "expected HolidayHorizonError beyond schedule coverage"
    except HolidayHorizonError:
        pass


def test_ad_hoc_closures_present_and_shift_sandy_grid():
    """Sandy is the one historical closure that moves a month grid."""
    d = CalendarDaemon(SCHEDULE)
    assert dt.date(2012, 10, 29) in d.ad_hoc_closures
    assert dt.date(2012, 10, 30) in d.ad_hoc_closures
    assert not d.is_session(dt.date(2012, 10, 29))
    p = d.month_plan("2012-10")
    # with Sandy removed the true 5th-to-last session is 2012-10-23, not 10-25
    assert p.formation == "2012-10-23", p
    assert p.entry == "2012-10-24", p
    assert p.exit == "2012-10-31", p


def test_grid_matches_backtest_except_adhoc_months():
    """The daemon must reproduce the evaluated grid wherever no ad-hoc closure
    intervened. Months containing one are EXPECTED to differ, and that difference
    is the defect being fixed."""
    import _cme_rebal_flow as B
    cal = B.build_calendar(start="1993-01-01", end="2023-12-31")
    refs = B.month_reference_dates(cal, 5, 4, None)
    d = CalendarDaemon(SCHEDULE)
    plans = {p.month: p for p in d.plans_between("1993-02", "2023-12")}
    adhoc_months = {c.isoformat()[:7] for c in d.ad_hoc_closures}
    diffs = []
    for _, r in refs.iterrows():
        p = plans.get(r["mo"])
        if p is None:
            continue
        if (p.formation, p.entry, p.exit) != (r["form"], r["entry"], r["exit"]):
            diffs.append(r["mo"])
    unexpected = [m for m in diffs if m not in adhoc_months]
    assert not unexpected, f"grid disagrees outside ad-hoc months: {unexpected}"
    assert "2012-10" in diffs


def test_toll_band_governor_binds_at_directive_threshold():
    """At the $190k tier boundary a 4.0x cap pushes every leg out of the 1-5 band,
    so the governor must reduce the multiple."""
    prices = {"es_daily": 4366.20, "ym_daily": 34807.85, "rty_daily": 1873.86}
    w = {"es_daily": 0.1471, "ym_daily": 0.1536, "rty_daily": 0.0721}
    k, binding = SZ.effective_multiple(w, prices, 190_000.0, leverage_cap=4.0)
    assert binding, "governor should bind at $190k under a 4.0x cap"
    assert 2.9 < k < 3.1, k
    plan = SZ.build_plan(w, prices, 190_000.0)
    assert plan.mode == SZ.PANEL
    assert plan.all_in_band, [o.contracts for o in plan.orders]
    assert any("GOVERNOR" in x for x in plan.warnings)


def test_single_instrument_mode_below_threshold():
    prices = {"es_daily": 4366.20, "ym_daily": 34807.85, "rty_daily": 1873.86}
    w = {"es_daily": 0.1471, "ym_daily": 0.1536, "rty_daily": 0.0721}
    plan = SZ.build_plan(w, prices, 120_000.0)
    assert plan.mode == SZ.SINGLE
    assert [o.symbol for o in plan.orders] == ["MES"]
    assert any("SINGLE_MES" in x for x in plan.warnings)


def test_vol_estimator_is_the_preregistered_one():
    closes = load_closes("es_daily")
    v = SZ.trailing_vol_annualised(list(closes.values), 60)
    assert 0.03 < v < 1.5, v
    # must consume exactly 61 closes, i.e. 60 returns ending at the last bar
    short = list(closes.values)[-61:]
    assert abs(SZ.trailing_vol_annualised(short, 60) - v) < 1e-12


def test_zero_holdout_reads():
    n = sum(1 for _ in open("prereg/HOLDOUT_ACCESS.log", encoding="utf-8"))
    assert n == 2, f"HOLDOUT_ACCESS.log grew to {n} lines"


# ---------------------------------------------------------------------------
# full dry run
# ---------------------------------------------------------------------------
def dry_run(equity: float = 190_000.0, month: str | None = None) -> dict:
    d = CalendarDaemon(SCHEDULE, state_path="ief/_dryrun_state.json")
    closes = {s: load_closes(s) for s in SERIES}
    common = sorted(set.intersection(*[set(c.index) for c in closes.values()]))

    if month is None:
        month = common[-1][:7]
    plan = d.month_plan(month)
    if plan is None:
        raise RuntimeError(f"{month} not tradable")

    print("=" * 78)
    print(f"  IEF DRY RUN — month {plan.month}  equity ${equity:,.0f}")
    print("=" * 78)
    print(f"\n[calendar] K={plan.K} published sessions")
    print(f"[calendar] prior_close {plan.prior_close}  formation {plan.formation}")
    print(f"[calendar] entry (OPEN) {plan.entry}  exit (15:59:30 slice) {plan.exit}")
    print(f"[calendar] early close on exit session: {d.is_early_close(dt.date.fromisoformat(plan.exit))}")
    for step, date in ((FORMATION, plan.formation), (ENTRY, plan.entry), (EXIT, plan.exit)):
        print(f"[calendar] action_for({date}) = {d.action_for(date)}  "
              f"confirm_open={d.confirm_open(date)}")

    sess = [x for x in common if plan.prior_close < x <= plan.formation]
    L = len(sess)
    print(f"\n[formation] {L} sessions from {plan.prior_close} to {plan.formation}")
    zs, sig = {}, {}
    for s in SERIES:
        if plan.formation not in closes[s].index or plan.prior_close not in closes[s].index:
            print(f"[formation] {s}: missing a reference date, leg dropped")
            continue
        S, sd, z = formation_signal(closes[s], plan.prior_close, plan.formation, L)
        zs[s], sig[s] = z, sd
        print(f"[formation] {s:10s} S={S:+.5f}  sigma_d={sd:.5f} "
              f"(ann {sd*math.sqrt(252):.3f})  z={z:+.3f}  -> side {'SHORT' if z>0 else 'LONG'}")

    w = target_weights(zs, sig)
    print(f"\n[weights] pre-registered targets: " +
          "  ".join(f"{k.split('_')[0]}={v:+.4f}" for k, v in w.items()))

    prices = {s: float(closes[s][plan.formation]) for s in zs}
    sp = SZ.build_plan(w, prices, equity)
    print(f"\n[sizing] mode {sp.mode}  cap {sp.leverage_cap:.2f}x  "
          f"effective {sp.k_effective:.2f}x  governor {'BINDING' if sp.governor_binding else 'idle'}")
    for o in sp.orders:
        print(f"[sizing]   {o.symbol} {'LONG ' if o.side>0 else 'SHORT'} {o.contracts} @ "
              f"{o.price:,.2f}  target ${o.target_notional:,.0f} actual ${o.actual_notional:,.0f} "
              f"(quant err {o.quantisation_error:+.1%}) band_ok={o.in_toll_band}")
    print(f"[sizing] gross notional ${sp.gross_notional:,.0f} = {sp.gross_leverage:.2f}x equity")
    for wn in sp.warnings:
        print(f"[WARN] {wn}")

    adapter = PaperAdapter(
        tick_size={"MES": 0.25, "MYM": 1.00, "M2K": 0.10}, log_path=LOG)
    print(f"\n[dispatch] ENTRY at the OPEN of {plan.entry} (Market-on-Open)")
    for o in sp.orders:
        q = quote_from_close(o.price, adapter.tick_size[o.symbol])
        f = adapter.submit(o.symbol, o.contracts, o.side, MARKET_ON_OPEN, q,
                           note=f"{plan.month}:ENTRY")
        print(f"[dispatch]   {f.symbol} fill {f.fill_price:,.4f} vs mid {f.intended_price:,.4f}"
              f"  slip {f.slippage_bp:.3f} bp  M_realised {f.m_realised:.4f}")
    print(f"[dispatch] positions after entry: {adapter.positions()}")

    exit_px = {s: float(closes[s][plan.exit]) for s in zs if plan.exit in closes[s].index}
    print(f"\n[dispatch] EXIT on {plan.exit} via 30-second time slice from 15:59:30 ET")
    for o in sp.orders:
        if o.series not in exit_px:
            print(f"[dispatch]   {o.symbol}: NO EXIT PRICE - kill switch would fire")
            continue
        q = quote_from_close(exit_px[o.series], adapter.tick_size[o.symbol])
        f = adapter.submit(o.symbol, o.contracts, -o.side, TIME_SLICED, q,
                           note=f"{plan.month}:EXIT")
        print(f"[dispatch]   {f.symbol} fill {f.fill_price:,.4f}  slip {f.slippage_bp:.3f} bp "
              f" M_realised {f.m_realised:.4f}")
    print(f"[dispatch] positions after exit: {adapter.positions()} (must be empty)")
    assert not adapter.positions(), "dry run did not flatten"

    gross = 0.0
    for o in sp.orders:
        if o.series not in exit_px:
            continue
        r = math.log(exit_px[o.series] / o.price) * o.side
        gross += r * abs(o.actual_notional) / equity
    a = adapter.audit()
    toll = sum(abs(o.actual_notional) / equity * SZ.CONTRACTS[o.series].toll_bp / 1e4
               for o in sp.orders)
    print(f"\n[pnl] gross {gross*1e4:+.2f} bp of equity   modelled toll {toll*1e4:.2f} bp")
    print(f"[audit] fills {a['fills']}  mean M_realised {a['m_realised_mean']:.4f} "
          f"vs Phase 4 measured {a['m_measured']}  excess {a['m_excess']:+.4f}")
    print(f"[audit] mean slippage {a['slippage_bp_mean']:.3f} bp  log -> {LOG}")

    d.mark_done(plan.month, EXIT, {"equity": equity, "mode": sp.mode})
    print(f"[state] marked {plan.month}:EXIT done; pending now {d.pending(plan.exit)}")
    print("=" * 78)
    return {"plan": plan, "sizing": sp, "audit": a, "gross_bp": gross * 1e4}


def test_dry_run_end_to_end():
    r = dry_run(190_000.0)
    assert r["sizing"].orders
    assert r["audit"]["fills"] == 2 * len(r["sizing"].orders)
    assert r["sizing"].all_in_band


if __name__ == "__main__":
    for eq in (120_000.0, 190_000.0):
        dry_run(eq)
        print()
    for f in ("ief/_dryrun_state.json",):
        if os.path.exists(f):
            os.remove(f)
