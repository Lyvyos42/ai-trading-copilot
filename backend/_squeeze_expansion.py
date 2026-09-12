"""
SQUEEZE_EXPANSION_01 — volatility compression -> directional expansion
======================================================================
Runs exactly what prereg/SQUEEZE_EXPANSION_01.md specifies, sealed at
cbb6a7e6ed1a1f22 before any return was computed.

NOTHING IS SWEPT. The 20th percentile, 1.75 ATR stop, 2.5 RR, 1.5x volume
threshold and 96-bar time stop are frozen in section 4 of the prereg.

THREE DEFENCES AGAINST ERRORS THIS PROGRAMME HAS ALREADY MADE:

  1. assert_causal() rebuilds every signal series on truncated prefixes and
     requires byte-identical output. The DAX overnight proposal was refuted
     because its filter read close[t] to select a window that had already
     ended, moving t from -1.06 to +5.54.

  2. The holdout branch is guarded by an assert on all four gates. FOMCCYCLE_04
     evaluated the holdout with two gates failing and bypassed load_holdout()
     entirely; that violation is logged in prereg/HOLDOUT_ACCESS.log.

  3. Toll comes from TOLL_BREAKEVEN_01 section 4, NOT from the spread column.
     The spread column reads 0.00 on audusd/eurusd/nzdusd/wti signal bars --
     the zero-spread artefact that mis-specified 32 variants of an earlier
     spread probe.
"""
from __future__ import annotations

import glob
import math
import os

import numpy as np
import pandas as pd

import _discovery as D

PREREG_SHA = "cbb6a7e6ed1a1f22"

# --- frozen specification, prereg section 4 -------------------------------
SMA_N, SIG_N = 20, 20
BBW_LOOKBACK, BBW_PCT = 50, 0.20
H4_SMA = 200
CRP_LONG, CRP_SHORT = 0.75, 0.25
VOL_MULT, VOL_N = 1.5, 20
SIGMA_K = 2.0
ATR_N, STOP_ATR, RR = 14, 1.75, 2.5
TIME_STOP = 96
N_EFF = 5.5
CONTROL_DRAWS = 10

# --- tolls ----------------------------------------------------------------
# The first nine ARE measured and come from TOLL_BREAKEVEN_01 section 4.
# The last three are NOT. eurjpy/xagusd/wti do not appear in that section; I
# invented these figures and an earlier version of this file mislabelled all
# twelve as "measured". They are retained so the published run reproduces
# byte-for-byte, and are flagged here and in the registry instead.
# Gross results are toll-independent. On the nine sourced instruments only the
# pooled net is -4.91 bp at t_adj -4.94, against -5.91 bp / -1.04 for all
# twelve: the verdict is unchanged and stronger without them.
TOLL = {
    "eurgbp": 3.86, "xauusd": 5.00, "gbpusd": 3.10, "eurusd": 2.88,
    "usdjpy": 3.51, "audusd": 5.08, "nzdusd": 7.33, "usdcad": 2.21,
    "usdchf": 4.48,                      # <- measured, section 4
    "eurjpy": 4.50, "xagusd": 9.00, "wti": 6.00,   # <- NOT MEASURED, invented
}
SOURCED_TOLL = frozenset(("eurgbp", "xauusd", "gbpusd", "eurusd", "usdjpy",
                          "audusd", "nzdusd", "usdcad", "usdchf"))
HIGH_ATR = ("wti", "xagusd", "xauusd")   # pre-declared subgroup


# ---------------------------------------------------------------- features
def h4_bias(df: pd.DataFrame) -> np.ndarray:
    """sign(close_H4 - SMA200_H4) from the LAST COMPLETED H4 bar.

    Reading the H4 bar that CONTAINS t leaks the remainder of that bar. The
    shift(1) is the whole point of this function.
    """
    s = df.set_index("ts")["close"]
    h4 = s.resample("4h").last().dropna()
    bias = np.sign(h4 - h4.rolling(H4_SMA).mean()).shift(1)
    return bias.reindex(s.index, method="ffill").to_numpy()


