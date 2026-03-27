"""
Memory Layer models — structured data for user interactions, preferences,
and agent corrections. (Vector memory lives in ChromaDB, not here.)
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Integer, Text, DateTime, ForeignKey
from app.db.database import Base


class UserInteraction(Base):
    """Every meaningful user event — signal views, ticker searches, feedback, etc."""
    __tablename__ = "user_interactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    # Event types: SIGNAL_VIEW, SIGNAL_GENERATE, OUTCOME_MARK,
    #              TICKER_SEARCH, JOURNAL_NOTE, FEEDBACK_THUMBS,
    #              PROFILE_CHANGE, ALERT_CREATE, SESSION_START
    ticker = Column(String(20), nullable=True, index=True)
    signal_id = Column(String(36), nullable=True)
    payload = Column(Text, nullable=True)  # JSON: event-specific data
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)


class UserPreference(Base):
    """Materialized view of aggregated user behaviour, recomputed periodically."""
    __tablename__ = "user_preferences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True)
    favorite_tickers = Column(Text, nullable=True)       # JSON array, ordered by frequency
    favorite_asset_classes = Column(Text, nullable=True)  # JSON array
    avg_risk_tolerance = Column(Float, nullable=True)
    preferred_timeframe = Column(String(10), nullable=True)
    preferred_direction = Column(String(20), nullable=True)  # LONG-leaning, SHORT-leaning, NEUTRAL
    signal_count = Column(Integer, default=0)
    win_rate = Column(Float, nullable=True)
    avg_confidence_pref = Column(Float, nullable=True)
    last_computed = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class AgentCorrection(Base):
    """What an agent 'learned' from a past mistake — human-readable lesson."""
    __tablename__ = "agent_corrections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_name = Column(String(50), nullable=False, index=True)
    signal_id = Column(String(36), ForeignKey("signals.id"), nullable=True)
    correction_type = Column(String(50), nullable=False)
    # Types: OVERCONFIDENT, WRONG_DIRECTION, MISSED_RISK, REGIME_MISS, TIMING_ERROR
    lesson = Column(Text, nullable=False)  # natural language lesson
    ticker = Column(String(20), nullable=True)
    conditions_hash = Column(String(64), nullable=True)  # dedup key
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
