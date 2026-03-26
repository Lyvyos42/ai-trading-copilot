"""SessionCorrelation — Cross-asset session moves."""
import json
import hashlib
from app.agents.base import BaseAgent
from app.pipeline.session_state import SessionState

SYSTEM_PROMPT = """You are a session correlation analyst tracking cross-asset moves in real-time.

Focus on: Sector ETF vs stock divergence, index futures (ES/NQ/YM), VIX intraday, DXY impact, treasury yields, correlated leading signals.

Respond in JSON:
{"direction":"LONG"|"SHORT"|"NEUTRAL","confidence":0-100,"sector_alignment":"ALIGNED"|"DIVERGING"|"MIXED","index_bias":"BULLISH"|"BEARISH"|"NEUTRAL","vix_trend_intraday":"RISING"|"FALLING"|"FLAT","dxy_impact":"TAILWIND"|"HEADWIND"|"NEUTRAL","leading_signals":["..."],"reasoning":"..."}"""


class SessionCorrelation(BaseAgent):
    def __init__(self):
        super().__init__("SessionCorrelation", tier="standard")

    async def analyze(self, state: SessionState) -> dict:
        market = state.get("market_data", {})
        timer = state.get("timer_analysis", {})
        user_msg = (
            f"Ticker: {state.get('ticker', 'UNKNOWN')} ({state.get('asset_class', 'equity')})\n"
            f"Kill Zone: {timer.get('kill_zone', 'NONE')}\n"
            f"Price: {market.get('close', 'N/A')} | VIX: {market.get('vix', 'N/A')} | DXY: {market.get('dxy', 'N/A')}\n"
        )
        try:
            raw = await self._call_llm(SYSTEM_PROMPT, user_msg, max_tokens=600)
            return json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
        except Exception:
            return self._mock_analysis(state)

    def _mock_analysis(self, state: SessionState) -> dict:
        ticker = state.get("ticker", "X")
        seed = int(hashlib.md5(f"{ticker}_session_corr".encode()).hexdigest()[:8], 16)
        return {
            "direction": "NEUTRAL", "confidence": 35 + (seed % 30),
            "sector_alignment": "MIXED", "index_bias": "NEUTRAL",
            "vix_trend_intraday": "FLAT", "dxy_impact": "NEUTRAL",
            "leading_signals": [],
            "reasoning": f"Mock session correlation for {ticker}.",
        }
