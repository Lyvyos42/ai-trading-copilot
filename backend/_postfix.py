"""Candidate 24: daily post-fix reversion at the London 16:00 WMR fix.

PRE-REGISTERED BEFORE EXECUTION

    hypothesis  the dealer inventory built to service the 16:00 London fix is
                unwound in the following hour, so the fix-hour move partially
                reverses. Verified at month-end on all six pairs (t -3.77 to
                -5.36); this asks whether it is a DAILY phenomenon.
    universe    EURUSD, GBPUSD, AUDUSD, NZDUSD, USDCAD, USDCHF H1, 2010-2026
    n           ~4,137 sessions per pair, 24.8x the month-end sample
    signal      r15 = the 15:00-16:00 London bar return (server hour 17)
    trade       at the 16:00 London open take the OPPOSITE side of r15,
                exit at the 17:00 London close
    costs       non-zero-median spread + $3/lot, expressed in bp
    power       filed a priori: post-fix sigma ~12 bp, so n=4,100 detects a
                0.50 bp mean at t 2.0. The toll is 0.64-1.87 bp, so COST, not
                power, is the binding constraint - the first time in this
                programme that has been true.

THE CONTROL IS THE EXPERIMENT, AGAIN

Bid-ask bounce induces negative autocorrelation between ANY two adjacent bars:
r(h) ends at the same printed price where r(h+1) begins, so noise in that
shared price pushes one up and the other down. A negative beta at the fix hour
is therefore NOT evidence of anything on its own.

The test is whether beta at the fix hour is more negative than the beta at the
other 23 hour-pairs of the same instrument. If the fix hour sits inside the
ordinary distribution, the reversion is microstructure noise and the candidate
is refuted regardless of its t-statistic.

GATES
    1  beta(fix) < 0 at |t| >= 2.39 (Bonferroni, 6 pairs)
    2  beta(fix) below the 5th percentile of the other 23 hourly betas
    3  tradeable net > 0 at t >= 1.65 after the measured toll
    4  chronological 80/20 holdout, OOS net > 0
    5  era stability: 2010-2015 and 2016-2026 both positive
"""
import math

import numpy as np
import pandas as pd
from scipy import stats
from zoneinfo import ZoneInfo

ATH = ZoneInfo("Europe/Athens")
LON = ZoneInfo("Europe/London")
PAIRS = ["eurusd", "gbpusd", "audusd", "nzdusd", "usdcad", "usdchf"]
FIX_HOUR_LON = 15          # the 15:00-16:00 London bar, i.e. into the fix
COMMISSION_USD = 3.00


def load(sym):
    d = pd.read_parquet(f"app/data/{sym}_h1.parquet")
    r = pd.to_datetime(d["time"], utc=True).dt.tz_localize(None)
    a = r.dt.tz_localize(ATH, ambiguous="NaT", nonexistent="NaT")
    d = d.assign(ath=a)
    d = d[d.ath.notna()]
    d = d.assign(lon=d.ath.dt.tz_convert(LON))
    d = d.assign(ld=d.lon.dt.date, lh=d.lon.dt.hour)
    d = d.assign(bp=(np.log(d.close) - np.log(d.open)) * 10000)
    return d.sort_values("lon").reset_index(drop=True)


def toll_bp(d, hour):
    x = d[d.lh == hour]
    sp = x.spread * 1e-5
    nz = sp[sp > 0].median()
    return float((nz + COMMISSION_USD / 100000) / x.close.mean() * 10000)


def hour_pairs(d, h):
    """r(h) and r(h+1) on the same London day, aligned."""
    a = d[d.lh == h][["ld", "bp"]].rename(columns={"bp": "x"})
    b = d[d.lh == (h + 1) % 24][["ld", "bp"]].rename(columns={"bp": "y"})
    m = a.merge(b, on="ld", how="inner")
    return m


def beta(m):
    if len(m) < 50:
        return np.nan, np.nan, 0
    sl = stats.linregress(m.x.values, m.y.values)
    return sl.slope, sl.slope / sl.stderr, len(m)


def tstat(x):
    x = np.asarray(x, float)
    return x.mean() / (x.std(ddof=1) / math.sqrt(len(x))) if len(x) > 1 else 0.0
