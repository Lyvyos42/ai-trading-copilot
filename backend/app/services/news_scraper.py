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
from app.data.tiingo_provider import fetch_ticker_news, fetch_market_news as tiingo_market_news

log = structlog.get_logger()

# ── RSS Feed Catalogue ────────────────────────────────────────────────────────
# Google News RSS is the most reliable source from any server (no bot blocking,
# no paywall). Fed is official/highly reliable. Yahoo included as bonus.
FEEDS = [
    # Google News RSS — always accessible, no paywall, no bot blocking
    {"url": "https://news.google.com/rss/search?q=stock+market+financial+news&hl=en-US&gl=US&ceid=US:en",     "source": "Google News"},
    {"url": "https://news.google.com/rss/search?q=inflation+economy+federal+reserve&hl=en-US&gl=US&ceid=US:en", "source": "Google News"},
    {"url": "https://news.google.com/rss/search?q=earnings+report+revenue+profit&hl=en-US&gl=US&ceid=US:en",   "source": "Google News"},
    {"url": "https://news.google.com/rss/search?q=cryptocurrency+bitcoin+ethereum&hl=en-US&gl=US&ceid=US:en",  "source": "Google News"},
    {"url": "https://news.google.com/rss/search?q=geopolitical+war+sanctions+tariff&hl=en-US&gl=US&ceid=US:en","source": "Google News"},
    {"url": "https://news.google.com/rss/search?q=S%26P+500+nasdaq+dow+jones&hl=en-US&gl=US&ceid=US:en",       "source": "Google News"},
    {"url": "https://news.google.com/rss/search?q=interest+rate+central+bank+monetary+policy&hl=en-US&gl=US&ceid=US:en", "source": "Google News"},
    {"url": "https://news.google.com/rss/search?q=bank+financial+crisis+debt&hl=en-US&gl=US&ceid=US:en",       "source": "Google News"},
    {"url": "https://news.google.com/rss/search?q=oil+gold+commodities+futures&hl=en-US&gl=US&ceid=US:en",     "source": "Google News"},
    {"url": "https://news.google.com/rss/search?q=forex+currency+exchange+rate&hl=en-US&gl=US&ceid=US:en",     "source": "Google News"},
    # Federal Reserve official feed — highly reliable
    {"url": "https://www.federalreserve.gov/feeds/releases.xml", "source": "Federal Reserve"},
    # Yahoo Finance — often works
    {"url": "https://finance.yahoo.com/news/rssindex", "source": "Yahoo Finance"},
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
                "is_active":      True,
            })
        return articles
    except Exception as exc:
        log.warning("feed_fetch_failed", url=url, error=str(exc))
        return []


