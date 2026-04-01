"""
QuiverQuant alternative data provider.
Congressional trades, insider transactions, lobbying activity.
Gated to Pro/Enterprise tiers. Falls back gracefully.
"""
from typing import Optional

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()

_BASE = "https://api.quiverquant.com/beta"
_TIMEOUT = 10.0


def _headers() -> dict:
    return {"Authorization": f"Bearer {settings.quiver_api_key}"}


def is_configured() -> bool:
    return bool(settings.quiver_api_key)


async def get_congressional_trades(ticker: str, limit: int = 10) -> Optional[list[dict]]:
    """Recent congressional trades for a ticker."""
    if not is_configured():
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_BASE}/historical/congresstrading/{ticker}",
                headers=_headers(),
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            trades = resp.json()[:limit]
            return [
                {
                    "representative": t.get("Representative", ""),
                    "transaction": t.get("Transaction", ""),
                    "amount": t.get("Amount", ""),
                    "date": t.get("TransactionDate", ""),
                    "party": t.get("Party", ""),
                }
                for t in trades
            ]
    except Exception as e:
        log.warning("quiver_congress_failed", ticker=ticker, error=str(e))
        return None


async def get_insider_trades(ticker: str, limit: int = 10) -> Optional[list[dict]]:
    """Recent SEC insider transactions."""
    if not is_configured():
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_BASE}/historical/insiders/{ticker}",
                headers=_headers(),
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            trades = resp.json()[:limit]
            return [
                {
                    "insider": t.get("Name", ""),
                    "title": t.get("Title", ""),
                    "transaction_type": t.get("TransactionType", ""),
                    "shares": t.get("Shares", 0),
                    "price": t.get("Price", 0),
                    "date": t.get("Date", ""),
                }
                for t in trades
            ]
    except Exception as e:
        log.warning("quiver_insider_failed", ticker=ticker, error=str(e))
        return None


async def get_lobbying(ticker: str, limit: int = 5) -> Optional[list[dict]]:
    """Recent lobbying activity."""
    if not is_configured():
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{_BASE}/historical/lobbying/{ticker}",
                headers=_headers(),
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()[:limit]
            return [
                {
                    "client": d.get("Client", ""),
                    "amount": d.get("Amount", 0),
                    "issue": d.get("Issue", ""),
                    "date": d.get("Date", ""),
                }
                for d in data
            ]
    except Exception as e:
        log.warning("quiver_lobbying_failed", ticker=ticker, error=str(e))
        return None


async def get_alternative_data(ticker: str) -> dict:
    """Fetch all available alternative data for a ticker. Returns empty dict on failure."""
    if not is_configured():
        return {}

    import asyncio
    congress, insiders, lobbying = await asyncio.gather(
        get_congressional_trades(ticker),
        get_insider_trades(ticker),
        get_lobbying(ticker),
        return_exceptions=True,
    )

    result = {}
    if isinstance(congress, list) and congress:
        result["congressional_trades"] = congress
    if isinstance(insiders, list) and insiders:
        result["insider_trades"] = insiders
    if isinstance(lobbying, list) and lobbying:
        result["lobbying"] = lobbying

    log.info("quiver_data", ticker=ticker, sections=len(result))
    return result


def format_for_agent(alt_data: dict) -> str:
    """Format alternative data as text block for agent prompts."""
    if not alt_data:
        return ""

    lines = ["=== ALTERNATIVE DATA (QuiverQuant) ==="]

    if "congressional_trades" in alt_data:
        lines.append("\nCONGRESSIONAL TRADING:")
        for t in alt_data["congressional_trades"][:5]:
            lines.append(f"  {t['date']}: {t['representative']} ({t['party']}) — {t['transaction']} {t['amount']}")

    if "insider_trades" in alt_data:
        lines.append("\nINSIDER TRANSACTIONS:")
        for t in alt_data["insider_trades"][:5]:
            lines.append(f"  {t['date']}: {t['insider']} ({t['title']}) — {t['transaction_type']} {t['shares']} shares @ ${t['price']}")

    if "lobbying" in alt_data:
        lines.append("\nLOBBYING ACTIVITY:")
        for d in alt_data["lobbying"][:3]:
            lines.append(f"  {d['date']}: {d['client']} — ${d['amount']:,.0f} ({d['issue']})")

    lines.append("")
    return "\n".join(lines)
