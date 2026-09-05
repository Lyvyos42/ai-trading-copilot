import uuid
import json as _json
from datetime import datetime, timedelta
from sqlalchemy import String, Float, Integer, DateTime, func, ForeignKey, Text
from sqlalchemy.types import TypeDecorator, TEXT
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class JSONEncodedValue(TypeDecorator):
    """Stores Python dict/list as JSON text — works with SQLite and PostgreSQL."""
    impl = TEXT
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return _json.dumps(value) if value is not None else "{}"

    def process_result_value(self, value, dialect):
        if value is None or value == "":
            return {}
        try:
            return _json.loads(value)
        except Exception:
            return {}


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    ticker: Mapped[str] = mapped_column(String, nullable=False, index=True)
    asset_class: Mapped[str] = mapped_column(String, nullable=False, default="stocks")
    timeframe: Mapped[str] = mapped_column(String, nullable=False, default="1D")
    direction: Mapped[str] = mapped_column(String, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit_1: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit_2: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit_3: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    agent_votes: Mapped[dict] = mapped_column(JSONEncodedValue, nullable=False, default=dict)
    reasoning_chain: Mapped[list] = mapped_column(JSONEncodedValue, nullable=False, default=list)
    strategy_sources: Mapped[list] = mapped_column(JSONEncodedValue, nullable=False, default=list)
    timeframe_levels: Mapped[dict] = mapped_column(JSONEncodedValue, nullable=True, default=dict)
    status: Mapped[str] = mapped_column(String, nullable=False, default="ACTIVE")
    outcome: Mapped[str | None] = mapped_column(String, nullable=True)  # WIN, LOSS, EXPIRED
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_favorable_excursion: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_adverse_excursion: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Probability model fields (Phase 5B)
    probability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    bullish_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    bearish_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    research_target: Mapped[float | None] = mapped_column(Float, nullable=True)
    invalidation_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    risk_reward_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    analytical_window: Mapped[str | None] = mapped_column(String, nullable=True)
    bull_case: Mapped[str | None] = mapped_column(Text, nullable=True)
    bear_case: Mapped[str | None] = mapped_column(Text, nullable=True)
    conviction_tier: Mapped[str | None] = mapped_column(String, nullable=True)
    signal_mode: Mapped[str | None] = mapped_column(String(20), nullable=True, default="AI")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    expiry_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SignalDecision(Base):
    """EVERY pipeline run, including the ones that produced no signal.

    The Signal table deliberately holds only tradeable results: rejections
    used to be written there and refilled Signal History within a minute of
    any RESET, which is why persisting them was removed.

    But that left no record of the decisions themselves, and a signal engine
    cannot be evaluated from its successes alone. How often does it decline?
    Which analysts abstain, on which asset classes? Did a change raise the
    signal rate or just move the threshold? Are two symbols producing
    identical votes? None of that is answerable from a table of accepted
    signals.

    So this is the AUDIT LOG, separate from the product surface. It is
    append-only, never shown to users, and never counted in the track record.
    One row per pipeline run, whatever the outcome.
    """
    __tablename__ = "signal_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)

    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    asset_class: Mapped[str | None] = mapped_column(String(30), nullable=True)
    timeframe: Mapped[str | None] = mapped_column(String(10), nullable=True)
    profile: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # "manual" (a user pressed Analyze) or "auto_scan"
    origin: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)

    # What came out. status is NO_SIGNAL, FILTERED, RISK_GATE_BLOCKED or ACTIVE.
    status: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    direction: Mapped[str | None] = mapped_column(String(10), nullable=True)
    probability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # How the decision was reached: every analyst's direction and confidence,
    # who abstained, how many formed a directional view, and which optional
    # data sources were unavailable for this run.
    agent_votes: Mapped[dict] = mapped_column(JSONEncodedValue, nullable=False, default=dict)
    abstained: Mapped[list] = mapped_column(JSONEncodedValue, nullable=False, default=list)
    directional_votes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status_reasons: Mapped[list] = mapped_column(JSONEncodedValue, nullable=False, default=list)
    degraded_sources: Mapped[list] = mapped_column(JSONEncodedValue, nullable=False, default=list)
    data_source: Mapped[str | None] = mapped_column(String(40), nullable=True)

    # Set only when the run produced a tradeable signal, so a decision can be
    # joined to its eventual outcome.
    signal_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    entry_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