_SEED_ARTICLES = [
    # MARKETS (4)
    {"headline": "S&P 500 Climbs 0.8% as Tech Rally Extends Into Third Consecutive Session",
     "summary": "The S&P 500 advanced on broad-based gains led by mega-cap technology stocks, with the index approaching its all-time high set earlier this month. NVIDIA and Meta were top contributors.",
     "source": "Reuters", "url": "https://seed.quantneuraledge.com/markets/sp500-rally-1",
     "category": "MARKETS", "tickers": ["SPY", "NVDA", "META"]},
    {"headline": "Wall Street Futures Point Higher Ahead of Key Inflation Data Release",
     "summary": "U.S. equity futures edged up as investors positioned ahead of Thursday's CPI report, which is expected to show inflation cooling slightly from last month's reading.",
     "source": "Bloomberg", "url": "https://seed.quantneuraledge.com/markets/futures-higher-2",
     "category": "MARKETS", "tickers": ["SPY", "QQQ"]},
    {"headline": "Small-Cap Stocks Outperform as Russell 2000 Posts Best Week Since November",
     "summary": "The Russell 2000 surged 2.1% on the week, outpacing large-cap peers as investors rotated into domestically focused companies on stronger-than-expected retail sales data.",
     "source": "CNBC", "url": "https://seed.quantneuraledge.com/markets/russell-outperform-3",
     "category": "MARKETS", "tickers": ["IWM"]},
    {"headline": "VIX Falls Below 14 as Volatility Expectations Hit Six-Month Low",
     "summary": "The CBOE Volatility Index dropped to its lowest level since September, signaling reduced near-term uncertainty as earnings season kicks off with largely positive surprises.",
     "source": "MarketWatch", "url": "https://seed.quantneuraledge.com/markets/vix-low-4",
     "category": "MARKETS", "tickers": ["SPY"]},
    # MACRO (4)
    {"headline": "U.S. CPI Rises 3.1% Year-Over-Year, Slightly Below Consensus Estimate of 3.2%",
     "summary": "Consumer prices rose at a slower pace than expected in February, boosting hopes that the Federal Reserve's inflation-fighting campaign is succeeding and that rate cuts may begin mid-year.",
     "source": "Reuters", "url": "https://seed.quantneuraledge.com/macro/cpi-feb-5",
     "category": "MACRO", "tickers": []},
    {"headline": "Nonfarm Payrolls Add 275,000 Jobs; Unemployment Ticks Up to 3.9%",
     "summary": "The U.S. economy added more jobs than expected in February while the unemployment rate rose slightly, pointing to a resilient but gradually cooling labor market.",
     "source": "AP News", "url": "https://seed.quantneuraledge.com/macro/nonfarm-payrolls-6",
     "category": "MACRO", "tickers": []},
    {"headline": "Euro-Zone PMI Rises to 49.2 in February, Signaling Contraction Easing",
     "summary": "The euro-zone composite PMI rose from 47.9 to 49.2, its highest reading in nine months, as services activity improved while manufacturing remained in contraction territory.",
     "source": "Bloomberg", "url": "https://seed.quantneuraledge.com/macro/eurozone-pmi-7",
     "category": "MACRO", "tickers": []},
    {"headline": "China's Industrial Output Beats Forecasts, Easing Concerns Over Growth Slowdown",
     "summary": "China's industrial production expanded 7.0% year-on-year in January-February, well above the 5.0% forecast, providing some relief to global markets worried about the world's second-largest economy.",
     "source": "Reuters", "url": "https://seed.quantneuraledge.com/macro/china-industrial-8",
     "category": "MACRO", "tickers": []},
    # EARNINGS (4)
    {"headline": "NVIDIA Reports Record Q4 Revenue of $22.1B, EPS Beats by Wide Margin",
     "summary": "NVIDIA's data center revenue surged 409% year-over-year to $18.4 billion, crushing analyst expectations, as demand for AI chips continues to overwhelm supply. The company guided Q1 revenue above $24 billion.",
     "source": "CNBC", "url": "https://seed.quantneuraledge.com/earnings/nvda-q4-9",
     "category": "EARNINGS", "tickers": ["NVDA"]},
    {"headline": "Apple Q1 Earnings: Revenue Misses Estimates for First Time in Six Quarters",
     "summary": "Apple reported quarterly revenue of $119.6 billion, slightly below the $121.0 billion consensus, as iPhone sales in China declined 13% amid intensifying competition from Huawei.",
     "source": "Bloomberg", "url": "https://seed.quantneuraledge.com/earnings/aapl-q1-10",
     "category": "EARNINGS", "tickers": ["AAPL"]},
    {"headline": "JPMorgan Chase Posts Record Full-Year Profit of $49.6B, Raises Dividend",
     "summary": "JPMorgan Chase reported record annual net income driven by higher interest income and investment banking fees. CEO Jamie Dimon warned of elevated geopolitical and fiscal risks heading into 2026.",
     "source": "Reuters", "url": "https://seed.quantneuraledge.com/earnings/jpm-annual-11",
     "category": "EARNINGS", "tickers": ["JPM"]},
    {"headline": "Tesla Q4 Deliveries Miss, Revenue Beats; Margins Compress to 17.6%",
     "summary": "Tesla delivered 484,507 vehicles in Q4, missing the consensus estimate of 499,000, while revenue beat on higher regulatory credit sales. Automotive gross margin fell to 17.6% from 25.9% a year ago.",
     "source": "MarketWatch", "url": "https://seed.quantneuraledge.com/earnings/tsla-q4-12",
     "category": "EARNINGS", "tickers": ["TSLA"]},
    # FED (4)
    {"headline": "Fed Holds Rates Steady at 5.25-5.50%, Signals Three Cuts Possible in 2025",
     "summary": "The Federal Open Market Committee voted unanimously to hold the federal funds rate steady. The updated dot plot shows a median of three quarter-point cuts projected for the year, unchanged from December.",
     "source": "Federal Reserve", "url": "https://seed.quantneuraledge.com/fed/fomc-hold-13",
     "category": "FED", "tickers": []},
    {"headline": "Powell Tells Congress Fed Is 'Not Far' From Confidence Needed to Cut Rates",
     "summary": "Federal Reserve Chair Jerome Powell told the Senate Banking Committee that the central bank is making progress toward its 2% inflation goal and will lower rates once officials have sufficient confidence inflation is on a sustainable downward path.",
     "source": "Bloomberg", "url": "https://seed.quantneuraledge.com/fed/powell-congress-14",
     "category": "FED", "tickers": []},
    {"headline": "Fed Minutes Show Officials Cautious on Timing of Rate Cuts, Want More Data",
     "summary": "Minutes from the January FOMC meeting revealed that policymakers were broadly in no rush to cut rates and wanted to see several more months of favorable inflation data before easing monetary policy.",
     "source": "Reuters", "url": "https://seed.quantneuraledge.com/fed/fomc-minutes-15",
     "category": "FED", "tickers": []},
    {"headline": "ECB Keeps Rates on Hold, President Lagarde Hints at June Cut If Data Cooperates",
     "summary": "The European Central Bank held all three key interest rates unchanged as expected. President Christine Lagarde said the ECB would be 'data dependent' but that a rate cut by June was plausible if inflation continued to ease.",
     "source": "AP News", "url": "https://seed.quantneuraledge.com/fed/ecb-hold-16",
     "category": "FED", "tickers": []},
    # GEOPOLITICAL (4)
    {"headline": "U.S. Expands Export Controls on Advanced Chips to Additional Countries",
     "summary": "The Biden administration announced new restrictions on the export of advanced semiconductors and related equipment to a broader list of countries, citing national security concerns. Shares of chip equipment makers fell on the news.",
     "source": "Reuters", "url": "https://seed.quantneuraledge.com/geopolitical/chip-controls-17",
     "category": "GEOPOLITICAL", "tickers": ["NVDA", "INTC"]},
    {"headline": "G7 Nations Agree to Use Frozen Russian Asset Profits to Fund Ukraine Aid",
     "summary": "G7 finance ministers reached a deal to use the approximately $3 billion per year in interest earned on frozen Russian sovereign assets to fund a $50 billion loan package for Ukraine, avoiding outright asset seizure.",
     "source": "Bloomberg", "url": "https://seed.quantneuraledge.com/geopolitical/g7-russia-assets-18",
     "category": "GEOPOLITICAL", "tickers": []},
    {"headline": "Red Sea Shipping Disruptions Drive Up Container Rates for Third Consecutive Month",
     "summary": "Freight rates on the Asia-Europe route climbed another 12% as Houthi attacks in the Red Sea continued to force shipping companies to reroute vessels around the Cape of Good Hope, adding 10-14 days to transit times.",
     "source": "CNBC", "url": "https://seed.quantneuraledge.com/geopolitical/red-sea-shipping-19",
     "category": "GEOPOLITICAL", "tickers": []},
    {"headline": "Taiwan Strait Tensions Ease After U.S.-China High-Level Military Talks Resume",
     "summary": "Senior U.S. and Chinese military officials held talks for the first time in over a year, signaling a partial thaw in relations. Defense stocks pulled back slightly on reduced near-term risk premium.",
     "source": "Reuters", "url": "https://seed.quantneuraledge.com/geopolitical/taiwan-talks-20",
     "category": "GEOPOLITICAL", "tickers": []},
]


