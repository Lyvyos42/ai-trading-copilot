"""
News scraper — fetches RSS feeds from major financial and world news sources.
Classifies articles into categories and scores sentiment using keyword matching.
No paid APIs required.
"""
import asyncio
import re
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
import httpx
import structlog
from sqlalchemy import select

from app.db.database import AsyncSessionLocal
from app.models.news import NewsArticle

log = structlog.get_logger()

# ── RSS Feed Catalogue ────────────────────────────────────────────────────────
# Note: Reuters deprecated public RSS in 2023. AP News changed URLs. CNBC often blocks bots.
# These are the most reliable free finance RSS feeds as of 2026.
FEEDS = [
    # Yahoo Finance — highly reliable, broad coverage
    {"url": "https://finance.yahoo.com/news/rssindex",                              "source": "Yahoo Finance"},
    # BBC — reliable, no paywall
    {"url": "https://feeds.bbci.co.uk/news/business/rss.xml",                      "source": "BBC Business"},
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml",                         "source": "BBC World"},
    # AP News — updated URLs (2024+)
    {"url": "https://feeds.apnews.com/rss/apf-business",                           "source": "AP Business"},
    {"url": "https://feeds.apnews.com/rss/apf-finance",                            "source": "AP Finance"},
    # MarketWatch
    {"url": "https://feeds.marketwatch.com/marketwatch/topstories/",               "source": "MarketWatch"},
    {"url": "https://feeds.marketwatch.com/marketwatch/marketpulse/",              "source": "MarketWatch"},
    # The Guardian — reliable, no paywall
    {"url": "https://www.theguardian.com/business/rss",                            "source": "The Guardian"},
    {"url": "https://www.theguardian.com/business/economics/rss",                  "source": "Guardian Economics"},
    # Investopedia
    {"url": "https://www.investopedia.com/feeds/rss.aspx",                         "source": "Investopedia"},
    # CNBC (top-level, less likely to be blocked)
    {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114", "source": "CNBC"},
    {"url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664",  "source": "CNBC Markets"},
    # Central Banks / Macro — official, highly reliable
    {"url": "https://www.federalreserve.gov/feeds/releases.xml",                   "source": "Federal Reserve"},
    {"url": "https://www.ecb.europa.eu/rss/press.html",                            "source": "ECB"},
    # Seeking Alpha (market news)
    {"url": "https://seekingalpha.com/market_currents.xml",                        "source": "Seeking Alpha"},
    # FT (limited but often available)
    {"url": "https://www.ft.com/rss/home/uk",                                      "source": "FT"},
]

# ── Category Keywords ─────────────────────────────────────────────────────────
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("FED", [
        "federal reserve", "fed ", "fomc", "powell", "interest rate", "rate hike",
        "rate cut", "monetary policy", "fed funds", "quantitative easing", "qt ",
        "balance sheet", "central bank", "boe", "ecb", "boj", "rba",
    ]),
    ("EARNINGS", [
        "earnings", "quarterly results", "quarterly profit", "revenue", " eps ",
        "earnings per share", "beat estimates", "missed estimates", "guidance",
        "full-year", "fiscal year", "q1 ", "q2 ", "q3 ", "q4 ", "annual profit",
    ]),
    ("MACRO", [
        "gdp", "inflation", " cpi ", " pce ", "consumer price", "producer price",
        "unemployment", "jobs report", "nonfarm payroll", "economic growth",
        "recession", "trade deficit", "current account", "purchasing managers",
        "pmi", "retail sales", "consumer confidence", "housing starts",
    ]),
    ("GEOPOLITICAL", [
        "war", "sanctions", "trade war", "tariff", "diplomatic", "military",
        "conflict", "nato", "ukraine", "russia", "china", "taiwan", "middle east",
        "iran", "north korea", "geopolit", "missile", "invasion", "ceasefire",
        "election", "coup", "protest", "regime",
    ]),
    ("CRISIS", [
        "bank failure", "bank run", "collapse", "crash", "default", "emergency",
        "bankruptcy", "bailout", "contagion", "systemic risk", "debt ceiling",
        "credit crunch", "financial crisis", "liquidity crisis", "insolvency",
    ]),
]
# Default if no rule matches
DEFAULT_CATEGORY = "MARKETS"

