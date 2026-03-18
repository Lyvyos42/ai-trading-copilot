"""
News API — returns scraped financial & geopolitical news articles.
"""
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.news import NewsArticle

log = structlog.get_logger()
router = APIRouter(prefix="/api/v1/news", tags=["news"])

VALID_CATEGORIES = {"MACRO", "GEOPOLITICAL", "EARNINGS", "FED", "CRISIS", "MARKETS"}
VALID_SENTIMENTS = {"POSITIVE", "NEGATIVE", "NEUTRAL"}


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class NewsArticleOut(BaseModel):
    id:              str
    headline:        str
    summary:         Optional[str]
    source:          str
    url:             str
    published_at:    Optional[datetime]
    scraped_at:      Optional[datetime]
    category:        str
    sentiment:       str
    sentiment_score: float
    tickers:         list[str]

    class Config:
        from_attributes = True


class CategorySummary(BaseModel):
    category:  str
    count:     int
    latest_at: Optional[datetime]


class NewsSummaryOut(BaseModel):
    total:      int
    categories: list[CategorySummary]
    last_scraped: Optional[datetime]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[NewsArticleOut])
async def list_news(
    category: Optional[str] = Query(None, description="Filter by category"),
    sentiment: Optional[str] = Query(None, description="Filter by sentiment"),
    source:    Optional[str] = Query(None, description="Filter by source name"),
    ticker:    Optional[str] = Query(None, description="Filter by mentioned ticker"),
    limit:     int = Query(50, ge=1, le=200),
    offset:    int = Query(0,  ge=0),
    db: AsyncSession = Depends(get_db),
):
    q = select(NewsArticle).where(NewsArticle.is_active.is_(True))

    if category and category.upper() in VALID_CATEGORIES:
        q = q.where(NewsArticle.category == category.upper())
    if sentiment and sentiment.upper() in VALID_SENTIMENTS:
        q = q.where(NewsArticle.sentiment == sentiment.upper())
    if source:
        q = q.where(NewsArticle.source.ilike(f"%{source}%"))
    if ticker:
        # JSON array contains — works for PostgreSQL
        q = q.where(NewsArticle.tickers.contains([ticker.upper()]))

    q = q.order_by(desc(NewsArticle.published_at)).limit(limit).offset(offset)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/summary", response_model=NewsSummaryOut)
async def news_summary(db: AsyncSession = Depends(get_db)):
    # Total count
    total_q = await db.execute(
        select(func.count()).select_from(NewsArticle).where(NewsArticle.is_active.is_(True))
    )
    total = total_q.scalar() or 0

    # Per-category counts + latest timestamp
    cat_q = await db.execute(
        select(
            NewsArticle.category,
            func.count().label("count"),
            func.max(NewsArticle.published_at).label("latest_at"),
        )
        .where(NewsArticle.is_active.is_(True))
        .group_by(NewsArticle.category)
        .order_by(desc("count"))
    )
    categories = [
        CategorySummary(category=row.category, count=row.count, latest_at=row.latest_at)
        for row in cat_q.all()
    ]

    # Most recent scrape time
    last_q = await db.execute(
        select(func.max(NewsArticle.scraped_at)).where(NewsArticle.is_active.is_(True))
    )
    last_scraped = last_q.scalar()

    return NewsSummaryOut(total=total, categories=categories, last_scraped=last_scraped)


@router.get("/{article_id}", response_model=NewsArticleOut)
async def get_article(article_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(NewsArticle).where(NewsArticle.id == article_id)
    )
    article = result.scalar_one_or_none()
    if not article:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@router.post("/refresh", status_code=202)
async def trigger_scrape():
    """Manually trigger a news scrape (for testing)."""
    import asyncio
    from app.services.news_scraper import scrape_all_feeds
    asyncio.create_task(scrape_all_feeds())
    return {"message": "Scrape triggered", "status": "accepted"}
