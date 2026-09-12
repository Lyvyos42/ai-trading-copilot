"""
VOLMOM_01 - volatility-conditioned G10 cross-sectional currency momentum
========================================================================
Runs exactly what prereg/VOLMOM_01.md specifies, sealed at 7e7468eafae22ec6
before any portfolio return was computed.

NOT A CARRY TEST. There is no rate data in this repository, so the interest
differential cannot be computed and the ranking signal is trailing 12-month
SPOT return. See prereg section 1.

DEFENCES:
  1. assert_causal() rebuilds the whole weight path on truncated prefixes.
  2. Rebalances are 22 trading days apart and held exactly one cycle, so
     monthly returns are non-overlapping by construction.
  3. The holdout branch is unreachable unless all four gates pass.
  4. Tolls come from TOLL_BREAKEVEN_01 section 4 for all seven instruments;
     none is invented here (unlike _squeeze_expansion.py, which is disclosed).
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

import _discovery as D

PREREG_SHA = "7e7468eafae22ec6"

U = ["eurusd", "gbpusd", "audusd", "nzdusd", "usdcad", "usdchf", "usdjpy"]
INV = {"usdcad", "usdchf", "usdjpy"}          # quoted USD-base; invert to get FX/USD
LAB = {"eurusd": "EUR", "gbpusd": "GBP", "audusd": "AUD", "nzdusd": "NZD",
       "usdcad": "CAD", "usdchf": "CHF", "usdjpy": "JPY"}
TOLL_BP = {"EUR": 2.88, "GBP": 3.10, "JPY": 3.51, "AUD": 5.08,
           "CAD": 2.21, "NZD": 7.33, "CHF": 4.48}          # section 4, GBP corrected
CLUSTER = {"EUR": 0, "CHF": 0, "GBP": 1, "AUD": 2, "NZD": 2, "CAD": 2, "JPY": 3}

VOL_N, BASE_N, MOM_N, STEP, K = 22, 60, 252, 22, 2
SUBWINDOWS = [("2010-09", "2014-01"), ("2014-01", "2017-05"),
              ("2017-05", "2020-09"), ("2020-09", "2023-12")]


def daily_panel(loader) -> pd.DataFrame:
    """Last H1 close at or before 22:00 UTC each day; inverted where needed."""
    cols = {}
    for k in U:
        d = loader(f"{k}_h1").sort_values("ts")
        s = d.set_index("ts")["close"]
        s = s[s.index.hour <= 22]
        s = s.resample("1D").last().dropna()
        cols[LAB[k]] = 1.0 / s if k in INV else s
    return pd.DataFrame(cols).dropna()


def state(P: pd.DataFrame):
    R = np.log(P).diff()
    rv = (R ** 2).rolling(VOL_N).mean().apply(np.sqrt) * math.sqrt(252)
    sig = rv.mean(axis=1)
    base = sig.rolling(BASE_N).mean().shift(1)          # causal
    calm = sig < base
    mom = np.log(P) - np.log(P.shift(MOM_N))
    return R, sig, base, calm, mom


def pick(row: pd.Series, sign: int):
    """Top-K by momentum, at most one per cluster. sign=+1 long, -1 short."""
    order = row.sort_values(ascending=(sign < 0)).index
    out, used = [], set()
    for c in order:
        cl = CLUSTER[c]
        if cl in used:
            continue
        out.append(c)
        used.add(cl)
        if len(out) == K:
            break
    return out


def weights(P: pd.DataFrame, conditioned: bool):
    """Weight matrix at each rebalance date. Uses only completed bars."""
    R, sig, base, calm, mom = state(P)
    start = max(MOM_N, VOL_N + BASE_N) + 1
    dates = P.index[start::STEP]
    W = pd.DataFrame(0.0, index=dates, columns=P.columns)
    for t in dates:
        m = mom.loc[t]
        if m.isna().any() or not np.isfinite(base.loc[t]):
            continue
        if conditioned and not bool(calm.loc[t]):
            continue                                   # flat to cash
        for c in pick(m, +1):
            W.at[t, c] = +0.5
        for c in pick(m, -1):
            W.at[t, c] = -0.5
    return W


def returns(P: pd.DataFrame, W: pd.DataFrame, charge_toll: bool = True):
    """Net monthly return in bp. Toll charged on every leg that CHANGES."""
    out, prev = [], pd.Series(0.0, index=P.columns)
    idx = list(W.index)
    for i, t in enumerate(idx):
        if i + 1 >= len(idx):
            break
        nxt = idx[i + 1]
        w = W.loc[t]
        fwd = (np.log(P.loc[nxt]) - np.log(P.loc[t])) * 1e4
        gross = float((w * fwd).sum())
        toll = 0.0
        if charge_toll:
            for c in P.columns:
                if abs(w[c] - prev[c]) > 1e-12:
                    toll += abs(w[c] - prev[c]) * TOLL_BP[c]
        # 'start' is the DECISION date. Partitioning by 'ts' (the period END)
        # would classify a month by a regime observed after it was entered --
        # the same error that took the DAX proposal from t -1.06 to +5.54.
        out.append((nxt, t, gross - toll, gross))
        prev = w
    s = pd.DataFrame(out, columns=["ts", "start", "net", "gross"]).set_index("ts")
    return s


def assert_causal(P: pd.DataFrame) -> bool:
    full = weights(P, True)
    for frac in (0.5, 0.7, 0.9):
        cut = int(len(P) * frac)
        part = weights(P.iloc[:cut], True)
        common = part.index.intersection(full.index)
        if len(common) < 5:
            continue
        if not np.allclose(part.loc[common].to_numpy(),
                           full.loc[common].to_numpy(), atol=1e-12):
            raise AssertionError(f"LOOKAHEAD at frac={frac}")
    return True


def tstat(x):
    x = np.asarray(x, float)
    return float(x.mean() / (x.std(ddof=1) / math.sqrt(len(x)))) if len(x) > 2 else float("nan")


def welch(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    return float((a.mean() - b.mean()) /
                 math.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b)))


def sharpe(x):
    x = np.asarray(x, float)
    s = x.std(ddof=1)
    return float(x.mean() / s * math.sqrt(12)) if s > 0 else float("nan")


def maxdd(x):
    eq = np.cumsum(np.asarray(x, float))
    return float((np.maximum.accumulate(eq) - eq).max())


def control_b(P, template: pd.DataFrame, draws=100):
    """Random long/short selection, same dates, same geometry, same tolls."""
    rng = np.random.default_rng(4242)
    cols = list(P.columns)
    means = []
    for d in range(draws):
        W = pd.DataFrame(0.0, index=template.index, columns=cols)
        for t in template.index:
            if not template.loc[t].abs().sum():
                continue                        # respect the cash months
            p = rng.permutation(cols)
            for c in p[:K]:
                W.at[t, c] = +0.5
            for c in p[K:2 * K]:
                W.at[t, c] = -0.5
        means.append(returns(P, W)["net"].to_numpy())
    return np.concatenate(means), np.array([m.mean() for m in means])


def run(loader, label):
    P = daily_panel(loader)
    print(f"\n=== {label} ===")
    print(f"daily panel {len(P)} days  {P.index.min().date()} -> {P.index.max().date()}")

    Wc = weights(P, True)
    Wu = weights(P, False)
    cond = returns(P, Wc)
    unc = returns(P, Wu)
    invested = int((Wc.abs().sum(axis=1) > 0).sum())
    print(f"rebalances {len(Wc)}  invested {invested}  flat {len(Wc)-invested} "
          f"({1-invested/len(Wc):.1%})")

    net = cond["net"].to_numpy()
    net_inv = cond["net"].to_numpy()[(Wc.abs().sum(axis=1) > 0).to_numpy()[:len(cond)]]
    ann_vol = float(np.std(unc["gross"].to_numpy(), ddof=1) * math.sqrt(12) / 1e4)
    print(f"\nrealised basket vol (unconditioned, gross) = {ann_vol:.2%} annualised "
          f"(prereg assumed 8.0%)")
    mde = 2.00 * np.std(net_inv, ddof=1) / math.sqrt(len(net_inv))
    print(f"MDE restated from realised vol: {mde:+.1f} bp/month at t=2.00 "
          f"(n={len(net_inv)} invested)")

    print(f"\n{'series':22s} {'n':>4s} {'mean bp':>9s} {'t':>7s} {'Sharpe':>8s} {'MaxDD bp':>9s}")
    for tag, x in (("conditioned NET", net), ("conditioned GROSS", cond["gross"].to_numpy()),
                   ("uncond (Ctrl A) NET", unc["net"].to_numpy()),
                   ("uncond (Ctrl A) GROSS", unc["gross"].to_numpy())):
        print(f"{tag:22s} {len(x):4d} {np.mean(x):+9.2f} {tstat(x):+7.2f} "
              f"{sharpe(x):+8.3f} {maxdd(x):9.1f}")
    print(f"{'conditioned NET (inv)':22s} {len(net_inv):4d} {net_inv.mean():+9.2f} "
          f"{tstat(net_inv):+7.2f} {sharpe(net_inv):+8.3f} {maxdd(net_inv):9.1f}")

    # Gate 2: partition CONTROL A by regime
    R, sig, base, calm, mom = state(P)
    cal = calm.reindex(pd.DatetimeIndex(unc["start"]), method="ffill").to_numpy().astype(bool)
    a = unc["net"].to_numpy()[cal]
    b = unc["net"].to_numpy()[~cal]
    g2t = welch(a, b)
    print(f"\nGate 2 partition: calm n={len(a)} mean={a.mean():+.2f} bp | "
          f"stress n={len(b)} mean={b.mean():+.2f} bp | Welch t={g2t:+.2f}")

    B, bmeans = control_b(P, Wc)
    g3t = welch(net, B)
    print(f"Control B: {len(B)} obs over 100 draws, mean={B.mean():+.2f} bp "
          f"(centred? |mean|={abs(B.mean()):.2f}), Welch t={g3t:+.2f}")

    subs = []
    for lo, hi in SUBWINDOWS:
        seg = cond.loc[(cond.index >= lo) & (cond.index < hi), "net"]
        subs.append((lo, hi, len(seg), float(seg.sum()) if len(seg) else float("nan")))
    print("\nsub-windows (net bp, summed):")
    for lo, hi, n, s in subs:
        print(f"  {lo} .. {hi}  n={n:3d}  {s:+9.1f}")
    npos = sum(1 for *_, s in subs if s > 0)

    g1 = bool(np.mean(net) > 0 and tstat(net) >= 2.00)
    g2 = bool(a.mean() - b.mean() > 0 and g2t >= 2.00)
    g3 = bool(g3t >= 2.00)
    g4 = bool(npos >= 3)
    print(f"\n  GATE 1  net>0 and t>=2.00                 : {'PASS' if g1 else 'FAIL'}"
          f"  (net {np.mean(net):+.2f} bp, t {tstat(net):+.2f})")
    print(f"  GATE 2  calm beats stress, Welch>=2.00    : {'PASS' if g2 else 'FAIL'}"
          f"  (t {g2t:+.2f})")
    print(f"  GATE 3  beats random selection, t>=2.00   : {'PASS' if g3 else 'FAIL'}"
          f"  (t {g3t:+.2f})")
    print(f"  GATE 4  net>0 in >=3 of 4 sub-windows     : {'PASS' if g4 else 'FAIL'}"
          f"  ({npos} of 4)")
    return (g1, g2, g3, g4)


if __name__ == "__main__":
    print(f"VOLMOM_01 - prereg sha {PREREG_SHA}")
    Pd = daily_panel(D.load_discovery)
    print(f"causality assertion: {'PASS' if assert_causal(Pd) else 'FAIL'}")
    gates = run(D.load_discovery, "DISCOVERY  ts < 2024-01-01")
    if all(gates):
        print("\nAll gates PASS -> holdout authorised by prereg section 5.")
        run(lambda s: D.load_holdout(s, "VOLMOM_01"), "HOLDOUT")
    else:
        bad = [f"GATE {i+1}" for i, g in enumerate(gates) if not g]
        print(f"\n{', '.join(bad)} FAILED -> holdout NOT read.")