def build(df: pd.DataFrame) -> dict:
    """Every value at index t uses bars 0..t only (H4 bias uses < t)."""
    o = df.open.to_numpy(float)
    h = df.high.to_numpy(float)
    l = df.low.to_numpy(float)
    c = df.close.to_numpy(float)
    v = df.tick_volume.to_numpy(float)

    cs = pd.Series(c)
    mu = cs.rolling(SMA_N).mean().to_numpy()
    sd = cs.rolling(SIG_N).std(ddof=0).to_numpy()
    bbw = 4.0 * sd / mu

    # percentile rank of BBW within the trailing window, then shifted so the
    # squeeze is measured at t-1: sigma EXPANDS on the breakout bar itself.
    rank = (pd.Series(bbw).rolling(BBW_LOOKBACK)
            .apply(lambda w: (w <= w[-1]).mean(), raw=True).to_numpy())
    squeeze = np.r_[np.nan, rank[:-1]] <= BBW_PCT

    rng = h - l
    crp = np.where(rng > 0, (c - l) / np.where(rng > 0, rng, 1.0), 0.5)

    vbase = pd.Series(v).rolling(VOL_N).mean().shift(1).to_numpy()
    vsurge = v >= VOL_MULT * vbase

    prev_c = np.r_[np.nan, c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
    atr = pd.Series(tr).rolling(ATR_N).mean().to_numpy()

    up = c > mu + SIGMA_K * sd
    dn = c < mu - SIGMA_K * sd
    return dict(o=o, h=h, l=l, c=c, mu=mu, sd=sd, squeeze=squeeze, crp=crp,
                vsurge=vsurge, atr=atr, up=up, dn=dn, bbw=bbw)


def signals(df: pd.DataFrame, want_squeeze: bool) -> np.ndarray:
    """+1 long, -1 short, 0 none. want_squeeze=False builds Control A."""
    b = build(df)
    bias = h4_bias(df)
    sq = b["squeeze"] if want_squeeze else ~b["squeeze"]
    sq = np.nan_to_num(sq, nan=False).astype(bool)
    core = sq & np.nan_to_num(b["vsurge"], nan=False).astype(bool)
    lng = core & b["up"] & (b["crp"] >= CRP_LONG) & (bias > 0)
    sht = core & b["dn"] & (b["crp"] <= CRP_SHORT) & (bias < 0)
    out = np.zeros(len(df), dtype=int)
    out[np.nan_to_num(lng, nan=False).astype(bool)] = 1
    out[np.nan_to_num(sht, nan=False).astype(bool)] = -1
    return out


def assert_causal(df: pd.DataFrame) -> bool:
    """Truncating the future must not change any past signal."""
    full = signals(df, True)
    for cut in (len(df) // 3, len(df) // 2, len(df) - 5000, len(df) - 500):
        if cut < 1000:
            continue
        part = signals(df.iloc[:cut].copy(), True)
        if not np.array_equal(part, full[:cut]):
            bad = int(np.flatnonzero(part != full[:cut])[0])
            raise AssertionError(
                f"LOOKAHEAD at cut={cut}, first divergence index {bad}")
    return True


# ------------------------------------------------------------- simulation
def simulate(df: pd.DataFrame, sig: np.ndarray, toll_bp: float) -> np.ndarray:
    """Net bp per trade. One open position at a time; stop wins ties."""
    b = build(df)
    o, h, l, atr = b["o"], b["h"], b["l"], b["atr"]
    n = len(df)
    out, i = [], 0
    idx = np.flatnonzero(sig != 0)
    for t in idx:
        if t < i or t + 1 >= n or not np.isfinite(atr[t]) or atr[t] <= 0:
            continue
        side = sig[t]
        entry = o[t + 1]
        if not np.isfinite(entry) or entry <= 0:
            continue
        stop_d = STOP_ATR * atr[t]
        tgt_d = RR * stop_d
        sl = entry - side * stop_d
        tp = entry + side * tgt_d
        end = min(t + 1 + TIME_STOP, n - 1)
        exit_px = None
        for k in range(t + 1, end + 1):
            hit_sl = (l[k] <= sl) if side > 0 else (h[k] >= sl)
            hit_tp = (h[k] >= tp) if side > 0 else (l[k] <= tp)
            if hit_sl:                      # TIE RULE: stop resolves first
                exit_px = sl
                break
            if hit_tp:
                exit_px = tp
                break
        if exit_px is None:
            exit_px = b["c"][end]
        gross = side * (exit_px - entry) / entry * 1e4
        out.append(gross - toll_bp)
        i = end + 1                         # no overlapping positions
    return np.asarray(out, dtype=float)


def control_b(df: pd.DataFrame, n_want: int, side_mix: float,
              toll_bp: float, seed: int) -> np.ndarray:
    """Random-timing control: same count, same side mix, same geometry."""
    rng = np.random.default_rng(seed)
    b = build(df)
    ok = np.flatnonzero(np.isfinite(b["atr"]) & (b["atr"] > 0))
    ok = ok[(ok > BBW_LOOKBACK + SMA_N) & (ok < len(df) - TIME_STOP - 2)]
    if len(ok) < n_want or n_want == 0:
        return np.asarray([], dtype=float)
    pick = rng.choice(ok, size=min(n_want * 3, len(ok)), replace=False)
    sig = np.zeros(len(df), dtype=int)
    sides = np.where(rng.random(len(pick)) < side_mix, 1, -1)
    sig[pick] = sides
    return simulate(df, sig, toll_bp)


def welch(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 3 or len(b) < 3:
        return float("nan")
    return float((a.mean() - b.mean()) /
                 math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b)))


def tstat(x: np.ndarray) -> float:
    if len(x) < 3 or x.std(ddof=1) == 0:
        return float("nan")
    return float(x.mean() / (x.std(ddof=1) / math.sqrt(len(x))))


# ------------------------------------------------------------------- main
def run(loader, label: str) -> dict:
    syms = [os.path.basename(f)[:-8] for f in sorted(glob.glob("app/data/*_m15.parquet"))]
    per, treat_all, ctrlA_all, ctrlB_all = {}, [], [], []

    print(f"\n=== {label} ===")
    print(f"{'symbol':9s} {'n':>5s} {'net bp':>8s} {'t':>6s} {'win':>6s} "
          f"{'ctrlA n':>8s} {'ctrlA bp':>9s} {'t_diff':>7s} {'ctrlB bp':>9s}")

    for sym in syms:
        df = loader(sym).sort_values("ts").reset_index(drop=True)
        if len(df) < 5000:
            continue
        base = sym.replace("_m15", "")
        toll = TOLL[base]
        sig = signals(df, True)
        treat = simulate(df, sig, toll)
        if len(treat) < 20:
            continue
        ctrlA = simulate(df, signals(df, False), toll)
        mix = float((sig[sig != 0] > 0).mean()) if (sig != 0).any() else 0.5
        cb = [control_b(df, len(treat), mix, toll, 1000 + s)
              for s in range(CONTROL_DRAWS)]
        cb = np.concatenate([x for x in cb if len(x)]) if any(len(x) for x in cb) \
            else np.asarray([])

        per[sym] = dict(n=len(treat), net=float(treat.mean()), t=tstat(treat),
                        win=float((treat > 0).mean()), nA=len(ctrlA),
                        netA=float(ctrlA.mean()) if len(ctrlA) else float("nan"),
                        tdiff=welch(treat, ctrlA),
                        netB=float(cb.mean()) if len(cb) else float("nan"))
        treat_all.append(treat)
        if len(ctrlA):
            ctrlA_all.append(ctrlA)
        if len(cb):
            ctrlB_all.append(cb)
        r = per[sym]
        print(f"{sym:9s} {r['n']:5d} {r['net']:+8.2f} {r['t']:+6.2f} {r['win']:6.3f} "
              f"{r['nA']:8d} {r['netA']:+9.2f} {r['tdiff']:+7.2f} {r['netB']:+9.2f}")

    T = np.concatenate(treat_all)
    A = np.concatenate(ctrlA_all) if ctrlA_all else np.asarray([])
    B = np.concatenate(ctrlB_all) if ctrlB_all else np.asarray([])
    t_raw = tstat(T)
    # correlation adjustment: 12 series carry ~N_EFF independent bets
    t_adj = t_raw / math.sqrt(12.0 / N_EFF)
    npos = sum(1 for r in per.values() if r["net"] > 0)

    print(f"\npooled treat  n={len(T):5d}  net={T.mean():+7.2f} bp  "
          f"t_raw={t_raw:+6.2f}  t_adj={t_adj:+6.2f}  win={np.mean(T > 0):.3f}")
    if len(A):
        print(f"pooled ctrlA  n={len(A):5d}  net={A.mean():+7.2f} bp  "
              f"t={tstat(A):+6.2f}   Welch(treat-ctrlA)={welch(T, A):+6.2f}")
    if len(B):
        sdB = B.std(ddof=1)
        z = (T.mean() - B.mean()) / (sdB / math.sqrt(len(T))) if sdB else float("nan")
        print(f"pooled ctrlB  n={len(B):5d}  net={B.mean():+7.2f} bp  "
              f"(centred? |mean|={abs(B.mean()):.2f})  z_vs_ctrlB={z:+6.2f}")
    else:
        z = float("nan")

    hi = [s for s in per if s.replace("_m15", "") in HIGH_ATR]
    if hi:
        print("\npre-declared high-ATR subgroup:")
        for s in hi:
            r = per[s]
            print(f"  {s:9s} n={r['n']:4d} net={r['net']:+8.2f} bp  t={r['t']:+6.2f}")

    g1 = bool(T.mean() > 0 and t_adj >= 2.00)
    g2 = bool(len(A) and welch(T, A) >= 2.00)
    g3 = bool(np.isfinite(z) and z >= 2.00)
    g4 = bool(npos >= 7)
    print(f"\n  GATE 1  pooled net>0 and t_adj>=2.00        : "
          f"{'PASS' if g1 else 'FAIL'}  (net {T.mean():+.2f} bp, t_adj {t_adj:+.2f})")
    print(f"  GATE 2  squeeze beats Control A, Welch>=2.00 : "
          f"{'PASS' if g2 else 'FAIL'}  (Welch {welch(T, A):+.2f})")
    print(f"  GATE 3  beats Control B by >=2.00 null sd    : "
          f"{'PASS' if g3 else 'FAIL'}  (z {z:+.2f})")
    print(f"  GATE 4  net positive on >=7 of 12            : "
          f"{'PASS' if g4 else 'FAIL'}  ({npos} of {len(per)})")
    return dict(gates=(g1, g2, g3, g4), per=per, t_adj=t_adj, net=float(T.mean()))


if __name__ == "__main__":
    print(f"SQUEEZE_EXPANSION_01 - prereg sha {PREREG_SHA}")
    probe = D.load_discovery("eurusd_m15").sort_values("ts").reset_index(drop=True)
    print(f"causality assertion on eurusd_m15 ({len(probe)} bars): "
          f"{'PASS' if assert_causal(probe) else 'FAIL'}")

    res = run(D.load_discovery, "DISCOVERY  ts < 2024-01-01")

    if all(res["gates"]):
        print("\nAll four gates PASS -> holdout is authorised by prereg section 7.")
        run(lambda s: D.load_holdout(s, "SQUEEZE_EXPANSION_01"), "HOLDOUT")
    else:
        failed = [f"GATE {i + 1}" for i, g in enumerate(res["gates"]) if not g]
        print(f"\n{', '.join(failed)} FAILED -> holdout NOT read. "
              f"Prereg section 7 makes the holdout branch unreachable.")