async def insert_seed_articles() -> int:
    """
    Insert seed/demo articles if the news table is completely empty.
    Called at startup so the UI is never blank on first visit.
    Returns count of articles inserted.
    """
    now = datetime.now(timezone.utc)
    saved = 0
    async with AsyncSessionLocal() as session:
        for i, seed in enumerate(_SEED_ARTICLES):
            existing = await session.execute(
                select(NewsArticle).where(NewsArticle.url == seed["url"])
            )
            if existing.scalar_one_or_none():
                continue
            text = f"{seed['headline']} {seed.get('summary', '')}"
            sentiment, score = _score_sentiment(text)
            session.add(NewsArticle(
                id=str(uuid.uuid4()),
                headline=seed["headline"],
                summary=seed.get("summary"),
                source=seed["source"],
                url=seed["url"],
                published_at=now,
                category=seed["category"],
                sentiment=sentiment,
                sentiment_score=score,
                tickers=seed.get("tickers", []),
            ))
            saved += 1
        await session.commit()
    if saved:
        log.info("seed_articles_inserted", count=saved)
    return saved


def _tiingo_to_article(art: dict) -> dict:
    """Convert a Tiingo news article to the internal article format."""
    text = f"{art['title']} {art.get('description', '')}"
    category = _classify_category(text)
    sentiment, score = _score_sentiment(text)
    tickers = _extract_tickers(text)
    # Also include tickers reported by Tiingo
    for t in art.get("tickers", []):
        upper = t.upper()
        if upper not in tickers:
            tickers.append(upper)
    pub_str = art.get("published_at", "")
    try:
        pub_date = datetime.fromisoformat(pub_str.replace("Z", "+00:00")) if pub_str else datetime.now(timezone.utc)
    except (ValueError, AttributeError):
        pub_date = datetime.now(timezone.utc)
    return {
        "id": str(uuid.uuid4()),
        "headline": art["title"],
        "summary": (art.get("description") or "")[:500] or None,
        "source": art.get("source", "Tiingo"),
        "url": art.get("url", ""),
        "published_at": pub_date,
        "category": category,
        "sentiment": sentiment,
        "sentiment_score": score,
        "tickers": tickers,
        "is_active": True,
    }


