"""
Memory Layer API endpoints.

POST /api/v1/memory/track          — record user interaction event
GET  /api/v1/memory/preferences    — get computed user preferences
GET  /api/v1/memory/memories       — get user's stored memories (dashboard)
GET  /api/v1/memory/corrections    — get agent correction history
GET  /api/v1/memory/corrections/{agent} — corrections for specific agent
GET  /api/v1/memory/stats          — memory system stats
DELETE /api/v1/memory/{memory_id}  — delete a specific memory
POST /api/v1/memory/feedback       — thumbs up/down on a signal
"""
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import get_optional_user
from app.db.database import get_db
from app.models.memory import UserInteraction, UserPreference, AgentCorrection
from app.services.memory import memory_manager
from app.services.interactions import track_event

router = APIRouter(prefix="/api/v1/memory", tags=["memory"])


# ── Request schemas ──────────────────────────────────────────────────────────

class TrackRequest(BaseModel):
    event_type: str
    ticker: str | None = None
    signal_id: str | None = None
    payload: dict | None = None


class FeedbackRequest(BaseModel):
    signal_id: str
    ticker: str | None = None
    feedback: str  # "THUMBS_UP" or "THUMBS_DOWN"
    note: str | None = None


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/track", status_code=202)
async def track_interaction(
    body: TrackRequest,
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_optional_user),
):
    """Record a user interaction event (fire-and-forget)."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = user.get("sub") or user.get("id") or user.get("user_id") or ""
    await track_event(
        db=db,
        user_id=user_id,
        event_type=body.event_type,
        ticker=body.ticker,
        signal_id=body.signal_id,
        payload=body.payload,
    )
    return {"status": "accepted"}


@router.post("/feedback", status_code=202)
async def signal_feedback(
    body: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_optional_user),
):
    """Record thumbs up/down feedback on a signal and store as memory."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = user.get("sub") or user.get("id") or user.get("user_id") or ""

    # Track the interaction
    await track_event(
        db=db,
        user_id=user_id,
        event_type="FEEDBACK_THUMBS",
        ticker=body.ticker,
        signal_id=body.signal_id,
        payload={"feedback": body.feedback, "note": body.note},
    )

    # Store as a memory if there's a note
    if body.note:
        memory_text = (
            f"User gave {body.feedback} on {body.ticker or 'signal'}: {body.note}"
        )
        memory_manager.store_memory(
            user_id=user_id,
            memory=memory_text,
            memory_type="BEHAVIOURAL",
            importance="MEDIUM",
        )

    return {"status": "accepted"}


@router.get("/memories")
async def get_memories(
    user: dict | None = Depends(get_optional_user),
):
    """Get all stored memories for the authenticated user (memory dashboard)."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = user.get("sub") or user.get("id") or user.get("user_id") or ""
    memories = memory_manager.get_user_memories(user_id, limit=100)
    return {"memories": memories, "total": len(memories)}


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    user: dict | None = Depends(get_optional_user),
):
    """Delete a specific memory (user trust — they control their data)."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = user.get("sub") or user.get("id") or user.get("user_id") or ""
    success = memory_manager.delete_memory(user_id, memory_id)
    if not success:
        raise HTTPException(status_code=404, detail="Memory not found or not yours")
    return {"status": "deleted"}


@router.get("/preferences")
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_optional_user),
):
    """Get computed preferences for the authenticated user."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    user_id = user.get("sub") or user.get("id") or user.get("user_id") or ""
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user_id)
    )
    pref = result.scalar_one_or_none()
    if not pref:
        return {"preferences": None, "message": "No preferences computed yet. Keep using the platform!"}

    return {
        "preferences": {
            "favorite_tickers": json.loads(pref.favorite_tickers) if pref.favorite_tickers else [],
            "favorite_asset_classes": json.loads(pref.favorite_asset_classes) if pref.favorite_asset_classes else [],
            "avg_risk_tolerance": pref.avg_risk_tolerance,
            "preferred_timeframe": pref.preferred_timeframe,
            "preferred_direction": pref.preferred_direction,
            "signal_count": pref.signal_count,
            "win_rate": pref.win_rate,
            "avg_confidence_pref": pref.avg_confidence_pref,
            "last_computed": pref.last_computed.isoformat() if pref.last_computed else None,
        }
    }


@router.get("/corrections")
async def get_corrections(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_optional_user),
):
    """Get agent correction history (for performance page)."""
    result = await db.execute(
        select(AgentCorrection)
        .order_by(desc(AgentCorrection.created_at))
        .limit(min(limit, 200))
    )
    corrections = result.scalars().all()
    return {
        "corrections": [
            {
                "id": c.id,
                "agent_name": c.agent_name,
                "correction_type": c.correction_type,
                "lesson": c.lesson,
                "ticker": c.ticker,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in corrections
        ]
    }


@router.get("/corrections/{agent_name}")
async def get_agent_corrections(
    agent_name: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Get corrections for a specific agent."""
    result = await db.execute(
        select(AgentCorrection)
        .where(AgentCorrection.agent_name == agent_name)
        .order_by(desc(AgentCorrection.created_at))
        .limit(min(limit, 100))
    )
    corrections = result.scalars().all()
    return {
        "corrections": [
            {
                "id": c.id,
                "correction_type": c.correction_type,
                "lesson": c.lesson,
                "ticker": c.ticker,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in corrections
        ]
    }


@router.get("/stats")
async def memory_stats(
    db: AsyncSession = Depends(get_db),
    user: dict | None = Depends(get_optional_user),
):
    """Memory system stats."""
    user_id = (user.get("sub") or user.get("id") or user.get("user_id")) if user else None

    # DB counts
    interaction_count = 0
    correction_count = 0
    try:
        r1 = await db.execute(select(func.count()).select_from(AgentCorrection))
        correction_count = r1.scalar() or 0
        if user_id:
            r2 = await db.execute(
                select(func.count()).select_from(UserInteraction)
                .where(UserInteraction.user_id == user_id)
            )
            interaction_count = r2.scalar() or 0
    except Exception:
        pass

    # ChromaDB count
    memory_count = memory_manager.get_user_memory_count(user_id) if user_id else 0

    return {
        "memory_count": memory_count,
        "interaction_count": interaction_count,
        "correction_count": correction_count,
        "status": "active" if memory_count > 0 else "warming_up",
    }
