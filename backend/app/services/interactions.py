"""
User interaction tracking — fire-and-forget event capture.

Records every meaningful user action for the Memory Layer:
  - What signals they generate and view
  - What tickers they search
  - Their feedback (thumbs up/down)
  - Journal notes linked to signals
  - Session starts and profile changes
"""
import json
from datetime import datetime, timezone
from typing import Any
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import UserInteraction

log = structlog.get_logger()


async def track_event(
    db: AsyncSession,
    user_id: str,
    event_type: str,
    ticker: str | None = None,
    signal_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """
    Insert a user interaction event. Fire-and-forget — failures are logged
    but never propagate to the caller.
    """
    try:
        interaction = UserInteraction(
            user_id=user_id,
            event_type=event_type,
            ticker=ticker,
            signal_id=signal_id,
            payload=json.dumps(payload, default=str) if payload else None,
        )
        db.add(interaction)
        await db.commit()
    except Exception as exc:
        log.error("interaction_track_failed", event=event_type, error=str(exc))
        try:
            await db.rollback()
        except Exception:
            pass
