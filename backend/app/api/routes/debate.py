"""
POST /api/v1/debate/trigger — force bull/bear debate on a specific asset
"""
from fastapi import APIRouter
from pydantic import BaseModel
from app.pipeline.graph import run_pipeline

router = APIRouter(prefix="/api/v1/debate", tags=["debate"])


class DebateRequest(BaseModel):
    ticker: str
    asset_class: str = "stocks"


@router.post("/trigger")
async def trigger_debate(body: DebateRequest):
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
