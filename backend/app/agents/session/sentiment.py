"""SessionSentiment — Live news flow during active trading session."""
import json
import hashlib
from app.agents.base import BaseAgent
from app.pipeline.session_state import SessionState

SYSTEM_PROMPT = """You are a session sentiment analyst monitoring live news for intraday impact.

Focus on: Breaking headlines (last 30min), social sentiment shifts, options flow anomalies, sector-wide moves, analyst actions today.

Rate urgency: FLASH (trade now), DEVELOPING (watch), BACKGROUND (no immediate impact).

Respond in JSON:
{"direction":"LONG"|"SHORT"|"NEUTRAL","confidence":0-100,"urgency":"FLASH"|"DEVELOPING"|"BACKGROUND","headline_sentiment":-1.0 to 1.0,"key_headlines":["..."],"options_flow":"BULLISH"|"BEARISH"|"NEUTRAL"|"UNKNOWN","reasoning":"..."}"""


class SessionSentiment(BaseAgent):
    def __init__(self):
        super().__init__("SessionSentiment", tier="standard")

    async def analyze(self, state: SessionState) -> dict:
        news = state.get("news_context", {})
        timer = state.get("timer_analysis", {})
        headlines = news.get("ticker_headlines", [])[:10]
        market_headlines = news.get("market_headlines", [])[:5]
        user_msg = (
            f"Ticker: {state.get('ticker', 'UNKNOWN')}\n"
            f"Session Phase: {timer.get('market_phase', 'UNKNOWN')}\n"
            f"\nTicker headlines:\n" + "\n".join(f"- {h}" for h in headlines) + "\n"
            f"\nMarket headlines:\n" + "\n".join(f"- {h}" for h in market_headlines) + "\n"
            f"\nSentiment stats: {news.get('sentiment_stats', {})}\n"
        )
        try:
            raw = await self._call_llm(SYSTEM_PROMPT, user_msg, max_tokens=600)
            return json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
        except Exception:
            return self._mock_analysis(state)

    def _mock_analysis(self, state: SessionState) -> dict:
        ticker = state.get("ticker", "X")
        seed = int(hashlib.md5(f"{ticker}_session_sent".encode()).hexdigest()[:8], 16)
        return {
            "direction": "NEUTRAL", "confidence": 40 + (seed % 25),
            "urgency": "BACKGROUND", "headline_sentiment": round((seed % 200 - 100) / 100, 2),
            "key_headlines": [], "options_flow": "UNKNOWN",
            "reasoning": f"Mock session sentiment for {ticker}.",
        }
