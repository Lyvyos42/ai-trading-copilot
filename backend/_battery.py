"""Level-primitive battery: 9 primitives x 12 symbols, each with its own control.

Every primitive is measured identically: find the level causally, wait for a
LATER touch, and record the forward return signed so POSITIVE means the level
held. Every primitive gets a control chosen to isolate its specific claim rather
than a generic one:

    fvg / order_block / equal_highs / asian_range   displaced 1.5-3 ATR
    prior_day_hl                                    the extreme 5 sessions back
    prior_week_hl                                   the extreme 3 weeks back
    round_number                                    an offset grid, same density
    weekend_gap                                     a midweek gap of equal size
    fractal_pivot                                   displaced (known refuted;
                                                    carried as calibration)

Cross-symbol consistency is the evidence. A real primitive should point the same
way on twelve instruments; a fitted one will not.
"""
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

ATH = ZoneInfo("Europe/Athens")
LON = ZoneInfo("Europe/London")
ZONE = 0.25          # touch tolerance in ATR
EXPIRY = 200
MINGAP = 20

SYMBOLS = ["eurusd", "gbpusd", "audusd", "nzdusd", "usdcad", "usdchf",
           "usdjpy", "eurjpy", "eurgbp", "xauusd", "xagusd", "wti"]


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
    d["lon"] = d.ath.dt.tz_convert(LON)
    d["day"] = d.lon.dt.date
    d["lh"] = d.lon.dt.hour
    return d


def _measure(d, levels, expiry=EXPIRY, mingap=MINGAP):
    """levels = list of (from_bar, price, kind). kind +1 = overhead resistance."""
    h, l, c, atr = d.high.values, d.low.values, d.close.values, d.atr.values
    n = len(d)
    ev = []
    for b0, price, kind in levels:
        if b0 >= n - 21 or not np.isfinite(price):
            continue
        for j in range(b0 + mingap, min(n - 21, b0 + expiry)):
            a = atr[j]
            if not np.isfinite(a) or a <= 0:
                continue
            z = a * ZONE
            hit = (h[j] >= price - z and c[j] < price) if kind > 0 else \
                  (l[j] <= price + z and c[j] > price)
            if hit:
                ev.append(-kind * (c[min(j + 10, n - 1)] - c[j]) / a)
                break
    return np.array(ev)


def _disp(levels, d, rng):
    atr = d.atr.values
    out = []
    for b0, price, kind in levels:
        a = atr[b0] if b0 < len(atr) and np.isfinite(atr[b0]) else np.nan
        if not np.isfinite(a) or a <= 0:
            continue
        out.append((b0, price + rng.choice([-1, 1]) * rng.uniform(1.5, 3.0) * a, kind))
    return out


# ---- primitives: each returns a list of (bar, price, kind) -----------------
def p_fractal(d, pl=5):
    h, l = d.high.values, d.low.values
    out = []
    for j in range(pl, len(d) - pl):
        if h[j] == h[j - pl:j + pl + 1].max():
            out.append((j + pl, h[j], 1))
        if l[j] == l[j - pl:j + pl + 1].min():
            out.append((j + pl, l[j], -1))
    return out


def p_fvg(d, mn=0.25):
    h, l, atr = d.high.values, d.low.values, d.atr.values
    out = []
    for i in range(20, len(d) - 21):
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        if h[i - 2] < l[i] and (l[i] - h[i - 2]) > a * mn:
            out.append((i, (h[i - 2] + l[i]) / 2, -1))
        elif l[i - 2] > h[i] and (l[i - 2] - h[i]) > a * mn:
            out.append((i, (h[i] + l[i - 2]) / 2, 1))
    return out


def p_order_block(d, imp=1.5):
    """Last opposite-colour candle before an impulsive move."""
    o, c, h, l, atr = d.open.values, d.close.values, d.high.values, d.low.values, d.atr.values
    out = []
    for i in range(20, len(d) - 21):
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        move = c[i] - o[i]
        if move > a * imp and c[i - 1] < o[i - 1]:          # bullish OB
            out.append((i, (o[i - 1] + c[i - 1]) / 2, -1))
        elif -move > a * imp and c[i - 1] > o[i - 1]:       # bearish OB
            out.append((i, (o[i - 1] + c[i - 1]) / 2, 1))
    return out


def p_equal_highs(d, tol=0.15, look=30):
    """Two swing extremes within tol*ATR - an SMC 'liquidity pool'."""
    h, l, atr = d.high.values, d.low.values, d.atr.values
    piv = p_fractal(d)
    hs = [(b, p) for b, p, k in piv if k > 0]
    ls = [(b, p) for b, p, k in piv if k < 0]
    out = []
    for arr, kind in ((hs, 1), (ls, -1)):
        for i in range(1, len(arr)):
            b1, p1 = arr[i]
            b0, p0 = arr[i - 1]
            if b1 - b0 > look:
                continue
            a = atr[b1] if np.isfinite(atr[b1]) else np.nan
            if not np.isfinite(a) or a <= 0:
                continue
            if abs(p1 - p0) < a * tol:
                out.append((b1, max(p0, p1) if kind > 0 else min(p0, p1), kind))
    return out


def p_asian(d):
    """Asian session (00:00-07:00 London) range extremes, used the same day."""
    out = []
    for day, g in d.groupby("day"):
        a = g[g.lh < 7]
        if len(a) < 4:
            continue
        end = a.index[-1]
        out.append((end, a.high.max(), 1))
        out.append((end, a.low.min(), -1))
    return out


def p_prior_day(d, lag=1):
    days = sorted(set(d.day))
    idx = {x: np.where(d.day.values == x)[0] for x in days}
    h, l = d.high.values, d.low.values
    out = []
    for k in range(lag, len(days)):
        ref, cur = days[k - lag], days[k]
        b0 = idx[cur][0]
        out.append((b0, h[idx[ref]].max(), 1))
        out.append((b0, l[idx[ref]].min(), -1))
    return out


def p_prior_week(d, lag=1):
    wk = d.lon.dt.isocalendar()
    key = list(zip(wk.year.values, wk.week.values))
    d2 = d.assign(_w=key)
    ws = sorted(set(key))
    idx = {w: np.where(np.array([k == w for k in key]))[0] for w in ws}
    h, l = d.high.values, d.low.values
    out = []
    for k in range(lag, len(ws)):
        ref, cur = ws[k - lag], ws[k]
        if len(idx[cur]) == 0 or len(idx[ref]) == 0:
            continue
        b0 = idx[cur][0]
        out.append((b0, h[idx[ref]].max(), 1))
        out.append((b0, l[idx[ref]].min(), -1))
    return out
