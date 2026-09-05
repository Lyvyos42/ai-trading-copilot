import json
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
        super().__init__("SentimentAnalyst", tier="standard")

    async def analyze(self, state: TradingState) -> dict:
        ticker      = state.get("ticker", "UNKNOWN")
        market_data = state.get("market_data", {})
        strategy_ctx = self._strategy_context(state)

        # 1. Retrieve news context from state or fetch on-demand
        news_ctx = state.get("news_context")
        if not news_ctx or not news_ctx.get("has_news"):
            try:
                from app.services.news_context import get_news_context
                news_ctx = await get_news_context(ticker)
            except Exception:
                news_ctx = {}

        ticker_hl = list(news_ctx.get("ticker_headlines", [])) if news_ctx else []
        market_hl = list(news_ctx.get("market_headlines", [])) if news_ctx else []

        # 2. If ticker-specific headlines are missing, try Tiingo ticker news
        if not ticker_hl:
            try:
                from app.data.tiingo_provider import fetch_ticker_news
                t_news = await fetch_ticker_news(ticker, limit=5)
                if t_news:
                    for art in t_news:
                        title = art.get("title", "").strip()
                        if title:
                            ticker_hl.append(f"[NEWS][Tiingo] {title}")
            except Exception:
                pass

        # 3. If both are empty, try Tiingo market news
        if not ticker_hl and not market_hl:
            try:
                from app.data.tiingo_provider import fetch_market_news
                m_news = await fetch_market_news(limit=10)
                if m_news:
                    for art in m_news:
                        title = art.get("title", "").strip()
                        if title:
                            market_hl.append(f"[NEWS][Tiingo] {title}")
            except Exception:
                pass

        total_articles = len(ticker_hl) + len(market_hl)
        has_news = total_articles > 0 or bool(news_ctx and news_ctx.get("has_news"))

        if not has_news or total_articles == 0:
            return self.abstain(
                f"No news articles found for {ticker} in scraped feed or Tiingo news API. "
                f"SentimentAnalyst abstains rather than synthesizing fake headlines.",
                sentiment_score=None,
                news_sentiment=0.0,
                social_sentiment=0.0,
                fear_greed_score=50.0,
                news_volume=0,
                social_buzz=None,
                key_themes=[],
                top_headlines=[],
                headlines=[],
            )

        # Build enriched news context
        enriched_ctx = {
            **(news_ctx or {}),
            "ticker_headlines": ticker_hl,
            "market_headlines": market_hl,
            "article_count": total_articles or (news_ctx.get("article_count", 0) if news_ctx else 0),
            "avg_sentiment": news_ctx.get("avg_sentiment", 0.0) if news_ctx else 0.0,
            "positive_pct": news_ctx.get("positive_pct", 50.0) if news_ctx else 50.0,
            "negative_pct": news_ctx.get("negative_pct", 50.0) if news_ctx else 50.0,
            "has_news": True,
        }

        # Declare whether this read is actually ABOUT this symbol.
        #
        # With no direct ticker mentions the agent is scoring the same
        # market-wide headline pool the macro agent reads, so its vote is not
        # an independent second opinion - it is the same opinion counted
        # twice. BTC-USD showed "0 direct mentions" while sentiment still
        # voted, and BTC/ETH and EURUSD/GBPUSD came back with identical
        # signals partly because of it. The trader pools votes flagged this
        # way; see MARKET_WIDE_POOL_WEIGHT.
        result = await self._analyze_with_live_news(ticker, market_data, enriched_ctx, strategy_ctx)
        if isinstance(result, dict):
            result["symbol_specific"] = bool(ticker_hl)
            result["ticker_mention_count"] = len(ticker_hl)
        return result

    # ── Live news path ────────────────────────────────────────────────────────

    async def _analyze_with_live_news(self, ticker: str, market_data: dict, news_ctx: dict, strategy_ctx: str = "") -> dict:
        ticker_hl  = news_ctx.get("ticker_headlines", [])
        market_hl  = news_ctx.get("market_headlines", [])
        avg_sent   = news_ctx.get("avg_sentiment", 0.0)
        pos_pct    = news_ctx.get("positive_pct", 50.0)
        neg_pct    = news_ctx.get("negative_pct", 50.0)
        art_count  = news_ctx.get("article_count") or (len(ticker_hl) + len(market_hl))

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

        user_msg = f"""{strategy_ctx}Analyze sentiment for {ticker} using LIVE scraped news data.

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

        raw = await self._call_claude(SYSTEM_PROMPT, user_msg)
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
            "key_themes": self._extract_themes(news_sent, ticker_hl or market_hl),
            "analyst_upgrades": 0,
            "analyst_downgrades": 0,
            "top_headlines": top_hl,
            "reasoning": (
                f"{ticker} live news analysis: sentiment score {news_sent:+.2f} from "
                f"{len(ticker_hl)} direct mentions and {len(market_hl)} market headlines. "
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
