"""Load MetaTrader 5 exports and put their timestamps in the right timezone.

THE PROBLEM, WHICH IS NOT COSMETIC

MT5 reports bar times in BROKER SERVER time. The exports in app/data carry a
`datetime64[ns, UTC]` dtype, but the label is wrong: the values are wall-clock
readings from a server running EET/EEST (UTC+2 in winter, UTC+3 in summer).

Established from the data rather than assumed. Median volume by timestamp
half-hour on sp500_m30 jumps 2.7x at 16:30 - from 1,155 to 3,136 - and does so
at 16:30 in BOTH halves of the year. A true UTC series tracking a US session
would move by an hour across US DST; one that does not move is a server clock
that changes on the same weekends the US does. 16:30 server is 09:30 Eastern
in both, which fixes the offset at seven hours.

WHY A FIXED SEVEN-HOUR OFFSET IS STILL WRONG

The US changes clocks on the second Sunday in March and the first Sunday in
November. Europe changes on the last Sunday in March and the last Sunday in
October. For about three weeks a year the two are out of step and the server
sits SIX hours ahead of Eastern instead of seven.

Measured on spy_m30: 6297 bars at -7h and 558 bars at -6h. That is 8.1% of the
series. A hardcoded -7 would place all 558 in the wrong half-hour bucket, and
for a strategy defined by a single 30-minute window that means those sessions
are scored on the 09:00 bar or the 10:00 bar while being labelled 09:30. It
would not error, and the result would look ordinary.

Localising to a real EET/EEST zone and converting to America/New_York gets both
transitions right, including the weeks they disagree, because the zone database
already knows.

VERIFICATION
After conversion, SPY's median real volume by Eastern half-hour is the textbook
US equity U-shape - 2.21M at 09:30, sagging to 0.85M at 13:30, 3.23M into the
15:30 close - across exactly the thirteen half-hours of a cash session. That
shape is the check; a wrong offset does not produce it.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import pandas as pd

ET = ZoneInfo("America/New_York")
# Any EET/EEST zone works; Bucharest is used because it observes the European
# transitions without the historical exceptions some other EET zones carry.
BROKER_TZ = ZoneInfo("Europe/Bucharest")

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

DATASETS = {
    "sp500": "sp500_m30",
    "nasdaq": "nasdaq_m30",
    "us30": "us30_m30",
    "spy": "spy_m30",
    "qqq": "qqq_m30",
}

# MT5 reports `spread` in POINTS - units of the last quoted digit - so it is
# not a price until it is scaled by the instrument's own precision. On sp500,
# quoted to one decimal, a spread of 50 is 5.0 index points; on spy, quoted to
# two, a spread of 1 is one cent. Comparing the raw integers across
# instruments compares nothing.
#
# It also matters WHEN it is measured. sp500's median spread is 50 points
# across all bars and 20 during the cash session: the wide number is the
# overnight quote, and a strategy that only trades 10:00-15:50 never pays it.
# Taking the all-bar median overstated the cost of the opening range breakout
# by more than a factor of two.


def load_m30(name: str, data_dir: Optional[Path] = None) -> pd.DataFrame:
    """Load one export with a correct `et` column added.

    Returns the frame indexed by position with columns:
        et, open, high, low, close, volume, spread, session

    `volume` prefers real_volume where the broker supplies it and falls back to
    tick_volume, with `volume_kind` recording which - they are different
    measurements and the strategies gate on knowing that.
    """
    stem = DATASETS.get(name, name)
    base = Path(data_dir) if data_dir else DATA_DIR
    path = base / f"{stem}.parquet"
    if not path.exists():
        path = base / f"{stem}.csv"
    if not path.exists():
        raise FileNotFoundError(f"no export for {name!r} in {base}")

    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)

    raw = pd.to_datetime(df["time"], utc=True).dt.tz_localize(None)
    # ambiguous/nonexistent arise only on the two transition hours a year;
    # NaT them and drop rather than guess which side of the fold a bar is on.
    as_broker = raw.dt.tz_localize(BROKER_TZ, ambiguous="NaT", nonexistent="NaT")
    et = as_broker.dt.tz_convert(ET)

    real = df.get("real_volume")
    tick = df.get("tick_volume")
    has_real = real is not None and (real.astype(float) > 0).any()
    volume = (real if has_real else tick).astype(float)

    out = pd.DataFrame({
        "et": et,
        "open": df["open"].astype(float),
        "high": df["high"].astype(float),
        "low": df["low"].astype(float),
        "close": df["close"].astype(float),
        "volume": volume,
        "spread": df.get("spread", pd.Series([0] * len(df))).astype(float),
    })
    out = out[out.et.notna()].reset_index(drop=True)
    out["session"] = out.et.dt.date
    out.attrs["volume_kind"] = "traded" if has_real else "tick_count"
    out.attrs["symbol"] = stem
    return out


def price_points(name: str, data_dir: Optional[Path] = None) -> float:
    """Value of one MT5 `point` for this instrument, from how it is quoted."""
    stem = DATASETS.get(name, name)
    base = Path(data_dir) if data_dir else DATA_DIR
    path = base / f"{stem}.parquet"
    df = pd.read_parquet(path) if path.exists() else pd.read_csv(base / f"{stem}.csv")
    decimals = int(df["close"].astype(str).str.split(".").str[-1].str.len().mode().iloc[0])
    return 10.0 ** -decimals


def spread_price(df: pd.DataFrame, point: float) -> pd.Series:
    """Per-bar spread as a price, ready to subtract from a trade result."""
    return df["spread"].astype(float) * point


def rth(df: pd.DataFrame) -> pd.DataFrame:
    """Regular cash session only: 09:30 up to but not including 16:00 ET."""
    t = df.et.dt.time
    from datetime import time as dtime
    return df[(t >= dtime(9, 30)) & (t < dtime(16, 0))]


def session_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per session with the windows these strategies are defined by.

    Sessions missing either the 09:30 or the 15:30 bar are dropped. That is
    mostly half days, and a strategy whose signal window or exit window does
    not exist has no trade rather than an improvised one.
    """
    from datetime import time as dtime
    t = df.et.dt.time
    first = df[t == dtime(9, 30)].set_index("session")
    last = df[t == dtime(15, 30)].set_index("session")
    opening = df[(t >= dtime(9, 30)) & (t < dtime(10, 0))]
    body = df[(t >= dtime(10, 0)) & (t < dtime(15, 50))]

    or_hi = opening.groupby("session").high.max()
    or_lo = opening.groupby("session").low.min()
    body_hi = body.groupby("session").high.max()
    body_lo = body.groupby("session").low.min()
    body_last = body.groupby("session").close.last()

    prior_close = df.groupby("session").close.last().shift(1)

    tab = pd.DataFrame({
        "first_open": first["open"], "first_close": first["close"],
        "first_high": first["high"], "first_low": first["low"],
        "last_open": last["open"], "last_close": last["close"],
        "or_high": or_hi, "or_low": or_lo,
        "body_high": body_hi, "body_low": body_lo, "body_close": body_last,
        "prior_close": prior_close,
        "first_volume": first["volume"],
    }).dropna(subset=["first_open", "last_open", "or_high", "or_low"])

    tab["gap"] = tab.first_open / tab.prior_close - 1.0
    tab["r_open"] = tab.first_close / tab.first_open - 1.0
    tab["r_close"] = tab.last_close / tab.last_open - 1.0
    return tab
