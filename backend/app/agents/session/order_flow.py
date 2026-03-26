"""SessionOrderFlow — Real-time tape reading during active session."""
import json
import hashlib
from app.agents.base import BaseAgent
from app.pipeline.session_state import SessionState

SYSTEM_PROMPT = """You are a session order flow analyst reading the tape in real-time.

Focus on: Bid/ask imbalance, large block trades (>3x avg), aggressor side, dark pool prints, VPIN, absorption patterns.

Respond in JSON:
{"direction":"LONG"|"SHORT"|"NEUTRAL","confidence":0-100,"bid_ask_imbalance":-1.0 to 1.0,"aggressor_side":"BUYERS"|"SELLERS"|"BALANCED","block_trade_bias":"BULLISH"|"BEARISH"|"NEUTRAL","tape_speed":"FAST"|"NORMAL"|"SLOW","absorption_detected":bool,"reasoning":"..."}"""


class SessionOrderFlow(BaseAgent):
    def __init__(self):
        super().__init__("SessionOrderFlow", tier="standard")

    async def analyze(self, state: SessionState) -> dict:
        market = state.get("market_data", {})
        timer = state.get("timer_analysis", {})
        user_msg = (
            f"Ticker: {state.get('ticker', 'UNKNOWN')}\n"
            f"Kill Zone: {timer.get('kill_zone', 'NONE')}\n"
            f"Price: {market.get('close', 'N/A')} | Volume: {market.get('volume', 'N/A')}\n"
            f"Bid: {market.get('bid', 'N/A')} | Ask: {market.get('ask', 'N/A')}\n"
        )
        try:
            raw = await self._call_llm(SYSTEM_PROMPT, user_msg, max_tokens=600)
            return json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
        except Exception:
            return self._mock_analysis(state)

    def _mock_analysis(self, state: SessionState) -> dict:
        ticker = state.get("ticker", "X")
        seed = int(hashlib.md5(f"{ticker}_session_flow".encode()).hexdigest()[:8], 16)
        return {
            "direction": ["LONG", "SHORT", "NEUTRAL"][seed % 3],
            "confidence": 40 + (seed % 35),
            "bid_ask_imbalance": round((seed % 200 - 100) / 100, 2),
            "aggressor_side": "BALANCED", "block_trade_bias": "NEUTRAL",
            "tape_speed": "NORMAL", "absorption_detected": False,
            "reasoning": f"Mock session order flow for {ticker}.",
        }
