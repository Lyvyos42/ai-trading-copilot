import uuid
import json as _json
from datetime import datetime, timedelta
from sqlalchemy import String, Float, DateTime, func, ForeignKey, Text
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
        if value:
            try:
                return _json.loads(value)
            except Exception:
                return {}
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
    status: Mapped[str] = mapped_column(String, nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    expiry_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
