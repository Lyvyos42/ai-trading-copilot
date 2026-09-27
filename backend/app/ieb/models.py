"""
Canonical records for signals that come from IEB (the local MT5 engine).

    ieb_signals      one row per signal, keyed by the signal_id IEB generated. Immutable once written:
                     a second delivery of the same id is a duplicate, never a second signal. The
                     outcome columns are filled once, by IEB, when the signal resolves.
    ieb_executions   what a particular execution of a signal produced (paper, demo, later live),
                     keyed by execution_id. Kept apart from the signal: signal quality and execution
                     economics are different measurements.
    ieb_instances    health and configuration of each IEB installation (heartbeats, last errors, the
                     configuration Copilot hands back on each heartbeat).
    signal_modules   the module registry, one row per (module_id, version). Versions are never
                     overwritten; a new version is a new row.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.signal import JSONEncodedValue


class IebSignal(Base):
    __tablename__ = "ieb_signals"

    signal_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    instance_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    module_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    module_version: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    signal_version: Mapped[str] = mapped_column(String(64), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    timeframe: Mapped[str | None] = mapped_column(String(16), nullable=True)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    # IEB rule modules produce no consensus score; the field stays empty rather than invented.
    consensus_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    historical_outcome_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    outcome_rate_sample: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outcome_rate_definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    entry_reference: Mapped[float] = mapped_column(Float, nullable=False)
    entry_basis: Mapped[str | None] = mapped_column(String(40), nullable=True)
    stop_reference: Mapped[float | None] = mapped_column(Float, nullable=True)
    tp1: Mapped[float | None] = mapped_column(Float, nullable=True)
    tp2: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_horizon: Mapped[str | None] = mapped_column(String(160), nullable=True)
    market_state: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session: Mapped[str | None] = mapped_column(String(16), nullable=True)
    context: Mapped[dict] = mapped_column(JSONEncodedValue, nullable=False, default=dict)
    invalidation: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    extras: Mapped[dict] = mapped_column(JSONEncodedValue, nullable=False, default=dict)
    received_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    telegram_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    telegram_outcome_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # outcome, written once by IEB at the module's own prices (signal layer, no costs)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exit_reason: Mapped[str | None] = mapped_column(String(16), nullable=True)
    exit_reference: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    mfe_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    mae_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    holding_minutes: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    stop_hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    direction_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    outcome_received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class IebExecution(Base):
    __tablename__ = "ieb_executions"

    execution_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    signal_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    instance_id: Mapped[str] = mapped_column(String(64), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    account_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)   # a hash, never a login
    entry: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop: Mapped[float | None] = mapped_column(Float, nullable=True)
    target: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    mae: Mapped[float | None] = mapped_column(Float, nullable=True)
    mfe: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    execution_profile: Mapped[str | None] = mapped_column(String(64), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class IebInstance(Base):
    __tablename__ = "ieb_instances"

    instance_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_signal_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_request_ok_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_auth_failure_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    backlog: Mapped[dict] = mapped_column(JSONEncodedValue, nullable=False, default=dict)
    # switched off on purpose in IEB (its COPILOT header switch): shown as PAUSED, not OFFLINE
    paused: Mapped[bool | None] = mapped_column(Boolean, nullable=True, default=False)
    modules_active: Mapped[list] = mapped_column(JSONEncodedValue, nullable=False, default=list)
    # Copilot -> IEB: handed back on every heartbeat. IEB records it; the local instance stays the
    # execution authority and acts on nothing here until that is built and switched on explicitly.
    config: Mapped[dict] = mapped_column(JSONEncodedValue, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SignalModule(Base):
    __tablename__ = "signal_modules"

    module_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)          # ieb | copilot
    module_name: Mapped[str] = mapped_column(String(120), nullable=False)
    module_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)          # LIVE BETA SHADOW RESEARCH PAUSED DISABLED RETIRED
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    timeframes: Mapped[list] = mapped_column(JSONEncodedValue, nullable=False, default=list)
    symbols: Mapped[list] = mapped_column(JSONEncodedValue, nullable=False, default=list)
    signal_logic_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    score_definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome_definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameters: Mapped[dict] = mapped_column(JSONEncodedValue, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
