"""
News context service — fetches structured live headlines from the DB
and packages them for agent consumption before the pipeline runs.
Falls back to empty context gracefully if DB has no articles yet.
"""
import html
import re
from datetime import datetime, timedelta, timezone
from sqlalchemy import desc, select

from app.db.database import AsyncSessionLocal
from app.models.news import NewsArticle

_MAX_HEADLINE_LEN = 160  # chars per sanitized headline


def _sanitize_headline(text: str) -> str:
    """Strip HTML tags, decode HTML entities, and truncate to safe length."""
    if not text:
        return ""
    # Decode HTML entities first (&amp; → &, &#8217; → ', etc.)
    text = html.unescape(text)
    # Strip any residual HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse whitespace
    text = " ".join(text.split())
    # Truncate (guards against oversized injected content)
    if len(text) > _MAX_HEADLINE_LEN:
        text = text[:_MAX_HEADLINE_LEN] + "…"
    return text


async def get_news_context(ticker: str) -> dict:
    """
    Returns a structured dict of recent headlines, grouped by relevance to
    SentimentAnalyst (market/earnings/ticker-specific) and MacroAnalyst
    (macro/fed/geopolitical/crisis).

    Structure:
    {
        "ticker_headlines":  list[str],   # headlines explicitly mentioning ticker
        "market_headlines":  list[str],   # latest MARKETS + EARNINGS headlines
        "macro_headlines":   list[str],   # latest MACRO + FED headlines
        "geo_headlines":     list[str],   # latest GEOPOLITICAL headlines
        "crisis_headlines":  list[str],   # latest CRISIS headlines
        "avg_sentiment":     float,       # mean sentiment_score across all fetched
        "positive_pct":      float,       # % of articles with POSITIVE sentiment
        "negative_pct":      float,       # % of articles with NEGATIVE sentiment
        "article_count":     int,         # total articles in context window
        "has_news":          bool,        # False if DB is empty (scraper not run yet)
    }
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    clean_ticker = ticker.replace("-USD", "").replace("=X", "").replace("=F", "").replace("^", "").upper()

    try:
        async with AsyncSessionLocal() as session:
            # Fetch last 24h of articles across all categories (max 150)
            result = await session.execute(
                select(NewsArticle)
                .where(NewsArticle.is_active == True)
                .where(NewsArticle.scraped_at >= cutoff)
                .order_by(desc(NewsArticle.published_at))
                .limit(150)
            )
            articles = result.scalars().all()

            # If nothing in last 24h, grab the most recent 60 regardless of age
            if not articles:
                result = await session.execute(
                    select(NewsArticle)
                    .where(NewsArticle.is_active == True)
                    .order_by(desc(NewsArticle.published_at))
                    .limit(60)
                )
                articles = result.scalars().all()

    except Exception:
        return _empty_context()

    if not articles:
        return _empty_context()

    # ── Group by category ────────────────────────────────────────────────────
    ticker_headlines  = []
    market_headlines  = []
    macro_headlines   = []
    geo_headlines     = []
    crisis_headlines  = []

    sentiment_scores = [a.sentiment_score for a in articles]
    positive = sum(1 for a in articles if a.sentiment == "POSITIVE")
    negative = sum(1 for a in articles if a.sentiment == "NEGATIVE")

    for art in articles:
        # Sanitize headline before injecting into agent prompts (prompt injection defense)
        safe_headline = _sanitize_headline(art.headline)
        # Format with [NEWS] boundary marker so agents know this is external content
        label = f"[NEWS][{art.source}] {safe_headline}"

        # Ticker-specific — mentioned in tickers array OR headline contains clean ticker
        if (clean_ticker in (art.tickers or [])) or (clean_ticker in art.headline.upper()):
            ticker_headlines.append(label)

        if art.category in ("MARKETS", "EARNINGS"):
            market_headlines.append(label)
        elif art.category in ("MACRO", "FED"):
            macro_headlines.append(label)
        elif art.category == "GEOPOLITICAL":
            geo_headlines.append(label)
        elif art.category == "CRISIS":
            crisis_headlines.append(label)

    total = len(articles)
    return {
        "ticker_headlines": ticker_headlines[:8],
        "market_headlines": market_headlines[:10],
        "macro_headlines":  macro_headlines[:10],
        "geo_headlines":    geo_headlines[:6],
        "crisis_headlines": crisis_headlines[:4],
        "avg_sentiment":    round(sum(sentiment_scores) / total, 3) if total else 0.0,
        "positive_pct":     round(positive / total * 100, 1) if total else 50.0,
        "negative_pct":     round(negative / total * 100, 1) if total else 50.0,
        "article_count":    total,
        "has_news":         True,
    }


def _empty_context() -> dict:
    return {
        "ticker_headlines": [],
        "market_headlines": [],
        "macro_headlines":  [],
        "geo_headlines":    [],
        "crisis_headlines": [],
        "avg_sentiment":    0.0,
        "positive_pct":     50.0,
        "negative_pct":     50.0,
        "article_count":    0,
        "has_news":         False,
    }
