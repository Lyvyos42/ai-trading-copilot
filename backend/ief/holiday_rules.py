"""
Exchange holiday schedule generator — NYSE / CME equity index
=============================================================
Generates the holiday and early-close schedule from PUBLISHED RULES rather than
from a hand-copied table, then proves itself against the historical record in
app/data/nyse_holidays.csv before any generated date is trusted forward.

WHY RULES AND NOT A TRANSCRIBED PDF:
The strategy's formation, entry and exit dates are derived from the session grid.
A single wrong holiday shifts the 5th-to-last session of that month and changes
the signal. A rule engine that reproduces 30+ years of known holidays is
auditable; a transcribed table is one typo away from a silent signal error.

STATUS OF GENERATED DATES: RULE-DERIVED, NOT OPERATOR-VERIFIED.
Dates from 2027 onward have no published CME calendar on file to check against.
They MUST be reconciled against CME Group's published holiday calendar before
go-live. validate_against() proves the engine on history; it cannot prove the
future.

RULES IMPLEMENTED (NYSE / CME equity index full holidays):
  New Year's Day        Jan 1, observed
  MLK Day               3rd Monday in January        (from 1998)
  Washington's Birthday 3rd Monday in February
  Good Friday           Friday before Easter Sunday  (Gregorian computus)
  Memorial Day          last Monday in May
  Juneteenth            Jun 19, observed             (from 2022)
  Independence Day      Jul 4, observed
  Labor Day             1st Monday in September
  Thanksgiving          4th Thursday in November
  Christmas Day         Dec 25, observed

OBSERVANCE: a holiday falling on Saturday is observed the preceding Friday; on
Sunday, the following Monday. Exception: New Year's Day falling on Saturday is
NOT observed on the preceding Friday (that Friday is in the prior year and the
exchange stays open).

EARLY CLOSES (13:00 ET): July 3 when Independence Day is a weekday, the Friday
after Thanksgiving, and December 24 when Christmas is a weekday. Early closes
are VALID SESSIONS for grid purposes but their settlement time moves, which
matters for the exit leg.
"""
from __future__ import annotations

import csv
import datetime as dt

FULL_HOLIDAY = "holiday"
EARLY_CLOSE = "early_close"

MLK_FROM = 1998
JUNETEENTH_FROM = 2022


def easter_sunday(year: int) -> dt.date:
    """Anonymous Gregorian computus."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    lam = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * lam) // 451
    month, day = divmod(h + lam - 7 * m + 114, 31)
    return dt.date(year, month, day + 1)


def nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(weekday - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def last_weekday(year: int, month: int, weekday: int) -> dt.date:
    nxt = dt.date(year + (month == 12), (month % 12) + 1, 1)
    d = nxt - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() - weekday) % 7)


def observed(d: dt.date, is_new_year: bool = False) -> dt.date | None:
    if d.weekday() == 5:                      # Saturday
        if is_new_year:
            return None                       # not observed; prior-year Friday
        return d - dt.timedelta(days=1)
    if d.weekday() == 6:                      # Sunday
        return d + dt.timedelta(days=1)
    return d


def holidays_for_year(year: int) -> list[dt.date]:
    out: list[dt.date | None] = [
        observed(dt.date(year, 1, 1), is_new_year=True),
        nth_weekday(year, 2, 0, 3),                       # Washington's Birthday
        easter_sunday(year) - dt.timedelta(days=2),       # Good Friday
        last_weekday(year, 5, 0),                         # Memorial Day
        observed(dt.date(year, 7, 4)),
        nth_weekday(year, 9, 0, 1),                       # Labor Day
        nth_weekday(year, 11, 3, 4),                      # Thanksgiving
        observed(dt.date(year, 12, 25)),
    ]
    if year >= MLK_FROM:
        out.append(nth_weekday(year, 1, 0, 3))
    if year >= JUNETEENTH_FROM:
        out.append(observed(dt.date(year, 6, 19)))
    return sorted(d for d in out if d is not None)


def early_closes_for_year(year: int) -> list[dt.date]:
    out = []
    jul4 = dt.date(year, 7, 4)
    if jul4.weekday() < 5:
        jul3 = dt.date(year, 7, 3)
        if jul3.weekday() < 5:
            out.append(jul3)
    out.append(nth_weekday(year, 11, 3, 4) + dt.timedelta(days=1))   # day after Thanksgiving
    dec25 = dt.date(year, 12, 25)
    if dec25.weekday() < 5:
        dec24 = dt.date(year, 12, 24)
        if dec24.weekday() < 5:
            out.append(dec24)
    return sorted(out)


def generate(start_year: int, end_year: int) -> list[tuple[str, str]]:
    """[(iso_date, kind)] sorted, kind in {holiday, early_close}."""
    rows: list[tuple[str, str]] = []
    for y in range(start_year, end_year + 1):
        rows += [(d.isoformat(), FULL_HOLIDAY) for d in holidays_for_year(y)]
        rows += [(d.isoformat(), EARLY_CLOSE) for d in early_closes_for_year(y)]
    return sorted(set(rows))


def validate_against(reference_csv: str, start_year: int, end_year: int) -> dict:
    """Prove the rule engine on the historical record before trusting it forward."""
    ref: set[str] = set()
    with open(reference_csv, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            h = (row.get("holiday_date") or "").strip()
            if h and start_year <= int(h[:4]) <= end_year:
                ref.add(h)
    gen = {d for d, k in generate(start_year, end_year)
           if k == FULL_HOLIDAY and start_year <= int(d[:4]) <= end_year}
    return {"reference": len(ref), "generated": len(gen),
            "matched": len(ref & gen),
            "missing_from_generated": sorted(ref - gen),
            "extra_in_generated": sorted(gen - ref)}


def write_csv(path: str, start_year: int, end_year: int) -> int:
    rows = generate(start_year, end_year)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "kind", "source"])
        for d, k in rows:
            w.writerow([d, k, "RULE_DERIVED"])
    return len(rows)
