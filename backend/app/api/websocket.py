"""
WS /ws/v1/signals/stream — real-time signal stream via WebSocket.

Clients connect and optionally subscribe to specific tickers.
The server periodically emits live signals for subscribed tickers.
"""
import asyncio
import json
import random
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.pipeline.graph import run_pipeline

router = APIRouter()

# Connected clients: {websocket: set_of_subscribed_tickers}
_clients: dict[WebSocket, set[str]] = {}


@router.websocket("/ws/v1/signals/stream")
async def signal_stream(ws: WebSocket):
    await ws.accept()
    _clients[ws] = set()

    try:
        # Start background signal emitter for this connection
        emit_task = asyncio.create_task(_emit_signals(ws))

        async for raw_msg in ws.iter_text():
            try:
                msg = json.loads(raw_msg)
                action = msg.get("action")
                tickers = msg.get("tickers", [])

                if action == "subscribe" and tickers:
                    _clients[ws].update(t.upper() for t in tickers)
                    await ws.send_json({"type": "subscribed", "tickers": list(_clients[ws])})

                elif action == "unsubscribe" and tickers:
                    for t in tickers:
                        _clients[ws].discard(t.upper())
                    await ws.send_json({"type": "unsubscribed", "tickers": list(_clients[ws])})

                elif action == "ping":
                    await ws.send_json({"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})

            except (json.JSONDecodeError, KeyError):
                await ws.send_json({"type": "error", "detail": "Invalid message format"})

    except WebSocketDisconnect:
        pass
    finally:
        _clients.pop(ws, None)
        emit_task.cancel()


async def _emit_signals(ws: WebSocket):
    """Every 15 seconds, run the pipeline on subscribed tickers and push signals."""
    DEFAULT_TICKERS = ["AAPL", "TSLA", "NVDA", "SPY"]
    while True:
        await asyncio.sleep(15)
        tickers = list(_clients.get(ws, set())) or DEFAULT_TICKERS[:1]

        for ticker in tickers:
            try:
                state = await run_pipeline(ticker=ticker)
                final = state.get("final_signal", {})
                if final:
                    await ws.send_json({
                        "type": "signal",
                        "ticker": ticker,
                        "direction": final.get("direction"),
                        "entry_price": final.get("entry_price"),
                        "stop_loss": final.get("stop_loss"),
                        "take_profit_1": final.get("take_profit_1"),
                        "confidence_score": final.get("confidence_score"),
                        "strategy_sources": final.get("strategy_sources", []),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
            except Exception as e:
                await ws.send_json({"type": "error", "ticker": ticker, "detail": str(e)})


async def broadcast_signal(ticker: str, signal: dict):
    """Broadcast a signal to all clients subscribed to that ticker."""
    dead = []
    for ws, subs in _clients.items():
        if ticker in subs or not subs:
            try:
                await ws.send_json({"type": "signal", **signal})
            except Exception:
                dead.append(ws)
    for ws in dead:
        _clients.pop(ws, None)
