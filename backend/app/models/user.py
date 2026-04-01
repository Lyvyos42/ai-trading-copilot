import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, nullable=False, default="free")
    active_profile: Mapped[str] = mapped_column(String, nullable=False, default="balanced")
    stripe_customer_id: Mapped[str | None] = mapped_column(String, nullable=True, unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String, nullable=True)
    subscription_status: Mapped[str | None] = mapped_column(String, nullable=True, default="none")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
