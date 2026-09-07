"""Which strategies are deployed, where, and on what evidence.

WHY DEPLOYMENT STATE IS DATA AND NOT A COMMENT

Four strategies, four different answers, and the answers are per instrument.
Overnight drift is live; intraday momentum is refuted; the opening range
breakout measures well in sample and does not clear the bar out of it; PEAD
has no data source connected. Holding that in anyone's head is how a refuted
strategy ends up voting.

Each entry carries the measurement that put it in its state. When someone
proposes promoting one, the argument has to engage with the number in the
record rather than with a recollection of it.

WHY OBSERVER IS A SEPARATE MODE AND NOT A WEIGHT OF ZERO

An observer could be implemented as a vote with confidence 0.0, and the
consensus tally already skips those. That is one edit away from voting: a
later change to the weighting, or a well-meaning normalisation, and a
strategy nobody validated is contributing to a published number.

Observers are therefore never added to the vote list at all. They are
computed, returned in their own block, and logged for forward tracking. The
tally cannot include them because it never sees them.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from app.strategies.base import BaseStrategy
from app.strategies.intraday_momentum import (
    IntradayMomentumStrategy, OpeningRangeBreakoutStrategy,
)
from app.strategies.overnight_drift import OvernightDriftStrategy
from app.strategies.pead import PEADTimeScreener
from app.strategies.vwap_bands import InstitutionalVWAPStrategy


class Deployment(str, Enum):
    LIVE = "live"          # contributes to the consensus score
    OBSERVER = "observer"  # computed and logged, contributes nothing
    GATED = "gated"        # not computed at all


@dataclass(frozen=True)
class Registration:
    strategy: type[BaseStrategy]
    deployment: Deployment
    # Instruments this is deployed on. Empty means every instrument the
    # strategy itself accepts. An instrument absent from a non-empty list is
    # GATED regardless of the mode above.
    instruments: tuple[str, ...] = ()
    consensus_weight: float = 0.0
    # The measurement behind the state. Shown in the API response so a reader
    # can see why a strategy is or is not counting.
    basis: str = ""
    params: dict = field(default_factory=dict)

    def applies_to(self, symbol: str) -> bool:
        if not self.instruments:
            return True
        return symbol.upper().replace("=F", "").replace("=X", "") in self.instruments


# Symbols are compared with =F / =X stripped, so ES matches ES=F.
REGISTRY: dict[str, Registration] = {
    "overnight_drift": Registration(
        strategy=OvernightDriftStrategy,
        deployment=Deployment.LIVE,
        instruments=("SPY", "QQQ", "ES", "NQ", "MES", "MNQ"),
        consensus_weight=0.6,
        basis=("8457 SPY and 6913 QQQ sessions. Filtered: Sharpe 0.90/1.09, "
               "maxDD -17.4%/-15.4%, Sharpe retention 1.00/0.96 out of sample. "
               "OOS t 2.36/2.47 against a 2.73 threshold - below it, but the "
               "retention and the 30-year prior carry it. Sized at one micro "
               "per 100k and gated on the funding plan permitting the hold."),
        params={"require_regime": True},
    ),

    "intraday_momentum": Registration(
        strategy=IntradayMomentumStrategy,
        deployment=Deployment.GATED,
        consensus_weight=0.0,
        basis=("REFUTED on 3629 sessions of true M30 windows. Correlation "
               "between the 09:30-10:00 and 15:30-16:00 returns is NEGATIVE on "
               "all three series with 1000+ sessions (-0.040, -0.027, -0.053). "
               "The sign trade returns t between -1.20 and +0.25 against 2.96. "
               "Not to be promoted without a new sample that says otherwise."),
    ),

    "opening_range_breakout": Registration(
        strategy=OpeningRangeBreakoutStrategy,
        deployment=Deployment.OBSERVER,
        instruments=("SP500", "SPX", "ES", "SPY"),
        consensus_weight=0.0,
        basis=("Real in sample, unproven out of it. 926 sp500 trades: win "
               "36.8%, expectancy +0.500R, PF 1.81, t +6.08. Out of sample "
               "t 2.23 (sp500) and 1.87 (spy) against a 2.96 threshold, with "
               "Sharpe retention 0.79 and 1.28. nasdaq retains 0.43 and us30 "
               "0.61, so neither is deployed even as an observer. Fill "
               "friction is not the obstacle: a median tick jump is 2.2% of R "
               "on sp500 and 1.7% on spy. Forward tracking decides promotion."),
        params={"require_gap_alignment": False, "require_validation": False},
    ),

    "institutional_vwap": Registration(
        strategy=InstitutionalVWAPStrategy,
        deployment=Deployment.LIVE,
        instruments=("ES", "NQ", "SPY", "QQQ", "MES", "MNQ", "6E", "6B", "6J"),
        consensus_weight=0.5,
        basis=("Deployed on the traded-volume allowlist only. Not backtested "
               "in this project - it is an execution benchmark rather than an "
               "anomaly, and its value is the reference level, not a directional "
               "claim. Its weight reflects that."),
    ),

    "pead_time_sue": Registration(
        strategy=PEADTimeScreener,
        deployment=Deployment.GATED,
        consensus_weight=0.0,
        basis=("No data source connected. FINNHUB_API_KEY is unset, so no "
               "earnings history has been fetched and no study has been run. "
               "Promotion requires the key AND a study, in that order."),
    ),
}


def live(symbol: str) -> list[tuple[str, Registration]]:
    return [(k, r) for k, r in REGISTRY.items()
            if r.deployment is Deployment.LIVE and r.applies_to(symbol)]


def observers(symbol: str) -> list[tuple[str, Registration]]:
    return [(k, r) for k, r in REGISTRY.items()
            if r.deployment is Deployment.OBSERVER and r.applies_to(symbol)]


def build(name: str) -> BaseStrategy:
    reg = REGISTRY[name]
    return reg.strategy(**reg.params)


def status() -> list[dict]:
    """The whole deployment table, for the API and for a human reading it."""
    return [{
        "strategy": k,
        "deployment": r.deployment.value,
        "instruments": list(r.instruments) or ["(any the strategy accepts)"],
        "consensus_weight": r.consensus_weight,
        "basis": r.basis,
    } for k, r in REGISTRY.items()]
