"""
FRED (Federal Reserve Economic Data) provider.
Fetches key macro indicators: GDP, CPI, Fed Funds Rate, Unemployment, Yield Curve spread.
Free API — requires key from https://fred.stlouisfed.org/docs/api/fred/

All functions return None on failure so callers can gracefully fall back.
"""
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()

_BASE = "https://api.stlouisfed.org/fred"
_TIMEOUT = 10.0

# Key economic series IDs
SERIES = {
    "gdp_growth":      "A191RL1Q225SBEA",  # Real GDP growth (quarterly, % change)
    "cpi_yoy":         "CPIAUCSL",          # CPI-U (monthly, use for YoY calc)
    "fed_funds":       "FEDFUNDS",          # Effective Federal Funds Rate
    "unemployment":    "UNRATE",            # Unemployment Rate
    "yield_10y":       "DGS10",             # 10-Year Treasury Yield
    "yield_2y":        "DGS2",              # 2-Year Treasury Yield
    "initial_claims":  "ICSA",              # Initial Jobless Claims (weekly)
    "pce_inflation":   "PCEPI",             # PCE Price Index (Fed's preferred)
    "ism_manufacturing": "MANEMP",          # Manufacturing Employment
}


async def _fetch_series(
    series_id: str,
    limit: int = 12,
    client: httpx.AsyncClient | None = None,
) -> Optional[list[dict]]:
    """Fetch recent observations for a FRED series. Returns list of {date, value} or None."""
    key = settings.fred_api_key
    if not key:
        return None

    url = f"{_BASE}/series/observations"
    params = {
        "series_id": series_id,
        "api_key": key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }

    try:
        if client:
            resp = await client.get(url, params=params, timeout=_TIMEOUT)
        else:
            async with httpx.AsyncClient() as c:
                resp = await c.get(url, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        observations = data.get("observations", [])
        # Filter out missing values (FRED uses "." for missing)
        return [
            {"date": o["date"], "value": float(o["value"])}
            for o in observations
            if o.get("value") and o["value"] != "."
        ]
    except Exception as e:
        log.warning("fred_fetch_failed", series_id=series_id, error=str(e))
        return None


async def get_macro_snapshot() -> dict:
    """
    Fetch all key macro indicators in parallel.
    Returns a dict with indicator names as keys. Missing indicators are omitted.
    Safe to call even without API key — returns empty dict.
    """
    if not settings.fred_api_key:
        return {}

    async with httpx.AsyncClient() as client:
        tasks = {
            name: _fetch_series(sid, limit=6, client=client)
            for name, sid in SERIES.items()
        }
        keys = list(tasks.keys())
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    snapshot = {}
    for name, result in zip(keys, results):
        if isinstance(result, Exception) or result is None:
            continue
        if result:
            latest = result[0]
            snapshot[name] = {
                "value": latest["value"],
                "date": latest["date"],
                "trend": _compute_trend(result),
            }

    # Compute yield curve spread if both yields available
    if "yield_10y" in snapshot and "yield_2y" in snapshot:
        spread = snapshot["yield_10y"]["value"] - snapshot["yield_2y"]["value"]
        snapshot["yield_curve_spread"] = {
            "value": round(spread, 3),
            "date": snapshot["yield_10y"]["date"],
            "trend": "INVERTED" if spread < 0 else "NORMAL" if spread > 0.5 else "FLAT",
        }

    log.info("fred_snapshot", indicators=len(snapshot))
    return snapshot


def _compute_trend(observations: list[dict]) -> str:
    """Determine trend from recent observations (newest first)."""
    if len(observations) < 2:
        return "STABLE"
    newest = observations[0]["value"]
    oldest = observations[-1]["value"]
    if oldest == 0:
        return "STABLE"
    pct_change = (newest - oldest) / abs(oldest) * 100
    if pct_change > 2:
        return "RISING"
    elif pct_change < -2:
        return "FALLING"
    return "STABLE"


def format_for_agent(snapshot: dict) -> str:
    """Format FRED snapshot as a text block for injection into agent prompts."""
    if not snapshot:
        return ""

    lines = ["=== LIVE ECONOMIC DATA (FRED) ==="]

    labels = {
        "gdp_growth": "Real GDP Growth (Q/Q %)",
        "cpi_yoy": "CPI Index",
        "fed_funds": "Fed Funds Rate",
        "unemployment": "Unemployment Rate",
        "yield_10y": "10Y Treasury Yield",
        "yield_2y": "2Y Treasury Yield",
        "yield_curve_spread": "Yield Curve Spread (10Y-2Y)",
        "initial_claims": "Initial Jobless Claims",
        "pce_inflation": "PCE Price Index",
        "ism_manufacturing": "Manufacturing Employment",
    }

    for key, label in labels.items():
        if key in snapshot:
            d = snapshot[key]
            val = d["value"]
            trend = d["trend"]
            date = d["date"]
            # Format percentage-type indicators
            if key in ("gdp_growth", "fed_funds", "unemployment", "yield_10y", "yield_2y"):
                lines.append(f"  {label}: {val:.2f}% ({trend}) [as of {date}]")
            elif key == "yield_curve_spread":
                lines.append(f"  {label}: {val:+.3f}% ({trend}) [as of {date}]")
            elif key == "initial_claims":
                lines.append(f"  {label}: {val:,.0f} ({trend}) [as of {date}]")
            else:
                lines.append(f"  {label}: {val:.1f} ({trend}) [as of {date}]")

    lines.append("")
    return "\n".join(lines)
