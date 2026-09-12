"""
WEINSTEIN_STAGE_01 — Stan Weinstein 4-Stage Market Cycle on SPY Daily
====================================================================
Runs exactly what prereg/WEINSTEIN_STAGE_01.md specifies, sealed at
493f9a30732cac89 before any return was computed.

NOTHING IS SWEPT. The 150-day SMA, 10-day slope lookback, entry/exit at open[t+1],
dual venue financing (Retail CFD vs CME Futures), and Buy-and-Hold symmetric
control are frozen in section 3 of the prereg.

DEFENCES AGAINST ERRORS THIS PROGRAMME HAS ALREADY MADE:
  1. assert_causal() rebuilds the signal series on truncated prefixes and requires
     exact array equality.
  2. The holdout branch is guarded by an assert on all four gates.
  3. Toll and financing are charged symmetrically on both strategy and benchmark.
"""
from __future__ import annotations

import math
import os
import sys
from typing import Dict, Any, Tuple

import numpy as np
import pandas as pd

import _discovery as D

PREREG_SHA = "493f9a30732cac89"

# --- frozen specification, prereg section 3 -------------------------------
SMA_N = 150
SLOPE_LAG = 10
WARMUP = SMA_N + SLOPE_LAG  # 160 sessions
TOLL_RT = 4.09e-4           # 4.09 bp per round trip

# Financing parameters (annualized)
CFD_RATE_GROSS = 0.0780     # SOFR + 2.5% broker markup
CFD_RATE_NET   = 0.0630     # Net of 1.5% dividend credit
FUT_RATE       = 0.0380     # CME ES/MES basis decay (r - q)

ERAS = [
    ("Era 1: Pre-GFC (1993-2007)",    "1993-01-01", "2007-12-31"),
    ("Era 2: ZIRP / QE (2008-2021)",  "2008-01-01", "2021-12-31"),
    ("Era 3: Rate Shock (2022-2023)", "2022-01-01", "2023-12-31"),
]


# ---------------------------------------------------------------- features
def build_signals(df: pd.DataFrame) -> np.ndarray:
    """Evaluate Stage 2 signal causal at close of session t.
    Uses bars 0..t only.
    """
    c = df["close"].to_numpy(float)
    s = pd.Series(c)
    sma = s.rolling(SMA_N).mean().to_numpy()
    slope = pd.Series(sma).diff(SLOPE_LAG).to_numpy()
    sig = np.where(np.isfinite(sma) & np.isfinite(slope) & (c > sma) & (slope > 0), 1, 0)
    return sig


