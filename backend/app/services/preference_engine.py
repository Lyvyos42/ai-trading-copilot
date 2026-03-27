"""
User Preference Engine — materializes aggregated user behaviour into
a structured profile that agents can use for personalization.

Recomputed on-demand (cached 1 hour) or via background scheduler.
"""
import json
from collections import Counter
from datetime import datetime, timezone
import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import UserInteraction, UserPreference
from app.models.signal import Signal

log = structlog.get_logger()


async def recompute_user_preferences(user_id: str, db: AsyncSession) -> dict | None:
    """
    Query user interactions and signals, then materialize into UserPreference.
    Returns the preference dict or None if insufficient data.
    """
    try:
        # ── Gather signal stats ────────────────────────────────────────────
        signals_result = await db.execute(
            select(Signal).where(Signal.user_id == user_id)
        )
        signals = signals_result.scalars().all()

        if len(signals) < 3:
            return None  # Not enough data

        # Ticker frequency
        ticker_counter = Counter(s.ticker for s in signals)
        favorite_tickers = [t for t, _ in ticker_counter.most_common(10)]

        # Asset class frequency
        ac_counter = Counter(s.asset_class for s in signals if s.asset_class)
        favorite_asset_classes = [ac for ac, _ in ac_counter.most_common(5)]

        # Direction lean
        long_count = sum(1 for s in signals if s.direction == "LONG")
        short_count = sum(1 for s in signals if s.direction == "SHORT")
        total = long_count + short_count
        if total > 0:
            long_pct = long_count / total
            if long_pct > 0.65:
                preferred_direction = "LONG-leaning"
            elif long_pct < 0.35:
                preferred_direction = "SHORT-leaning"
            else:
                preferred_direction = "NEUTRAL"
        else:
            preferred_direction = "NEUTRAL"

        # Timeframe preference
        tf_counter = Counter(s.timeframe for s in signals if s.timeframe)
        preferred_timeframe = tf_counter.most_common(1)[0][0] if tf_counter else "1D"

        # Win rate
        resolved = [s for s in signals if s.outcome in ("WIN", "LOSS")]
        wins = sum(1 for s in resolved if s.outcome == "WIN")
        win_rate = round(wins / len(resolved), 3) if resolved else None

        # Average confidence of signals they generate
        confidences = [s.confidence_score for s in signals if s.confidence_score]
        avg_confidence = round(sum(confidences) / len(confidences), 1) if confidences else None

        # Risk tolerance (derived from average PnL of losses)
        losses = [s for s in resolved if s.outcome == "LOSS" and s.pnl_pct is not None]
        avg_loss = round(sum(s.pnl_pct for s in losses) / len(losses), 2) if losses else None

        # ── Gather interaction stats ───────────────────────────────────────
        interaction_count = 0
        try:
            r = await db.execute(
                select(func.count()).select_from(UserInteraction)
                .where(UserInteraction.user_id == user_id)
            )
            interaction_count = r.scalar() or 0
        except Exception:
            pass

        # ── Upsert into UserPreference ─────────────────────────────────────
        now = datetime.utcnow()
        result = await db.execute(
            select(UserPreference).where(UserPreference.user_id == user_id)
        )
        pref = result.scalar_one_or_none()

        pref_data = {
            "favorite_tickers": json.dumps(favorite_tickers),
            "favorite_asset_classes": json.dumps(favorite_asset_classes),
            "avg_risk_tolerance": avg_loss,
            "preferred_timeframe": preferred_timeframe,
            "preferred_direction": preferred_direction,
            "signal_count": len(signals),
            "win_rate": win_rate,
            "avg_confidence_pref": avg_confidence,
            "last_computed": now,
        }

        if pref:
            for k, v in pref_data.items():
                setattr(pref, k, v)
        else:
            pref = UserPreference(user_id=user_id, **pref_data)
            db.add(pref)

        await db.commit()

        log.info("preferences_recomputed", user_id=user_id[:8],
                 signals=len(signals), win_rate=win_rate)

        return {
            "favorite_tickers": favorite_tickers,
            "favorite_asset_classes": favorite_asset_classes,
            "preferred_direction": preferred_direction,
            "preferred_timeframe": preferred_timeframe,
            "signal_count": len(signals),
            "win_rate": win_rate,
            "avg_confidence_pref": avg_confidence,
        }

    except Exception as exc:
        log.error("preference_compute_failed", user_id=user_id[:8], error=str(exc))
        return None
