"""
POST /api/v1/debate/trigger — force bull/bear debate on a specific asset
Requires a valid Bearer token. IP rate-limited to 5 requests/minute.
"""
import time
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from app.auth.jwt import get_current_user
from app.pipeline.graph import run_pipeline

router = APIRouter(prefix="/api/v1/debate", tags=["debate"])

# ── IP rate limit: 5 debate triggers per minute per IP ──────────────────────
_rate_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT = 5
_RATE_WINDOW = 60  # seconds


def _check_ip_rate_limit(ip: str) -> None:
    now = time.time()
    window_start = now - _RATE_WINDOW
    _rate_store[ip] = [t for t in _rate_store[ip] if t > window_start]
    if len(_rate_store[ip]) >= _RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Max {_RATE_LIMIT} debate triggers per minute per IP.",
            headers={"Retry-After": "60"},
        )
    _rate_store[ip].append(now)


class DebateRequest(BaseModel):
    ticker: str
    asset_class: str = "stocks"


@router.post("/trigger")
async def trigger_debate(
    request: Request,
    body: DebateRequest,
    _user: dict = Depends(get_current_user),
):
    client_ip = (
        request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
        .split(",")[0]
        .strip()
    )
    _check_ip_rate_limit(client_ip)

    ticker = body.ticker.upper().strip()
    state = await run_pipeline(ticker=ticker, asset_class=body.asset_class)

    return {
        "ticker": ticker,
        "asset_class": body.asset_class,
        "bull_case": state.get("bull_case", ""),
        "bear_case": state.get("bear_case", ""),
        "analyst_votes": {
            "fundamental": state.get("fundamental_analysis", {}).get("direction"),
            "technical": state.get("technical_analysis", {}).get("direction"),
            "sentiment": state.get("sentiment_analysis", {}).get("direction"),
            "macro": state.get("macro_analysis", {}).get("direction"),
        },
        "final_direction": state.get("final_signal", {}).get("direction"),
        "confidence_score": state.get("final_signal", {}).get("confidence_score"),
        "reasoning_chain": state.get("reasoning_chain", []),
    }
