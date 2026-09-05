"""Record EVERY pipeline decision, whatever it decided.

There are two entry points that run the pipeline - POST /signals/generate and
the auto-scanner - and until now only the tradeable results left any trace.
A signal engine cannot be evaluated from its successes alone: the questions
that matter after a change are how often it declines, which analysts abstain
on which asset classes, whether two symbols are producing identical votes, and
whether a change raised the signal rate or merely moved a threshold. None of
those are answerable from a table of accepted signals.

This writes one row per run to `signal_decisions`, separate from the product
surface, so the audit trail cannot refill Signal History or contaminate the
track record - which is what happened the last time rejections were persisted.

Writing is best-effort by design: a failure to record an observation must
never fail the observation itself.
"""
import structlog

log = structlog.get_logger()

_ANALYSTS = [
    ("fundamental_analysis", "fundamental"),
    ("technical_analysis", "technical"),
    ("sentiment_analysis", "sentiment"),
    ("macro_analysis", "macro"),
    ("order_flow_analysis", "order_flow"),
    ("regime_change_analysis", "regime_change"),
    ("correlation_analysis", "correlation"),
]


def summarise_votes(state: dict) -> tuple[dict, list, int]:
    """(votes, abstained, directional_count) from a finished pipeline state."""
    votes: dict = {}
    abstained: list = []
    directional = 0
    for key, label in _ANALYSTS:
        a = state.get(key) or {}
        if a.get("abstained"):
            abstained.append(label)
            votes[label] = {"direction": None, "confidence": 0.0, "abstained": True}
            continue
        d = a.get("direction")
        c = a.get("confidence")
        # symbol_specific False means the opinion was formed without looking at
        # THIS instrument - the market-wide news pool. Recorded because it is
        # the difference between seven opinions and five opinions plus one
        # shared view counted twice.
        votes[label] = {
            "direction": d,
            "confidence": c,
            "symbol_specific": a.get("symbol_specific", True),
        }
        if d in ("LONG", "SHORT") and (c or 0) > 0:
            directional += 1
    return votes, abstained, directional


async def record(
    db,
    *,
    state: dict,
    final: dict,
    ticker: str,
    asset_class: str | None = None,
    timeframe: str | None = None,
    profile: str | None = None,
    origin: str = "manual",
    user_id: str | None = None,
    signal_id: str | None = None,
) -> None:
    """Append one decision row. Never raises."""
    try:
        from app.models.signal import SignalDecision

        votes, abstained, directional = summarise_votes(state)
        md = state.get("market_data") or {}
        row = SignalDecision(
            user_id=user_id,
            ticker=ticker,
            asset_class=asset_class,
            timeframe=timeframe,
            profile=profile,
            origin=origin,
            status=final.get("status") or "ACTIVE",
            direction=final.get("direction"),
            probability_score=final.get("probability_score"),
            confidence_score=final.get("confidence_score"),
            agent_votes=votes,
            abstained=abstained,
            directional_votes=directional,
            status_reasons=(final.get("status_reasons")
                            or final.get("risk_gate_reasons") or []),
            degraded_sources=state.get("degraded_sources") or [],
            data_source=md.get("data_source"),
            signal_id=signal_id,
            entry_price=final.get("entry_price"),
            latency_ms=state.get("pipeline_latency_ms"),
        )
        db.add(row)
        await db.commit()
    except Exception as exc:
        # A failure to record an observation must never fail the observation.
        try:
            await db.rollback()
        except Exception:
            pass
        log.warning("decision_log_failed", ticker=ticker,
                    error=f"{type(exc).__name__}: {exc}")
