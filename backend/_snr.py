"""Do support/resistance levels predict anything, or are they tautologies?

THE TRAP THIS IS BUILT TO AVOID
A pivot high is DEFINED as a local maximum. Price reversed there - that is what
made it a pivot. Measuring "price reverses at pivot levels" over the window that
created them is circular and will always confirm.

The only non-circular question is whether price reverses when it RETURNS to a
level that was established earlier. So levels are built causally from bars up to
i, and every measurement is taken on touches at bars strictly after the pivot
that created the level.

THE CONTROL
Being at any particular price is not neutral - price is mean-reverting at some
horizons and trending at others, and a level sits at a distance from the current
price that is itself informative. So each real level is matched with a FAKE
level: same instrument, same bar, same signed ATR-distance from the price at the
time the level was formed, but placed where no pivot exists. If real levels
carry information, touches on them behave differently from touches on fakes.

WHAT FOLKLORE CLAIMS, STATED SO IT CAN FAIL
  1. price reverses at S/R more often than at an arbitrary price
  2. more touches make a level stronger
  3. a broken level becomes support/resistance in the opposite sense
Each is measured separately.
"""
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

ATH = ZoneInfo("Europe/Athens")
PIVOT_LEN = 5           # fractal half-width, the engine's snr_pivot_len default
ZONE_ATR = 0.25         # touch tolerance, in ATR
EXPIRY = 500            # bars a level stays live
MIN_GAP = 20            # a touch must be this far after the pivot that made it


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
    return d


def pivots(d):
    """Causal fractal pivots: confirmed PIVOT_LEN bars after they form."""
    h, l = d.high.values, d.low.values
    n = len(d)
    out = []
    for j in range(PIVOT_LEN, n - PIVOT_LEN):
        w = slice(j - PIVOT_LEN, j + PIVOT_LEN + 1)
        if h[j] == h[w].max():
            out.append((j + PIVOT_LEN, h[j], +1))      # confirmed bar, price, resistance
        if l[j] == l[w].min():
            out.append((j + PIVOT_LEN, l[j], -1))      # support
    return out


def touches(d, levels, fake_offset=None, rng=None):
    """Every later approach to a live level. fake_offset shifts the level to a
    price where no pivot is, preserving distance-from-price geometry."""
    h, l, c, atr = d.high.values, d.low.values, d.close.values, d.atr.values
    n = len(d)
    ev = []
    for conf_bar, price, kind in levels:
        if not np.isfinite(atr[conf_bar]) or atr[conf_bar] <= 0:
            continue
        lvl = price
        if fake_offset is not None:
            # displace by 1-3 ATR in a random direction: same kind of distance,
            # no pivot there
            lvl = price + rng.choice([-1, 1]) * rng.uniform(1.0, 3.0) * atr[conf_bar]
        start = conf_bar + MIN_GAP
        end = min(n - 21, conf_bar + EXPIRY)
        for j in range(start, end):
            if not np.isfinite(atr[j]) or atr[j] <= 0:
                continue
            z = atr[j] * ZONE_ATR
            hit = (h[j] >= lvl - z and c[j] < lvl) if kind > 0 else \
                  (l[j] <= lvl + z and c[j] > lvl)
            if hit:
                ev.append({"bar": j, "kind": kind, "level": lvl, "atr": atr[j],
                           "close": c[j],
                           "r5": (c[min(j + 5, n - 1)] - c[j]) / atr[j],
                           "r10": (c[min(j + 10, n - 1)] - c[j]) / atr[j],
                           "r20": (c[min(j + 20, n - 1)] - c[j]) / atr[j]})
                break          # first touch only; later ones are not independent
    return pd.DataFrame(ev)


def reversal_stats(df):
    """A 'reversal' is a move AWAY from the level: down off resistance, up off
    support. Signed so positive always means the level held."""
    if df.empty:
        return {}
    out = {}
    for hz in ("r5", "r10", "r20"):
        s = -df["kind"] * df[hz]          # +ve = level held
        out[hz] = (s.mean(), s.std() / np.sqrt(len(s)), (s > 0).mean(), len(s))
    return out
