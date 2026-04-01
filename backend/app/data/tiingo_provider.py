"""
Tiingo news provider — fetches financial news articles with sentiment.
Free tier: 500 requests/day. Paid tiers available for higher volume.
Falls back gracefully if no API key or if rate limited.
"""
from datetime import datetime, timedelta
from typing import Optional

import httpx
import structlog

from app.config import settings

log = structlog.get_logger()

_BASE = "https://api.tiingo.com"
_TIMEOUT = 10.0


async def fetch_ticker_news(
    ticker: str,
    limit: int = 10,
    lookback_days: int = 3,
) -> Optional[list[dict]]:
    """
    Fetch recent news articles for a ticker from Tiingo.
    Returns list of {title, description, url, source, published_at, tickers, tags} or None.
    """
    key = settings.tiingo_api_key
    if not key:
        return None

    start_date = (datetime.utcnow() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    url = f"{_BASE}/news"
    params = {
        "tickers": ticker.lower(),
        "startDate": start_date,
        "limit": limit,
        "sortBy": "crawlDate",
        "token": key,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            articles = resp.json()

        results = []
        for art in articles:
            results.append({
                "title": art.get("title", ""),
                "description": art.get("description", ""),
                "url": art.get("url", ""),
                "source": art.get("source", "tiingo"),
                "published_at": art.get("publishedDate", ""),
                "tickers": art.get("tickers", []),
                "tags": art.get("tags", []),
            })

        log.info("tiingo_news_fetched", ticker=ticker, count=len(results))
        return results

    except Exception as e:
        log.warning("tiingo_news_failed", ticker=ticker, error=str(e))
        return None


async def fetch_market_news(limit: int = 20) -> Optional[list[dict]]:
    """Fetch broad market news (no specific ticker filter)."""
    key = settings.tiingo_api_key
    if not key:
        return None

    url = f"{_BASE}/news"
    params = {
        "limit": limit,
        "sortBy": "crawlDate",
        "token": key,
    }

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=_TIMEOUT)
            resp.raise_for_status()
            articles = resp.json()

        results = []
        for art in articles:
            results.append({
                "title": art.get("title", ""),
                "description": art.get("description", ""),
                "url": art.get("url", ""),
                "source": art.get("source", "tiingo"),
                "published_at": art.get("publishedDate", ""),
                "tickers": art.get("tickers", []),
                "tags": art.get("tags", []),
            })

        log.info("tiingo_market_news_fetched", count=len(results))
        return results

    except Exception as e:
        log.warning("tiingo_market_news_failed", error=str(e))
        return None