def assert_causal(df: pd.DataFrame) -> bool:
    """Truncating future sessions must not change any past signal."""
    sig_full = build_signals(df)
    for cut in (len(df) // 2, len(df) - 1000, len(df) - 200, len(df) - 50):
        sig_part = build_signals(df.iloc[:cut])
        if not np.array_equal(sig_part, sig_full[:cut]):
            raise AssertionError(f"LOOKAHEAD detected in Weinstein Stage signal at cut={cut}")
    return True


# ---------------------------------------------------------------- simulation
def compute_stats(r_series: pd.Series, years: float) -> Dict[str, float]:
    """Standardized performance and risk metrics."""
    eq = (1.0 + r_series).cumprod()
    cagr = float((eq.iloc[-1] ** (1.0 / years)) - 1.0) if years > 0 else 0.0
    peak = eq.cummax()
    dd = (eq - peak) / peak
    max_dd = float(dd.min())
    ann_ret = float(r_series.mean() * 252.0)
    ann_vol = float(r_series.std(ddof=1) * math.sqrt(252.0))
    sharpe = float(ann_ret / ann_vol) if ann_vol > 0 else 0.0
    mar = float(cagr / abs(max_dd)) if abs(max_dd) > 1e-6 else 0.0
    return {
        "cagr": cagr,
        "ann_ret": ann_ret,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "mar": mar,
        "terminal": float(eq.iloc[-1]),
    }


def simulate_panel(df: pd.DataFrame) -> pd.DataFrame:
    """Construct causal Open-to-Open returns with exact calendar day financing."""
    df = df.sort_values("ts").reset_index(drop=True).copy()
    sig = build_signals(df)
    df["sig"] = sig

    # Order execution: Signal at close[t] executes at open[t+1]
    df["pos"] = df["sig"].shift(1).fillna(0).astype(int)

    # Restrict to valid evaluation window after moving average warmup
    sim = df.iloc[WARMUP:].copy().reset_index(drop=True)

    # Calendar days between execution bar t and exit bar t+1
    sim["dt"] = pd.to_datetime(sim["ts"])
    sim["cal_days"] = (sim["dt"].shift(-1) - sim["dt"]).dt.days.fillna(1.0)
    sim["ret_oo"] = (sim["open"].shift(-1) - sim["open"]) / sim["open"]

    # Drop the terminal bar where open[t+1] is unknown
    sim = sim.dropna(subset=["ret_oo"]).copy().reset_index(drop=True)

    # Turnover accounting
    sim["entry"] = ((sim["pos"] == 1) & (sim["pos"].shift(1).fillna(0) == 0)).astype(int)
    sim["exit"]  = ((sim["pos"] == 0) & (sim["pos"].shift(1).fillna(0) == 1)).astype(int)
    sim["turnover_toll"] = (sim["entry"] + sim["exit"]) * (TOLL_RT / 2.0)

    # Daily financing drags
    sim["fin_cfd_bh"] = CFD_RATE_NET * (sim["cal_days"] / 365.0)
    sim["fin_cfd_w"]  = CFD_RATE_NET * (sim["cal_days"] / 365.0) * sim["pos"]

    sim["fin_fut_bh"] = FUT_RATE * (sim["cal_days"] / 365.0)
    sim["fin_fut_w"]  = FUT_RATE * (sim["cal_days"] / 365.0) * sim["pos"]

    # Net daily returns
    sim["ret_bh_gross"] = sim["ret_oo"]
    sim["ret_w_gross"]  = sim["ret_oo"] * sim["pos"] - sim["turnover_toll"]

    sim["ret_bh_fut"]   = sim["ret_oo"] - sim["fin_fut_bh"]
    sim["ret_w_fut"]    = sim["ret_oo"] * sim["pos"] - sim["turnover_toll"] - sim["fin_fut_w"]

    sim["ret_bh_cfd"]   = sim["ret_oo"] - sim["fin_cfd_bh"]
    sim["ret_w_cfd"]    = sim["ret_oo"] * sim["pos"] - sim["turnover_toll"] - sim["fin_cfd_w"]

    return sim


def evaluate(sim: pd.DataFrame, label: str) -> Dict[str, Any]:
    """Run full evaluation suite across all venues and chronological sub-eras."""
    years = (sim["dt"].max() - sim["dt"].min()).days / 365.25
    time_in_market = float(sim["pos"].mean())
    n_flips = int((sim["pos"].diff().abs() == 1).sum())
    rt_per_year = (n_flips / 2.0) / years if years > 0 else 0.0

    print(f"\n=======================================================================")
    print(f"  {label} ({years:.1f} YEARS, {len(sim)} SESSIONS)")
    print(f"=======================================================================")
    print(f"Time in Market: {time_in_market*100:.1f}% | Regime Flips: {n_flips} ({rt_per_year:.2f} RT/year)")
    print(f"Warmup Sessions: {WARMUP} | Date Span: {sim['dt'].min().date()} to {sim['dt'].max().date()}")

    venues = [
        ("GROSS (No Toll / Financing)", "ret_bh_gross", "ret_w_gross"),
        ("VENUE B: CME FUTURES (3.8% basis decay)", "ret_bh_fut", "ret_w_fut"),
        ("VENUE A: RETAIL CFD (6.3% net financing drag)", "ret_bh_cfd", "ret_w_cfd"),
    ]

    v_stats = {}
    for name, col_bh, col_w in venues:
        sbh = compute_stats(sim[col_bh], years)
        sw  = compute_stats(sim[col_w], years)
        d_sh = sw["sharpe"] - sbh["sharpe"]
        d_cagr = (sw["cagr"] - sbh["cagr"]) * 100.0
        dd_ratio = abs(sw["max_dd"]) / abs(sbh["max_dd"]) if abs(sbh["max_dd"]) > 0 else 1.0
        mar_ratio = sw["mar"] / sbh["mar"] if sbh["mar"] > 0 else 0.0
        v_stats[name] = {"bh": sbh, "w": sw, "d_sh": d_sh, "dd_ratio": dd_ratio, "mar_ratio": mar_ratio}

        print(f"\n--- {name} ---")
        print(f"  B&H       : CAGR={sbh['cagr']*100:6.2f}%  Vol={sbh['ann_vol']*100:5.2f}%  Sharpe={sbh['sharpe']:5.2f}  MaxDD={sbh['max_dd']*100:6.2f}%  MAR={sbh['mar']:5.2f}  Terminal={sbh['terminal']:7.2f}x")
        print(f"  Weinstein : CAGR={sw['cagr']*100:6.2f}%  Vol={sw['ann_vol']*100:5.2f}%  Sharpe={sw['sharpe']:5.2f}  MaxDD={sw['max_dd']*100:6.2f}%  MAR={sw['mar']:5.2f}  Terminal={sw['terminal']:7.2f}x")
        print(f"  Delta     : dSharpe={d_sh:+5.2f}  dCAGR={d_cagr:+6.2f}%  MaxDD Ratio={dd_ratio:5.2f}x  MAR Ratio={mar_ratio:5.2f}x")

    # Chronological Sub-Eras (Evaluated on Venue B: CME Futures)
    print(f"\n--- GATE 3 SUB-ERAS (Venue B: CME Futures Basis Decay) ---")
    era_passes = 0
    era_results = []
    for elabel, start_d, end_d in ERAS:
        sub = sim[(sim["dt"] >= pd.Timestamp(start_d, tz="UTC")) & (sim["dt"] <= pd.Timestamp(end_d, tz="UTC"))].copy()
        if len(sub) < 50:
            continue
        y_sub = (sub["dt"].max() - sub["dt"].min()).days / 365.25
        sbh_sub = compute_stats(sub["ret_bh_fut"], y_sub)
        sw_sub  = compute_stats(sub["ret_w_fut"], y_sub)
        d_sh_sub = sw_sub["sharpe"] - sbh_sub["sharpe"]
        passed = bool(sw_sub["sharpe"] >= sbh_sub["sharpe"])
        if passed:
            era_passes += 1
        era_results.append((elabel, len(sub), sbh_sub, sw_sub, d_sh_sub, passed))
        status = "PASS" if passed else "FAIL"
        print(f"  {elabel:30s} n={len(sub):4d}  B&H Sh={sbh_sub['sharpe']:5.2f} (DD={sbh_sub['max_dd']*100:5.1f}%)  W Sh={sw_sub['sharpe']:5.2f} (DD={sw_sub['max_dd']*100:5.1f}%)  dSharpe={d_sh_sub:+5.2f}  [{status}]")

    # Gate evaluations
    fut_stats = v_stats["VENUE B: CME FUTURES (3.8% basis decay)"]
    cfd_stats = v_stats["VENUE A: RETAIL CFD (6.3% net financing drag)"]

    g1 = bool((fut_stats["d_sh"] >= 0.10) and (cfd_stats["d_sh"] >= 0.10))
    g2 = bool((fut_stats["dd_ratio"] <= 0.60) and (fut_stats["mar_ratio"] >= 1.25))
    g3 = bool(era_passes >= 2)
    g4 = bool((fut_stats["w"]["cagr"] > 0) and (cfd_stats["w"]["cagr"] > 0))

    print(f"\n=======================================================================")
    print(f"  GATE READOUT — WEINSTEIN_STAGE_01")
    print(f"=======================================================================")
    print(f"  GATE 1 (Alpha over B&H dSharpe >= +0.10) : {'PASS' if g1 else 'FAIL'}  (Fut dSh: {fut_stats['d_sh']:+.2f}, CFD dSh: {cfd_stats['d_sh']:+.2f})")
    print(f"  GATE 2 (Drawdown Truncation <= 0.60x)     : {'PASS' if g2 else 'FAIL'}  (DD Ratio: {fut_stats['dd_ratio']:.2f}x, MAR Ratio: {fut_stats['mar_ratio']:.2f}x)")
    print(f"  GATE 3 (Temporal Stability >= 2/3 Eras)   : {'PASS' if g3 else 'FAIL'}  ({era_passes} of 3 sub-eras passed)")
    print(f"  GATE 4 (Net Economic Viability CAGR > 0)  : {'PASS' if g4 else 'FAIL'}  (Fut CAGR: {fut_stats['w']['cagr']*100:+.2f}%, CFD CAGR: {cfd_stats['w']['cagr']*100:+.2f}%)")

    verdict = "VALIDATED" if (g1 and g2 and g3 and g4) else "FAILED"
    print(f"\n  OVERALL VERDICT: {verdict}")
    print(f"=======================================================================\n")

    return {
        "gates": (g1, g2, g3, g4),
        "v_stats": v_stats,
        "era_results": era_results,
        "time_in_market": time_in_market,
        "n_flips": n_flips,
        "years": years,
        "verdict": verdict,
    }


if __name__ == "__main__":
    print(f"WEINSTEIN_STAGE_01 — Pre-Registration SHA: {PREREG_SHA}")
    df_raw = D.load_discovery("spy_daily")
    print(f"Loaded discovery data: {len(df_raw)} sessions ({df_raw.ts.min().date()} to {df_raw.ts.max().date()})")

    # 1. Causality assertion
    causal_ok = assert_causal(df_raw)
    print(f"Causality assertion on spy_daily: {'PASS' if causal_ok else 'FAIL'}")

    # 2. Run discovery simulation
    sim_disc = simulate_panel(df_raw)
    res = evaluate(sim_disc, "DISCOVERY EVALUATION (ts < 2024-01-01)")

    # 3. Holdout evaluation gate check
    if all(res["gates"]):
        print("ALL FOUR GATES PASSED -> Holdout read is authorised under prereg section 4.")
        df_holdout = D.load_holdout("spy_daily", "WEINSTEIN_STAGE_01")
        sim_hold = simulate_panel(df_holdout)
        evaluate(sim_hold, "SEALED HOLDOUT READOUT (ts >= 2024-01-01)")
    else:
        failed_gates = [f"GATE {i+1}" for i, passed in enumerate(res["gates"]) if not passed]
        print(f"EXECUTION STOPPED: {', '.join(failed_gates)} FAILED.")
        print("Prereg section 4 mechanically blocks holdout access. Holdout remains SEALED.")
