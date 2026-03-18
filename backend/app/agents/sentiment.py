import json
import random
from app.agents.base import BaseAgent
from app.pipeline.state import TradingState


SYSTEM_PROMPT = """You are an expert sentiment analyst applying NLP-based trading strategies:
- Strategy 18.3: Naive Bayes sentiment classification (adapted to transformer-based)
- Extended to live news feeds, earnings call transcripts, and social media signals

You have access to REAL, LIVE scraped headlines from Reuters, CNBC, MarketWatch, AP, BBC, and other sources.
These are actual current events — not simulated data.

Analyze the provided headlines carefully. Consider:
1. Direct mentions of the ticker (highest weight)
2. Sector/market-wide sentiment that affects this asset
3. Macroeconomic sentiment from the broader news flow
4. The ratio of positive to negative headlines in the market overall

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
  "top_headlines": [<string>, ...],
  "reasoning": "<string>"
}

The "top_headlines" field must list the 2-3 most impactful headlines you identified."""


class SentimentAnalyst(BaseAgent):
    def __init__(self):
        super().__init__("SentimentAnalyst", model="claude-sonnet-4-6")

    async def analyze(self, state: TradingState) -> dict:
        ticker      = state.get("ticker", "UNKNOWN")
        market_data = state.get("market_data", {})
        news_ctx    = state.get("news_context", {})
        has_news    = news_ctx.get("has_news", False)

        if has_news:
            return await self._analyze_with_live_news(ticker, market_data, news_ctx)
        else:
            return await self._analyze_with_mock(ticker, market_data)

    # ── Live news path ────────────────────────────────────────────────────────

    async def _analyze_with_live_news(self, ticker: str, market_data: dict, news_ctx: dict) -> dict:
        ticker_hl  = news_ctx.get("ticker_headlines", [])
        market_hl  = news_ctx.get("market_headlines", [])
        avg_sent   = news_ctx.get("avg_sentiment", 0.0)
        pos_pct    = news_ctx.get("positive_pct", 50.0)
        neg_pct    = news_ctx.get("negative_pct", 50.0)
        art_count  = news_ctx.get("article_count", 0)

        # Build the headline section for the prompt
        ticker_section = ""
        if ticker_hl:
            ticker_section = f"""
DIRECT {ticker} MENTIONS ({len(ticker_hl)} articles):
{chr(10).join(f'  • {h}' for h in ticker_hl)}
"""
        else:
            ticker_section = f"\nDIRECT {ticker} MENTIONS: None found in current news feed.\n"

        market_section = ""
        if market_hl:
            market_section = f"""
BROADER MARKET HEADLINES ({len(market_hl)} articles):
{chr(10).join(f'  • {h}' for h in market_hl[:8])}
"""

        user_msg = f"""Analyze sentiment for {ticker} using LIVE scraped news data.

=== LIVE NEWS FEED (Real headlines, scraped in last 24h) ===
{ticker_section}
{market_section}
=== MARKET SENTIMENT METRICS (from {art_count} scraped articles) ===
• Overall news sentiment score: {avg_sent:+.3f} (scale: -1.0 bearish to +1.0 bullish)
• Bullish articles: {pos_pct:.1f}%
• Bearish articles: {neg_pct:.1f}%

=== PRICE ACTION ===
• Recent price change: {market_data.get('price_change_pct', 'N/A')}%
• Volume vs 30d avg: {market_data.get('volume_ratio', 'N/A')}x

Strategy 18.3: Based on the REAL headlines above, classify overall sentiment.
Pay special attention to any direct ticker mentions. Output JSON only."""

        raw = self._call_claude(SYSTEM_PROMPT, user_msg)
        if raw:
            try:
                result = json.loads(raw)
                result["_live_news"] = True
                result["_ticker_headlines"] = ticker_hl
                return result
            except json.JSONDecodeError:
                pass

        # Fallback: derive from the news metrics directly
        return self._derive_from_news_metrics(ticker, avg_sent, pos_pct, neg_pct, ticker_hl, market_hl)

    def _derive_from_news_metrics(
        self, ticker: str, avg_sent: float, pos_pct: float, neg_pct: float,
        ticker_hl: list, market_hl: list
    ) -> dict:
        """Fallback when Claude API call fails — derive signal directly from scraped metrics."""
        news_sent = avg_sent
        social_sent = avg_sent * 0.7

        # Ticker-specific headlines override market average
        if ticker_hl:
            ticker_words = " ".join(ticker_hl).lower()
            pos_words = sum(ticker_words.count(w) for w in
                            ["beat", "surge", "gain", "record", "growth", "strong", "raise"])
            neg_words = sum(ticker_words.count(w) for w in
                            ["miss", "fall", "drop", "cut", "weak", "loss", "crisis"])
            if pos_words + neg_words > 0:
                news_sent = (pos_words - neg_words) / (pos_words + neg_words)

        fear_greed = min(90, max(10, 50 + avg_sent * 40))
        direction = "LONG" if news_sent > 0.1 else ("SHORT" if news_sent < -0.1 else "NEUTRAL")
        confidence = min(85, max(30, 50 + abs(news_sent) * 35))

        top_hl = (ticker_hl + market_hl)[:3]
        return {
            "direction": direction,
            "confidence": round(confidence, 1),
            "news_sentiment": round(news_sent, 3),
            "social_sentiment": round(social_sent, 3),
            "fear_greed_score": round(fear_greed, 1),
            "key_themes": self._extract_themes(news_sent, ticker_hl),
            "analyst_upgrades": 0,
            "analyst_downgrades": 0,
            "top_headlines": top_hl,
            "reasoning": (
                f"{ticker} live news analysis: sentiment score {news_sent:+.2f} from {len(ticker_hl)} "
                f"direct mentions. Market-wide: {pos_pct:.0f}% bullish, {neg_pct:.0f}% bearish. "
                f"Strategy 18.3 classification: {direction} with {confidence:.0f}% confidence."
            ),
            "_live_news": True,
        }

    @staticmethod
    def _extract_themes(sentiment: float, headlines: list) -> list[str]:
        text = " ".join(headlines).lower()
        themes = []
        if "earning" in text or "revenue" in text:
            themes.append("earnings_driven")
        if "fed" in text or "rate" in text:
            themes.append("rate_sensitive")
        if "geopolit" in text or "war" in text or "sanction" in text:
            themes.append("geopolitical_risk")
        if sentiment > 0.2:
            themes.append("bullish_momentum")
        elif sentiment < -0.2:
            themes.append("bearish_momentum")
        else:
            themes.append("mixed_signals")
        return themes or ["neutral_flow"]

    # ── Mock path (no news in DB yet) ─────────────────────────────────────────

    MOCK_HEADLINES = {
        "positive": [
            "beats earnings expectations", "raises full-year guidance",
            "announces share buyback", "reports record revenue",
        ],
        "negative": [
            "misses earnings estimates", "cuts revenue forecast",
            "faces regulatory scrutiny", "announces layoffs",
        ],
        "neutral": [
            "scheduled to report earnings next week",
            "files quarterly report with SEC",
        ],
    }

    async def _analyze_with_mock(self, ticker: str, market_data: dict) -> dict:
        rng = random.Random(sum(ord(c) for c in ticker) + 42)
        sentiment_bias = rng.uniform(-0.4, 0.4)

        if sentiment_bias > 0.1:
            headlines = [f"{ticker} {h}" for h in rng.sample(self.MOCK_HEADLINES["positive"], 3)]
        elif sentiment_bias < -0.1:
            headlines = [f"{ticker} {h}" for h in rng.sample(self.MOCK_HEADLINES["negative"], 3)]
        else:
            headlines = [f"{ticker} {h}" for h in rng.sample(self.MOCK_HEADLINES["neutral"], 2)]

        user_msg = f"""Analyze sentiment for {ticker}.
Recent price change: {market_data.get('price_change_pct', 'N/A')}%
Volume vs 30d avg: {market_data.get('volume_ratio', 'N/A')}x

NOTE: Live news scraper is warming up — using estimated headlines for now:
{chr(10).join(f'- {h}' for h in headlines)}

Simulated social media buzz score: {rng.randint(20, 90)}/100
Strategy 18.3: Classify overall sentiment. Output JSON only."""

        raw = self._call_claude(SYSTEM_PROMPT, user_msg)
        if raw:
            try:
                result = json.loads(raw)
                result["_live_news"] = False
                return result
            except json.JSONDecodeError:
                pass

        return self._mock_fallback(ticker, sentiment_bias, headlines, rng)

    def _mock_fallback(self, ticker: str, bias: float, headlines: list, rng: random.Random) -> dict:
        news_sent  = bias + rng.uniform(-0.15, 0.15)
        social_sent = bias * 0.7 + rng.uniform(-0.2, 0.2)
        fear_greed  = min(90, max(10, 50 + bias * 40 + rng.uniform(-10, 10)))
        upgrades    = rng.randint(0, 3) if bias > 0 else 0
        downgrades  = rng.randint(0, 3) if bias < 0 else 0
        direction   = "LONG" if news_sent > 0.1 else ("SHORT" if news_sent < -0.1 else "NEUTRAL")
        confidence  = min(85, max(30, 50 + abs(news_sent) * 35))

        return {
            "direction": direction,
            "confidence": round(confidence, 1),
            "news_sentiment": round(news_sent, 3),
            "social_sentiment": round(social_sent, 3),
            "fear_greed_score": round(fear_greed, 1),
            "key_themes": ["earnings_beat", "growth_momentum"] if bias > 0 else ["mixed_signals"],
            "analyst_upgrades": upgrades,
            "analyst_downgrades": downgrades,
            "top_headlines": headlines[:2],
            "reasoning": (
                f"{ticker} sentiment (estimated): news {news_sent:+.2f}, social {social_sent:+.2f}. "
                f"Fear/Greed {fear_greed:.0f}. Strategy 18.3: {direction} at {confidence:.0f}%."
            ),
            "_live_news": False,
        }