# ── Sentiment Keywords ────────────────────────────────────────────────────────
POSITIVE_WORDS = [
    "surge", "rally", "soar", "jump", "gain", "rise", "record", "beat",
    "strong", "bullish", "recovery", "growth", "profit", "upgrade", "outperform",
    "boom", "optimism", "expansion", "positive", "improve", "rebound",
]
NEGATIVE_WORDS = [
    "fall", "drop", "crash", "plunge", "miss", "weak", "bearish", "decline",
    "loss", "downgrade", "underperform", "recession", "crisis", "default",
    "collapse", "concern", "risk", "warning", "negative", "slowdown", "fear",
]

# ── Common tickers to extract from headlines ──────────────────────────────────
TICKER_PATTERN = re.compile(
    r'\b(AAPL|MSFT|NVDA|GOOGL|AMZN|TSLA|META|NFLX|AMD|INTC|JPM|GS|BAC|'
    r'MS|WFC|V|MA|PYPL|BRK\.B|XOM|CVX|WMT|TGT|COST|HD|SBUX|SPY|QQQ|'
    r'IWM|DIA|GLD|SLV|USO|BTC|ETH|BNB|SOL|XRP)\b',
    re.IGNORECASE
)


def _classify_category(text: str) -> str:
    t = text.lower()
    for category, keywords in CATEGORY_RULES:
        if any(kw in t for kw in keywords):
            return category
    return DEFAULT_CATEGORY


def _score_sentiment(text: str) -> tuple[str, float]:
    t = text.lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in t)
    neg = sum(1 for w in NEGATIVE_WORDS if w in t)
    total = pos + neg
    if total == 0:
        return "NEUTRAL", 0.0
    score = (pos - neg) / total  # -1.0 to +1.0
    if score > 0.1:
        return "POSITIVE", round(score, 3)
    if score < -0.1:
        return "NEGATIVE", round(score, 3)
    return "NEUTRAL", round(score, 3)


def _extract_tickers(text: str) -> list[str]:
    return list(set(TICKER_PATTERN.findall(text.upper())))


def _parse_date(entry) -> Optional[datetime]:
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                return parsedate_to_datetime(raw).replace(tzinfo=timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


async def _fetch_feed(client: httpx.AsyncClient, feed_meta: dict) -> list[dict]:
    url = feed_meta["url"]
    source = feed_meta["source"]
    try:
        resp = await client.get(url, timeout=12.0)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.text)
        articles = []
        for entry in parsed.entries[:20]:  # max 20 per feed per run
            headline = getattr(entry, "title", "").strip()
            if not headline:
                continue
            link = getattr(entry, "link", "").strip()
            if not link:
                continue
            summary_raw = getattr(entry, "summary", "") or ""
            # Strip HTML tags from summary
            summary = re.sub(r"<[^>]+>", " ", summary_raw).strip()[:500]

            full_text = f"{headline} {summary}"
            category = _classify_category(full_text)
            sentiment, score = _score_sentiment(full_text)
            tickers = _extract_tickers(full_text)
            pub_date = _parse_date(entry)

            articles.append({
                "id":             str(uuid.uuid4()),
                "headline":       headline,
                "summary":        summary or None,
                "source":         source,
                "url":            link,
                "published_at":   pub_date,
                "category":       category,
                "sentiment":      sentiment,
                "sentiment_score": score,
                "tickers":        tickers,
            })
        return articles
    except Exception as exc:
        log.warning("feed_fetch_failed", url=url, error=str(exc))
        return []


async def scrape_all_feeds() -> int:
    """Fetch all feeds and upsert new articles. Returns count of new articles saved."""
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (compatible; QuantNeural/1.0; +https://quantneuraledge.com/bot)"},
        timeout=httpx.Timeout(20.0, connect=8.0),
        follow_redirects=True,
    ) as client:
        results = await asyncio.gather(*[_fetch_feed(client, f) for f in FEEDS], return_exceptions=True)
    # Filter out exceptions (individual feed failures should not crash the whole batch)
    results = [r if isinstance(r, list) else [] for r in results]

    all_articles = [a for batch in results for a in batch]
    if not all_articles:
        return 0

    saved = 0
    async with AsyncSessionLocal() as session:
        for art in all_articles:
            # Skip if URL already exists
            existing = await session.execute(
                select(NewsArticle).where(NewsArticle.url == art["url"])
            )
            if existing.scalar_one_or_none():
                continue
            session.add(NewsArticle(**art))
            saved += 1
        await session.commit()

    log.info("news_scrape_done", total_fetched=len(all_articles), new_saved=saved)
    return saved
