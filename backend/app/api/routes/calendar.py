"""
Economic Calendar — static schedule generator for major macro events.
GET /api/v1/calendar/events?weeks=2
"""
from datetime import date, timedelta
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"])

# ── Known FOMC meeting dates (2025-2026) ──────────────────────────────────────
_FOMC_DATES = [
    # 2025
    "2025-01-29", "2025-03-19", "2025-05-07", "2025-06-18",
    "2025-07-30", "2025-09-17", "2025-11-05", "2025-12-17",
    # 2026
    "2026-01-28", "2026-03-18", "2026-05-06", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16",
]


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Return the nth occurrence of a weekday (0=Mon) in a given month."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    d = first + timedelta(days=offset + (n - 1) * 7)
    return d


def _generate_events(start: date, end: date) -> list[dict]:
    events: list[dict] = []

    # Iterate each month in range
    d = start.replace(day=1)
    while d <= end:
        y, m = d.year, d.month
        last_day_of_month = (date(y, m + 1, 1) if m < 12 else date(y + 1, 1, 1)) - timedelta(days=1)

        # NFP — First Friday of month (released for prior month)
        nfp_date = _nth_weekday(y, m, 4, 1)  # Friday=4
        if start <= nfp_date <= end:
            events.append({
                "date": nfp_date.isoformat(),
                "time": "08:30",
                "name": "Non-Farm Payrolls",
                "country": "US",
                "impact": "HIGH",
                "category": "employment",
                "previous": "256K" if m % 2 == 0 else "227K",
                "forecast": None if nfp_date > date.today() else "200K",
                "actual": None if nfp_date > date.today() else "215K",
            })

        # CPI — ~13th of month
        cpi_target = date(y, m, 13)
        # Shift to nearest weekday
        while cpi_target.weekday() >= 5:
            cpi_target -= timedelta(days=1)
        if start <= cpi_target <= end:
            events.append({
                "date": cpi_target.isoformat(),
                "time": "08:30",
                "name": "CPI (YoY)",
                "country": "US",
                "impact": "HIGH",
                "category": "inflation",
                "previous": "2.9%" if m % 2 == 0 else "3.0%",
                "forecast": None if cpi_target > date.today() else "2.8%",
                "actual": None if cpi_target > date.today() else "2.8%",
            })

        # PPI — ~15th of month
        ppi_target = date(y, m, 15)
        while ppi_target.weekday() >= 5:
            ppi_target -= timedelta(days=1)
        if start <= ppi_target <= end:
            events.append({
                "date": ppi_target.isoformat(),
                "time": "08:30",
                "name": "PPI (MoM)",
                "country": "US",
                "impact": "MEDIUM",
                "category": "inflation",
                "previous": "0.2%",
                "forecast": None if ppi_target > date.today() else "0.3%",
                "actual": None if ppi_target > date.today() else "0.3%",
            })

        # Retail Sales — ~16th of month
        retail_target = date(y, m, 16)
        while retail_target.weekday() >= 5:
            retail_target -= timedelta(days=1)
        if start <= retail_target <= end:
            events.append({
                "date": retail_target.isoformat(),
                "time": "08:30",
                "name": "Retail Sales (MoM)",
                "country": "US",
                "impact": "MEDIUM",
                "category": "consumer",
                "previous": "0.4%",
                "forecast": None if retail_target > date.today() else "0.5%",
                "actual": None if retail_target > date.today() else "0.4%",
            })

        # PMI — First business day of month
        pmi_target = date(y, m, 1)
        while pmi_target.weekday() >= 5:
            pmi_target += timedelta(days=1)
        if start <= pmi_target <= end:
            events.append({
                "date": pmi_target.isoformat(),
                "time": "10:00",
                "name": "ISM Manufacturing PMI",
                "country": "US",
                "impact": "MEDIUM",
                "category": "manufacturing",
                "previous": "50.9" if m % 2 == 0 else "49.3",
                "forecast": None if pmi_target > date.today() else "50.5",
                "actual": None if pmi_target > date.today() else "50.2",
            })

        # GDP — End of month (quarterly: Jan, Apr, Jul, Oct for advance estimate)
        if m in (1, 4, 7, 10):
            gdp_target = date(y, m, 28)
            while gdp_target.weekday() >= 5:
                gdp_target -= timedelta(days=1)
            if start <= gdp_target <= end:
                events.append({
                    "date": gdp_target.isoformat(),
                    "time": "08:30",
                    "name": "GDP (QoQ Advance)",
                    "country": "US",
                    "impact": "HIGH",
                    "category": "growth",
                    "previous": "2.3%",
                    "forecast": None if gdp_target > date.today() else "2.1%",
                    "actual": None if gdp_target > date.today() else "2.0%",
                })

        # PCE — Last Friday of month
        pce_target = last_day_of_month
        while pce_target.weekday() != 4:
            pce_target -= timedelta(days=1)
        if start <= pce_target <= end:
            events.append({
                "date": pce_target.isoformat(),
                "time": "08:30",
                "name": "Core PCE (YoY)",
                "country": "US",
                "impact": "HIGH",
                "category": "inflation",
                "previous": "2.8%",
                "forecast": None if pce_target > date.today() else "2.7%",
                "actual": None if pce_target > date.today() else "2.7%",
            })

        # Advance to next month
        if m == 12:
            d = date(y + 1, 1, 1)
        else:
            d = date(y, m + 1, 1)

    # FOMC meeting dates
    for fd in _FOMC_DATES:
        fomc_date = date.fromisoformat(fd)
        if start <= fomc_date <= end:
            events.append({
                "date": fomc_date.isoformat(),
                "time": "14:00",
                "name": "FOMC Rate Decision",
                "country": "US",
                "impact": "HIGH",
                "category": "central_bank",
                "previous": "4.50%",
                "forecast": None,
                "actual": None if fomc_date > date.today() else "4.50%",
            })

    # Jobless Claims — every Thursday
    thursday = start
    while thursday.weekday() != 3:
        thursday += timedelta(days=1)
    while thursday <= end:
        events.append({
            "date": thursday.isoformat(),
            "time": "08:30",
            "name": "Initial Jobless Claims",
            "country": "US",
            "impact": "LOW",
            "category": "employment",
            "previous": "223K",
            "forecast": None if thursday > date.today() else "220K",
            "actual": None if thursday > date.today() else "218K",
        })
        thursday += timedelta(days=7)

    events.sort(key=lambda e: (e["date"], e["time"]))
    return events


@router.get("/events")
async def get_calendar_events(
    weeks: int = Query(2, ge=1, le=8, description="Weeks to look ahead"),
):
    today = date.today()
    start = today - timedelta(days=7)  # Include past week for context
    end = today + timedelta(weeks=weeks)
    events = _generate_events(start, end)
    return {"events": events, "start": start.isoformat(), "end": end.isoformat()}
