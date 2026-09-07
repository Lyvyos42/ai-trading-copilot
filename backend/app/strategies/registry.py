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
from app.strategies.donchian_fail import DonchianFailureStrategy
from app.strategies.fomc_drift import FOMCDriftStrategy
from app.strategies.ibs import IBSMeanReversionStrategy
from app.strategies.intraday_momentum import (
    IntradayMomentumStrategy, OpeningRangeBreakoutStrategy,
)
from app.strategies.nr7 import NR7BreakoutStrategy
from app.strategies.overnight_drift import OvernightDriftStrategy
from app.strategies.pead import PEADTimeScreener
from app.strategies.turn_of_month import TurnOfMonthStrategy
from app.strategies.vp_auction import VolumeProfileAuctionStrategy
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
    # Strategies that make the SAME trade. Two entries naming each other must
    # never both be LIVE: the consensus would count one edge twice and report
    # a conviction it has not earned. Enforced by check_exclusions().
    excludes: tuple[str, ...] = ()
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
        instruments=("SPY",),
        consensus_weight=0.0,
        basis=("SPY only, after costs. The earlier deployment included sp500 "
               "on a GROSS result; charging the spread quoted on the entry bar "
               "changes it. sp500 pays 0.299R per trade - its opening range is "
               "9.1 index points and the cash-session spread is 2.0 - which "
               "takes +0.500R to +0.201R and collapses out-of-sample retention "
               "from 0.79 to 0.15. spy pays 0.032R and keeps +0.316R at t "
               "+3.11, OOS Sharpe 2.72, retention 1.31. nasdaq nets +0.301R "
               "but retains 0.31; us30 0.17; qqq is negative on 100 trades. "
               "Tick jump was measured earlier and is small (2.2% of R); the "
               "SPREAD was not, and it is the larger cost."),
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

    "ibs_mean_reversion": Registration(
        strategy=IBSMeanReversionStrategy,
        deployment=Deployment.GATED,
        consensus_weight=0.0,
        excludes=("overnight_drift",),
        basis=("Discriminates, but it is the same trade. With the regime "
               "filter applied to both groups, sp500 sessions closing below "
               "IBS 0.2 return +17.8bp overnight against +0.6bp for the rest - "
               "Welch t 3.01 over 833 observations. The intraday leg separates "
               "at t 0.18, so the whole effect is overnight, which is what "
               "overnight_drift already trades. Standalone OOS t is 1.82-2.18 "
               "against 3.08 on only 154-218 qualifying sessions. Deployed as "
               "the ibs_max parameter of OvernightDriftStrategy, not as a "
               "second voter."),
    ),

    "vp_auction": Registration(
        strategy=VolumeProfileAuctionStrategy,
        deployment=Deployment.GATED,
        instruments=("SPY", "QQQ", "IWM"),
        consensus_weight=0.0,
        basis=("Rules not supported, now on two instruments. The 80% rule "
               "measures 60.0% on 493 SPY sessions (100 setups, base rate "
               "54.6%, z +0.94) and 52.5% on 3818 IWM sessions (871 setups, "
               "base rate 53.5%, z -0.50). On the larger sample the setup "
               "traverses slightly LESS often than an arbitrary entry inside "
               "the value area, so the SPY figure was the high end of noise. "
               "Traded on SPY: rejection -0.023R (t -0.25), acceptance -0.038R "
               "and degrading as confirmation is added. build_profile() and "
               "value_area() are retained for reference levels; it is the "
               "auction rules that failed, not the construct."),
    ),

    "nr7_breakout": Registration(
        strategy=NR7BreakoutStrategy,
        deployment=Deployment.GATED,
        consensus_weight=0.0,
        basis=("Pre-registered and refuted. 540 qualifying sessions across "
               "five instruments, two stop variants. Best full-sample t is "
               "1.38 against a 2.96 hurdle - it does not clear IN sample - and "
               "out-of-sample Sharpe retention is NEGATIVE on three of four "
               "variants. Gross expectancy is +0.04R to +0.21R, so costs are "
               "not the explanation. Volatility clustering is real; the "
               "DIRECTION of the expansion being predictable from the opening "
               "range is the claim that failed."),
    ),

    "turn_of_month": Registration(
        strategy=TurnOfMonthStrategy,
        deployment=Deployment.GATED,
        instruments=("SPY", "QQQ", "ES", "NQ"),
        consensus_weight=0.0,
        basis=("Real, and decayed. 296 SPY blocks 1993-2026 return +0.373% "
               "against +0.105% for every other 4-session block, Welch t 2.81. "
               "The edge is in the INTRADAY legs (Welch 2.74) not the overnight "
               "ones (1.13), so it would not duplicate overnight_drift. But it "
               "fades by era: Welch 2.96 in 1993-2004, 1.40 in 2005-2015, 0.51 "
               "in 2016-2026. Pre-registered split gives out-of-sample t 0.98 "
               "and retention 0.54 against a 2.96 / 0.70 hurdle. Lakonishok & "
               "Smidt published in 1988; the decay is the ordinary fate of a "
               "documented anomaly."),
    ),

    "donchian_fail": Registration(
        strategy=DonchianFailureStrategy,
        deployment=Deployment.GATED,
        instruments=("SPY", "IWM"),
        consensus_weight=0.0,
        basis=("Refuted on 15 years of IWM, having looked like the strongest "
               "candidate in the programme on 2 years of SPY. 1318 IWM trades "
               "give t 1.83 and out-of-sample retention of -0.13: the holdout "
               "lost money. By era, t +3.69 in 2011-2015, +0.28 in 2016-2020, "
               "-0.68 in 2021-2026. SPY's +0.354R at t 2.40 with retention "
               "0.99 was 184 trades measured inside the dead era. More data "
               "reversed the verdict - the retention statistic was not wrong, "
               "it was computed over a window too short to contain the decay. "
               "Separately the CFD cost wall stands: sp500 pays 0.70R in the "
               "cash session against a gross edge of +0.021R."),
    ),

    "fomc_drift": Registration(
        strategy=FOMCDriftStrategy,
        deployment=Deployment.GATED,
        instruments=("SPY", "IWM", "QQQ"),
        consensus_weight=0.0,
        basis=("Study BLOCKED, not concluded. The event file drops every "
               "projection-month meeting from 2021 - 8% of rows fall in "
               "Mar/Jun/Sep/Dec against a true 50% - which removes exactly the "
               "high-information events and lands on the 2018-2026 window the "
               "modern-third gate tests. Separately, SPY exists here only as "
               "daily bars and cannot resolve a 14:00 boundary, so neither "
               "pre-registered window is computable on the primary universe. "
               "On what does run - IWM M30 2011-2019, 69 events - W1 gives "
               "t +0.33 and W2 t -0.76, indistinguishable from the same hours "
               "on an ordinary day. The SPY overnight leg, a subset the spec "
               "did not ask for, gives Welch +1.84 over 216 events, "
               "concentrated in 2002-2010. Nothing clears any gate and nothing "
               "is refuted."),
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


def check_exclusions() -> list[str]:
    """Pairs that would double-count one edge if both went live.

    Called at import so a registry edit that puts two voters on the same trade
    fails immediately, rather than quietly inflating consensus confidence on
    exactly the setups where both fire - which is the worst place for it,
    because those are the ones that reach the user.
    """
    problems = []
    for name, reg in REGISTRY.items():
        if reg.deployment is not Deployment.LIVE:
            continue
        for other in reg.excludes:
            o = REGISTRY.get(other)
            if o is not None and o.deployment is Deployment.LIVE:
                problems.append(
                    f"{name} and {other} are both LIVE but make the same "
                    f"trade; the consensus would count it twice")
    return problems


_conflicts = check_exclusions()
if _conflicts:
    raise RuntimeError("strategy registry: " + "; ".join(_conflicts))


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
