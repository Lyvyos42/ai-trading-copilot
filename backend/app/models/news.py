import uuid
from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, Float, JSON, String, Text, func
from app.db.database import Base


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id           = Column(String,   primary_key=True, default=lambda: str(uuid.uuid4()))
    headline     = Column(Text,     nullable=False)
    summary      = Column(Text,     nullable=True)
    source       = Column(String(100), nullable=False)
    url          = Column(Text,     unique=True, nullable=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    scraped_at   = Column(DateTime(timezone=True), server_default=func.now())

    # Classification
    category        = Column(String(50),  nullable=False, default="MARKETS")
    sentiment       = Column(String(20),  nullable=False, default="NEUTRAL")
    sentiment_score = Column(Float,       nullable=False, default=0.0)

    # Mentioned tickers extracted from headline
    tickers    = Column(JSON,    nullable=False, default=list)
    is_active  = Column(Boolean, nullable=False, default=True)
