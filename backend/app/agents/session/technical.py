"""SessionTechnical — Intraday levels, VWAP, ORB, momentum on 1-15min timeframes."""
import json
import hashlib
from app.agents.base import BaseAgent
from app.pipeline.session_state import SessionState

SYSTEM_PROMPT = """You are a session-focused technical analyst for intraday trading.
Analyze 1-minute to 15-minute charts during active trading sessions.

Focus on: VWAP position, Opening Range Breakout status, intraday S/R, momentum (RSI/MACD on 5min), volume profile, micro market structure.

Respond in JSON:
{"direction":"LONG"|"SHORT"|"NEUTRAL","confidence":0-100,"vwap_position":"ABOVE"|"BELOW"|"AT","orb_status":"BREAKOUT_LONG"|"BREAKOUT_SHORT"|"INSIDE"|"NOT_SET","intraday_trend":"UP"|"DOWN"|"RANGE","key_levels":{"support":float,"resistance":float},"momentum_score":-100 to 100,"reasoning":"..."}"""


class SessionTechnical(BaseAgent):
    def __init__(self):
        super().__init__("SessionTechnical", tier="standard")

    async def analyze(self, state: SessionState) -> dict:
        market = state.get("market_data", {})
        timer = state.get("timer_analysis", {})
        user_msg = (
            f"Ticker: {state.get('ticker', 'UNKNOWN')}\n"
            f"Kill Zone: {timer.get('kill_zone', 'NONE')} ({timer.get('kill_zone_minutes_remaining', '?')}min)\n"
            f"Price: {market.get('close', 'N/A')} | VWAP: {market.get('vwap', 'N/A')}\n"
            f"High: {market.get('high', 'N/A')} | Low: {market.get('low', 'N/A')}\n"
            f"Volume: {market.get('volume', 'N/A')} | RSI: {market.get('rsi_14', 'N/A')} | ATR: {market.get('atr', 'N/A')}\n"
        )
        try:
            raw = await self._call_llm(SYSTEM_PROMPT, user_msg, max_tokens=800)
            return json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
        except Exception:
            return self._mock_analysis(state)

    def _mock_analysis(self, state: SessionState) -> dict:
        ticker = state.get("ticker", "X")
        seed = int(hashlib.md5(f"{ticker}_session_tech".encode()).hexdigest()[:8], 16)
        price = state.get("market_data", {}).get("close", 100)
        return {
            "direction": ["LONG", "SHORT", "NEUTRAL"][seed % 3],
            "confidence": 45 + (seed % 40),
            "vwap_position": "ABOVE" if seed % 2 == 0 else "BELOW",
            "orb_status": "INSIDE",
            "intraday_trend": "RANGE",
            "key_levels": {"support": round(price * 0.995, 2), "resistance": round(price * 1.005, 2)},
            "momentum_score": (seed % 60) - 30,
            "reasoning": f"Mock intraday analysis for {ticker}.",
        }