async def _scrape_tiingo() -> list[dict]:
    """Try fetching broad market news from Tiingo. Returns article dicts or empty list."""
    raw = await tiingo_market_news(limit=30)
    if not raw:
        return []
    articles = [_tiingo_to_article(a) for a in raw if a.get("title")]
    log.info("tiingo_scrape_done", count=len(articles))
    return articles


async def scrape_all_feeds() -> int:
    """Fetch all feeds and upsert new articles. Tries Tiingo first, falls back to RSS."""
    # Try Tiingo as primary source
    tiingo_articles = await _scrape_tiingo()

    # Always fetch RSS as well to maximize coverage
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 (compatible; QuantNeural/1.0; +https://quantneuraledge.com/bot)"},
        timeout=httpx.Timeout(20.0, connect=8.0),
        follow_redirects=True,
    ) as client:
        results = await asyncio.gather(*[_fetch_feed(client, f) for f in FEEDS], return_exceptions=True)
    # Filter out exceptions (individual feed failures should not crash the whole batch)
    results = [r if isinstance(r, list) else [] for r in results]

    rss_articles = [a for batch in results for a in batch]

    # Combine: Tiingo first (higher quality), then RSS
    all_articles = tiingo_articles + rss_articles
    if not all_articles:
        log.warning("all_feeds_failed_using_seeds")
        return await insert_seed_articles()

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
