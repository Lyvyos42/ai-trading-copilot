"""Run the level-primitive battery across all symbols and print the matrix."""
import math
import pickle
import sys
import warnings

import numpy as np

warnings.filterwarnings("ignore")
sys.path.insert(0, ".")
from _battery import (SYMBOLS, load, _measure, _disp, p_fractal, p_fvg,   # noqa
                      p_order_block, p_equal_highs, p_asian, p_prior_day,
                      p_prior_week, ZONE)

rng = np.random.default_rng(19)
STEP = {"xauusd": 10.0, "xagusd": 0.25, "wti": 0.50, "usdjpy": 0.50,
        "eurjpy": 0.50}


def round_grid(d, sym, offset_frac=0.0):
    step = STEP.get(sym, 0.0050)
    c, atr = d.close.values, d.atr.values
    off = step * offset_frac
    out, prev = [], None
    for j in range(20, len(d) - 21):
        a = atr[j]
        if not np.isfinite(a) or a <= 0:
            continue
        lvl = round((c[j] - off) / step) * step + off
        if abs(c[j] - lvl) > a * ZONE:
            prev = None
            continue
        if lvl == prev:
            continue
        prev = lvl
        out.append((j, lvl, 1 if c[j] <= lvl else -1))
    return out


def stat(v):
    if v is None or len(v) < 60:
        return None
    return v.mean(), v.mean() / (v.std(ddof=1) / math.sqrt(len(v))), (v > 0).mean(), len(v)


PRIMS = [
    ("fvg",           lambda d, s: p_fvg(d),          "disp"),
    ("order_block",   lambda d, s: p_order_block(d),  "disp"),
    ("equal_highs",   lambda d, s: p_equal_highs(d),  "disp"),
    ("asian_range",   lambda d, s: p_asian(d),        "disp"),
    ("fractal_pivot", lambda d, s: p_fractal(d),      "disp"),
    ("prior_day_hl",  lambda d, s: p_prior_day(d, 1), "lag5"),
    ("prior_week_hl", lambda d, s: p_prior_week(d, 1), "lag3w"),
    ("round_number",  lambda d, s: round_grid(d, s),  "grid"),
]

res = {}
for sym in SYMBOLS:
    d = load(sym)
    print(f"[{sym}] loaded {len(d)} bars", flush=True)
    for name, fn, ctl in PRIMS:
        try:
            lv = fn(d, sym)
            real = _measure(d, lv)
            if ctl == "disp":
                fake = _measure(d, _disp(lv, d, rng))
            elif ctl == "lag5":
                fake = _measure(d, p_prior_day(d, 5))
            elif ctl == "lag3w":
                fake = _measure(d, p_prior_week(d, 3))
            else:
                fake = _measure(d, round_grid(d, sym, 1 / 3))
            res[(sym, name)] = (stat(real), stat(fake))
            a, b = res[(sym, name)]
            if a and b:
                print(f"   {name:14s} real n={a[3]:6d} t{a[1]:+6.2f} held {100*a[2]:5.1f}%  "
                      f"| ctrl t{b[1]:+6.2f}", flush=True)
        except Exception as exc:
            print(f"   {name:14s} FAILED {type(exc).__name__}: {exc}", flush=True)
            res[(sym, name)] = (None, None)

with open("_battery_res.pkl", "wb") as fh:
    pickle.dump(res, fh)
print("written _battery_res.pkl", flush=True)
