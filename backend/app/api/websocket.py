"""
WS /ws/v1/signals/stream — real-time signal + alert stream via WebSocket.

Clients connect with an optional ?token=<jwt> query param.
- All clients: can subscribe/unsubscribe to tickers, receive pings.
- Pro/Enterprise/Admin clients: automatically receive scanner alerts
  broadcast to their user_id.
"""
import asyncio
import json
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional

router = APIRouter()

PREMIUM_TIERS = {"pro", "enterprise", "admin"}

# Connected clients: websocket → {tickers: set, user_id: str|None, tier: str}
_clients: dict[WebSocket, dict] = {}


def _decode_user(token: str | None) -> tuple[str | None, str]:
    """Extract (user_id, tier) from a JWT token. Returns (None, 'free') on failure."""
    if not token:
        return None, "free"
    try:
        from jose import jwt
        from app.config import settings
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload.get("sub"), payload.get("tier", "free") or "free"
    except Exception:
        # Token failed verification — treat as unauthenticated free user.
        # NEVER use get_unverified_claims: an attacker can forge any tier/user_id.
        return None, "free"


@router.websocket("/ws/v1/signals/stream")
async def signal_stream(ws: WebSocket, token: Optional[str] = Query(default=None)):
    await ws.accept()

    user_id, tier = _decode_user(token)
    _clients[ws] = {"tickers": set(), "user_id": user_id, "tier": tier}

    # Inform client of their tier on connect
    await ws.send_json({
        "type":    "connected",
        "user_id": user_id,
        "tier":    tier,
        "premium": tier in PREMIUM_TIERS,
    })

    try:
        async for raw_msg in ws.iter_text():
            try:
                msg    = json.loads(raw_msg)
                action = msg.get("action")
                tickers = msg.get("tickers", [])

                if action == "subscribe" and tickers:
                    _clients[ws]["tickers"].update(t.upper() for t in tickers)
                    await ws.send_json({"type": "subscribed", "tickers": list(_clients[ws]["tickers"])})

                elif action == "unsubscribe" and tickers:
                    for t in tickers:
                        _clients[ws]["tickers"].discard(t.upper())
                    await ws.send_json({"type": "unsubscribed", "tickers": list(_clients[ws]["tickers"])})

                elif action == "ping":
                    await ws.send_json({"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat() + "Z"})

            except (json.JSONDecodeError, KeyError):
                await ws.send_json({"type": "error", "detail": "Invalid message format"})

    except WebSocketDisconnect:
        pass
    finally:
        _clients.pop(ws, None)


async def broadcast_signal(ticker: str, signal: dict):
    """Broadcast a signal to all clients subscribed to that ticker."""
    dead = []
    for ws, meta in _clients.items():
        if ticker.upper() in meta["tickers"] or not meta["tickers"]:
            try:
                await ws.send_json({"type": "signal", **signal})
            except Exception:
                dead.append(ws)
    for ws in dead:
        _clients.pop(ws, None)


async def broadcast_alert(user_id: str, alert: dict):
    """
    Push a scanner alert to the specific premium user's WebSocket connection.
    Only sends to connections that match user_id and have a premium tier.
    """
    dead = []
    for ws, meta in _clients.items():
        if meta.get("user_id") == user_id and meta.get("tier") in PREMIUM_TIERS:
            try:
                await ws.send_json({"type": "alert", **alert})
            except Exception:
                dead.append(ws)
    for ws in dead:
        _clients.pop(ws, None)
