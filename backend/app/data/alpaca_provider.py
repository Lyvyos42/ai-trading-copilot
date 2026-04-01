"""
Alpaca paper trading provider.
Enables simulated order execution based on signal recommendations.
Uses paper trading API — no real money involved.
Falls back gracefully if no API key configured.
"""
from typing import Optional

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()

_TIMEOUT = 10.0


def _headers() -> dict:
    return {
        "APCA-API-KEY-ID": settings.alpaca_api_key,
        "APCA-API-SECRET-KEY": settings.alpaca_secret_key,
    }


def is_configured() -> bool:
    return bool(settings.alpaca_api_key and settings.alpaca_secret_key)


async def get_account() -> Optional[dict]:
    """Get paper trading account info (balance, buying power, etc.)."""
    if not is_configured():
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.alpaca_base_url}/v2/account",
                headers=_headers(),
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "equity": float(data.get("equity", 0)),
                "cash": float(data.get("cash", 0)),
                "buying_power": float(data.get("buying_power", 0)),
                "portfolio_value": float(data.get("portfolio_value", 0)),
                "day_trade_count": int(data.get("daytrade_count", 0)),
                "status": data.get("status", "UNKNOWN"),
            }
    except Exception as e:
        log.warning("alpaca_account_failed", error=str(e))
        return None


async def submit_order(
    symbol: str,
    qty: float,
    side: str,  # "buy" or "sell"
    order_type: str = "market",
    time_in_force: str = "day",
) -> Optional[dict]:
    """Submit a paper trading order."""
    if not is_configured():
        return None
    try:
        payload = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
        }
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{settings.alpaca_base_url}/v2/orders",
                headers=_headers(),
                json=payload,
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "order_id": data.get("id"),
                "status": data.get("status"),
                "symbol": data.get("symbol"),
                "qty": data.get("qty"),
                "side": data.get("side"),
                "type": data.get("type"),
                "filled_avg_price": data.get("filled_avg_price"),
                "created_at": data.get("created_at"),
            }
    except Exception as e:
        log.warning("alpaca_order_failed", symbol=symbol, error=str(e))
        return None


async def get_positions() -> Optional[list[dict]]:
    """Get all open paper trading positions."""
    if not is_configured():
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.alpaca_base_url}/v2/positions",
                headers=_headers(),
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            positions = resp.json()
            return [
                {
                    "symbol": p.get("symbol"),
                    "qty": float(p.get("qty", 0)),
                    "side": p.get("side"),
                    "avg_entry_price": float(p.get("avg_entry_price", 0)),
                    "current_price": float(p.get("current_price", 0)),
                    "unrealized_pl": float(p.get("unrealized_pl", 0)),
                    "unrealized_plpc": float(p.get("unrealized_plpc", 0)),
                    "market_value": float(p.get("market_value", 0)),
                }
                for p in positions
            ]
    except Exception as e:
        log.warning("alpaca_positions_failed", error=str(e))
        return None


async def get_order_history(limit: int = 50) -> Optional[list[dict]]:
    """Get recent paper trading order history."""
    if not is_configured():
        return None
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.alpaca_base_url}/v2/orders",
                headers=_headers(),
                params={"status": "all", "limit": limit},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            orders = resp.json()
            return [
                {
                    "order_id": o.get("id"),
                    "symbol": o.get("symbol"),
                    "qty": o.get("qty"),
                    "side": o.get("side"),
                    "type": o.get("type"),
                    "status": o.get("status"),
                    "filled_avg_price": o.get("filled_avg_price"),
                    "created_at": o.get("created_at"),
                    "filled_at": o.get("filled_at"),
                }
                for o in orders
            ]
    except Exception as e:
        log.warning("alpaca_orders_failed", error=str(e))
        return None
