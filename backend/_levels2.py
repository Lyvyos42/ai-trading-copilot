"""Three level primitives: prior-day extremes, round numbers, and SMC gaps.

Each has a mechanism behind it, unlike the fractal pivots already refuted:
  prior-day H/L   resting stops cluster just beyond yesterday's extremes
  round numbers   option strikes and human/algo order placement
  fair value gap  the core SMC claim - an imbalance price must return to fill

ROUND NUMBERS ARE THE CLEANEST TEST IN THE PROGRAMME
The level is EXOGENOUS. It is not derived from price, so there is no circularity
to design around and no need for a displaced fake. The control is a grid of the
same density offset off the round figure - same number of levels, same spacing,
just not aligned to human-salient numbers.
"""
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

ATH = ZoneInfo("Europe/Athens")
ZONE_ATR = 0.25


def load(sym):
    d = pd.read_parquet(f"app/data/{sym}_h1.parquet")
    t = pd.to_datetime(d["time"], utc=True).dt.tz_localize(None)
    a = t.dt.tz_localize(ATH, ambiguous="NaT", nonexistent="NaT")
    d = d.assign(ath=a)
    d = d[d.ath.notna()].reset_index(drop=True)
    h, l, c = d.high.values, d.low.values, d.close.values
    pc = np.concatenate([[c[0]], c[:-1]])
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    d["atr"] = pd.Series(tr).rolling(14).mean().values
    d["day"] = d.ath.dt.date
    return d


def _fwd(c, atr, j, n, k):
    return (c[min(j + k, n - 1)] - c[j]) / atr[j]


def grid_touches(d, step, offset=0.0):
    """Every approach to a price grid of spacing `step`, shifted by `offset`.

    offset 0 gives the round-number grid; offset step/3 gives a control grid of
    identical density that is not aligned to salient numbers.
    """
    h, l, c, atr = d.high.values, d.low.values, d.close.values, d.atr.values
    n = len(d)
    ev = []
    prev_lvl = None
    for j in range(20, n - 21):
        a = atr[j]
        if not np.isfinite(a) or a <= 0:
            continue
        z = a * ZONE_ATR
        lvl = round((c[j] - offset) / step) * step + offset
        if abs(c[j] - lvl) > z:
            prev_lvl = None
            continue
        if lvl == prev_lvl:                    # one event per approach
            continue
        prev_lvl = lvl
        # approach direction: from below means the level is overhead resistance
        kind = 1 if c[j] <= lvl else -1
        ev.append({"kind": kind, "r5": _fwd(c, atr, j, n, 5),
                   "r10": _fwd(c, atr, j, n, 10), "r20": _fwd(c, atr, j, n, 20)})
    return pd.DataFrame(ev)


def prior_day_touches(d, lag=1):
    """Touches of the high/low of the session `lag` days back."""
    h, l, c, atr = d.high.values, d.low.values, d.close.values, d.atr.values
    n = len(d)
    days = sorted(set(d.day))
    idx = {dd: np.where(d.day.values == dd)[0] for dd in days}
    hi = {dd: h[idx[dd]].max() for dd in days}
    lo = {dd: l[idx[dd]].min() for dd in days}
    ev = []
    for k in range(lag, len(days)):
        today, ref = days[k], days[k - lag]
        rows = idx[today]
        for lvl, kind in ((hi[ref], 1), (lo[ref], -1)):
            for j in rows:
                if j >= n - 21:
                    break
                a = atr[j]
                if not np.isfinite(a) or a <= 0:
                    continue
                z = a * ZONE_ATR
                hit = (h[j] >= lvl - z and c[j] < lvl) if kind > 0 else \
                      (l[j] <= lvl + z and c[j] > lvl)
                if hit:
                    ev.append({"kind": kind, "r5": _fwd(c, atr, j, n, 5),
                               "r10": _fwd(c, atr, j, n, 10),
                               "r20": _fwd(c, atr, j, n, 20)})
                    break
    return pd.DataFrame(ev)


def fvg_touches(d, min_atr=0.25, expiry=200, fake=False, rng=None):
    """Fair value gaps: high[i-2] < low[i] is a bullish imbalance. SMC claims
    price returns to fill it and the zone then holds."""
    h, l, c, atr = d.high.values, d.low.values, d.close.values, d.atr.values
    n = len(d)
    ev = []
    for i in range(20, n - 21):
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        bull = h[i - 2] < l[i] and (l[i] - h[i - 2]) > a * min_atr
        bear = l[i - 2] > h[i] and (l[i - 2] - h[i]) > a * min_atr
        if not (bull or bear):
            continue
        kind = -1 if bull else 1          # bullish gap = support below
        lo_z, hi_z = (h[i - 2], l[i]) if bull else (h[i], l[i - 2])
        if fake:
            shift = rng.choice([-1, 1]) * rng.uniform(1.5, 3.0) * a
            lo_z, hi_z = lo_z + shift, hi_z + shift
        for j in range(i + 3, min(n - 21, i + expiry)):
            aj = atr[j]
            if not np.isfinite(aj) or aj <= 0:
                continue
            if l[j] <= hi_z and h[j] >= lo_z:      # price entered the zone
                ev.append({"kind": kind, "r5": _fwd(c, atr, j, n, 5),
                           "r10": _fwd(c, atr, j, n, 10),
                           "r20": _fwd(c, atr, j, n, 20)})
                break
    return pd.DataFrame(ev)


def stats(df, hz="r10"):
    if df is None or df.empty or len(df) < 50:
        return None
    s = -df["kind"] * df[hz]              # +ve = the level HELD
    return s.mean(), s.mean() / (s.std() / np.sqrt(len(s))), (s > 0).mean(), len(s)
