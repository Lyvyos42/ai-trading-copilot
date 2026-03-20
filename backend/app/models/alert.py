import uuid
import json as _json
from datetime import datetime
from sqlalchemy import String, Float, Boolean, Integer, DateTime, ForeignKey, Text, func
from sqlalchemy.types import TypeDecorator, TEXT
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class JSONList(TypeDecorator):
    """Stores Python list as JSON text — works with SQLite and PostgreSQL."""
    impl = TEXT
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return _json.dumps(value) if value is not None else "[]"

    def process_result_value(self, value, dialect):
        if value:
            try:
                return _json.loads(value)
            except Exception:
                return []
        return []


class ScannerConfig(Base):
    """Per-user scanner configuration — opt-in, off by default."""
    __tablename__ = "scanner_configs"

    user_id:           Mapped[str]  = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    enabled:           Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    symbols:           Mapped[list] = mapped_column(JSONList, nullable=False, default=list)  # max 20
    max_concurrent:    Mapped[int]  = mapped_column(Integer, nullable=False, default=2)       # 1–5
    interval_minutes:  Mapped[int]  = mapped_column(Integer, nullable=False, default=30)      # 15|30|60
    last_scan_at:      Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at:        Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at:        Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class MarketAlert(Base):
    """An opportunity detected by the scanner for a specific user."""
    __tablename__ = "market_alerts"

    id:              Mapped[str]   = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id:         Mapped[str]   = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    ticker:          Mapped[str]   = mapped_column(String(20), nullable=False)
    direction:       Mapped[str]   = mapped_column(String(10), nullable=False)          # LONG | SHORT
    confidence:      Mapped[float] = mapped_column(Float, nullable=False)               # 0–100
    summary:         Mapped[str]   = mapped_column(Text, nullable=False)                # 1-sentence rationale
    entry_hint:      Mapped[float] = mapped_column(Float, nullable=False)               # live price at scan time
    read:            Mapped[bool]  = mapped_column(Boolean, nullable=False, default=False)
    created_at:      Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
