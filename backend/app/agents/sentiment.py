import json
import random
from app.agents.base import BaseAgent
from app.pipeline.state import TradingState


SYSTEM_PROMPT = """You are an expert sentiment analyst applying NLP-based trading strategies:
- Strategy 18.3: Naive Bayes sentiment classification (adapted to transformer-based)
- Extended to news, earnings call transcripts, and social media signals

Given ticker and simulated news/sentiment data, assess market sentiment.
Respond ONLY with a valid JSON object:
{
  "direction": "LONG" | "SHORT" | "NEUTRAL",
  "confidence": <float 0-100>,
  "news_sentiment": <float -1 to 1>,
  "social_sentiment": <float -1 to 1>,
  "fear_greed_score": <float 0-100>,
  "key_themes": [<string>, ...],
  "analyst_upgrades": <int>,
  "analyst_downgrades": <int>,
  "reasoning": "<string>"
}"""

MOCK_HEADLINES = {
    "positive": [
        "beats earnings expectations",
        "raises full-year guidance",
        "announces share buyback program",
        "reports record revenue",
        "secures major partnership deal",
        "expands into new markets",
    ],
    "negative": [
        "misses earnings estimates",
        "cuts revenue forecast",
        "faces regulatory scrutiny",
        "reports increased competition",
        "announces layoffs",
        "CEO resignation announced",
    ],
    "neutral": [
        "scheduled to report earnings next week",
        "announces product launch date",
        "files quarterly report with SEC",
        "holds annual shareholder meeting",
    ],
}


class SentimentAnalyst(BaseAgent):
    def __init__(self):
        super().__init__("SentimentAnalyst", model="claude-sonnet-4-6")

    async def analyze(self, state: TradingState) -> dict:
        ticker = state.get("ticker", "UNKNOWN")
        market_data = state.get("market_data", {})

        rng = random.Random(sum(ord(c) for c in ticker) + 42)
        sentiment_bias = rng.uniform(-0.4, 0.4)

        # Simulate news headlines
        headlines = []
        if sentiment_bias > 0.1:
            headlines = [f"{ticker} {h}" for h in rng.sample(MOCK_HEADLINES["positive"], 3)]
        elif sentiment_bias < -0.1:
            headlines = [f"{ticker} {h}" for h in rng.sample(MOCK_HEADLINES["negative"], 3)]
        else:
            headlines = [f"{ticker} {h}" for h in rng.sample(MOCK_HEADLINES["neutral"], 2)]

        user_msg = f"""Analyze sentiment for {ticker}.
Recent price change: {market_data.get('price_change_pct', 'N/A')}%
Volume vs 30d avg: {market_data.get('volume_ratio', 'N/A')}x

Simulated recent headlines:
{chr(10).join(f'- {h}' for h in headlines)}

Simulated social media buzz score: {rng.randint(20, 90)}/100
Strategy 18.3: Classify overall sentiment. Output JSON only."""

        raw = self._call_claude(SYSTEM_PROMPT, user_msg)
        if raw:
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass

        return self._mock_analysis(ticker, sentiment_bias, headlines, rng)

    def _mock_analysis(self, ticker: str, bias: float, headlines: list, rng: random.Random) -> dict:
        news_sent = bias + rng.uniform(-0.15, 0.15)
        social_sent = bias * 0.7 + rng.uniform(-0.2, 0.2)
        fear_greed = min(90, max(10, 50 + bias * 40 + rng.uniform(-10, 10)))

        upgrades = rng.randint(0, 3) if bias > 0 else 0
        downgrades = rng.randint(0, 3) if bias < 0 else 0

        direction = "LONG" if news_sent > 0.1 else ("SHORT" if news_sent < -0.1 else "NEUTRAL")
        confidence = min(85, max(30, 50 + abs(news_sent) * 35))

        themes = []
        if bias > 0.1:
            themes = ["earnings_beat", "growth_momentum", "bullish_analyst_coverage"]
        elif bias < -0.1:
            themes = ["earnings_miss", "guidance_cut", "bearish_sentiment"]
        else:
            themes = ["mixed_signals", "event_driven", "low_conviction"]

        return {
            "direction": direction,
            "confidence": round(confidence, 1),
            "news_sentiment": round(news_sent, 3),
            "social_sentiment": round(social_sent, 3),
            "fear_greed_score": round(fear_greed, 1),
            "key_themes": themes,
            "analyst_upgrades": upgrades,
            "analyst_downgrades": downgrades,
            "reasoning": (
                f"{ticker} sentiment: news score {news_sent:+.2f}, social score {social_sent:+.2f}. "
                f"Fear/Greed index at {fear_greed:.0f}. "
                f"Analyst activity: {upgrades} upgrades, {downgrades} downgrades. "
                f"Strategy 18.3 classification: {direction} with {confidence:.0f}% confidence."
            ),
        }
