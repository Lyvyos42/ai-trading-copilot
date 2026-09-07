"""Bridge between the quantitative strategies and the 9-agent consensus.

WHAT THIS RETURNS AND WHY IT IS SHAPED THIS WAY

Two separate blocks, never merged:

    votes[]      - LIVE strategies only, as (direction, confidence) pairs the
                   trader can fold into its tally
    observations[] - OBSERVER strategies, with their signals in full and a
                   consensus_weight of 0.0, for logging and forward tracking

The separation is the point. An observer expressed as a zero-weight vote sits
one edit away from counting; an observer that is never put in the vote list
cannot be counted by a tally that never receives it.

ABSTENTIONS ARE RETURNED, NOT DROPPED

A strategy that could not run returns its reason and appears in
`abstentions[]`. It contributes nothing to the tally - not a neutral vote, not
a 50% - because "I could not look" and "I looked and see nothing" are
different statements and averaging the first into a consensus drags every
other agent toward the middle. The reasons are surfaced so a user reading a
51% confidence can see that four of the panel had no data rather than
disagreeing.
"""
from __future__ import annotations

from typing import Any, Optional, Sequence

import structlog

from app.strategies import registry
from app.strategies.base import BarSeries, Direction, SignalResult

log = structlog.get_logger()


def _vote_confidence(result: SignalResult, weight: float) -> float:
    """Confidence a live strategy contributes, scaled by its registered weight.

    The strategy's own conviction is a size hint on its own terms; the weight
    is how much this project trusts the strategy. Multiplying keeps the two
    judgements separate and visible.
    """
    return max(0.0, min(1.0, result.conviction)) * max(0.0, weight)


def evaluate_symbol(symbol: str, bars: BarSeries) -> dict[str, Any]:
    """Run every registered strategy that applies to `symbol`.

    `bars` must be the interval the strategies expect - daily for overnight
    drift, intraday for the rest. A caller with only one interval will get
    honest abstentions from the strategies that needed the other, which is the
    correct outcome rather than a reason to pass the wrong bars.
    """
    votes: list[tuple[str, float]] = []
    contributions: list[dict] = []
    observations: list[dict] = []
    abstentions: list[dict] = []

    for name, reg in registry.live(symbol):
        try:
            result = registry.build(name).generate_signals(bars)
        except Exception as exc:
            log.warning("strategy_failed", strategy=name, symbol=symbol,
                        error=f"{type(exc).__name__}: {exc}")
            abstentions.append({"strategy": name, "reason":
                                f"raised {type(exc).__name__}: {exc}"})
            continue

        if result.abstained:
            abstentions.append({"strategy": name, "reason": result.reason})
            continue
        if result.direction is Direction.FLAT:
            contributions.append({**result.to_dict(),
                                  "consensus_weight": reg.consensus_weight,
                                  "counted": False})
            continue

        conf = _vote_confidence(result, reg.consensus_weight)
        if conf <= 0:
            contributions.append({**result.to_dict(),
                                  "consensus_weight": reg.consensus_weight,
                                  "counted": False})
            continue

        votes.append((result.direction.value, conf))
        contributions.append({**result.to_dict(),
                              "consensus_weight": reg.consensus_weight,
                              "vote_confidence": round(conf, 4),
                              "counted": True})

    for name, reg in registry.observers(symbol):
        try:
            result = registry.build(name).generate_signals(bars)
        except Exception as exc:
            log.warning("observer_failed", strategy=name, symbol=symbol,
                        error=f"{type(exc).__name__}: {exc}")
            continue
        # Recorded whatever it says, including FLAT and abstain. The point of
        # an observer is the record, and a record with the quiet days removed
        # would overstate how often it has an opinion.
        observations.append({
            **result.to_dict(),
            "consensus_weight": 0.0,
            "counted": False,
            "deployment": "observer",
            "basis": reg.basis,
        })
        log.info("strategy_observation", strategy=name, symbol=symbol,
                 direction=result.direction.value, abstained=result.abstained,
                 conviction=round(result.conviction, 4),
                 entry=result.entry, stop=result.stop,
                 time_exit_utc=result.time_exit_utc, reason=result.reason)

    return {
        "symbol": symbol,
        "votes": votes,
        "contributions": contributions,
        "observations": observations,
        "abstentions": abstentions,
        # So a reader can tell a thin panel from a disagreeing one.
        "counted": len(votes),
        "abstained": len(abstentions),
    }


def merge_into_votes(existing: list[tuple[str, float]],
                     strategy_block: dict) -> list[tuple[str, float]]:
    """Append the LIVE strategy votes to the agent tally.

    Only `votes` is read. `observations` is deliberately not reachable from
    here: there is no argument this function could be passed that would make
    an observer count.
    """
    return list(existing) + list(strategy_block.get("votes") or [])
