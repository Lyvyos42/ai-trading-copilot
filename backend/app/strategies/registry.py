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

from app.strategies.artemis_squeeze import ArtemisSqueezeStrategy
from app.strategies.base import BaseStrategy
from app.strategies.crt import CRTStrategy
from app.strategies.donchian_fail import DonchianFailureStrategy
from app.strategies.fomc_drift import FOMCDriftStrategy
from app.strategies.ibs import IBSMeanReversionStrategy
from app.strategies.intraday_momentum import (
    IntradayMomentumStrategy, OpeningRangeBreakoutStrategy,
)
from app.strategies.meanrev import MeanReversionStrategy
from app.strategies.nr7 import NR7BreakoutStrategy
from app.strategies.orb_london import LondonORBStrategy
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
        basis=("Underpowered, not refuted - and the only candidate in this "
               "programme with NO decay. W1 reproduces across two instruments "
               "(+18.9bp t 1.88 on 99 IWM events, +20.6bp t 1.86 on 34 sp500) "
               "and the modern third is the STRONGEST era: 2018-2026 gives "
               "t +2.46 against -0.37 for 2011-2014, clearing the anti-decay "
               "gate that every other candidate failed. It fails the other two "
               "gates: the entire effect is the overnight leg (t 3.22), so the "
               "non-overnight portion returns t -0.26 against a required 2.00, "
               "and out-of-sample t is 1.32 against 2.96. The overlap gate "
               "fails in an informative direction - the effect concentrates "
               "BELOW the 200-day average (Welch 2.32, n=29) where "
               "overnight_drift is deliberately flat, so the two are disjoint "
               "rather than duplicative, matching Lucca and Moench on the "
               "drift being larger under uncertainty. 99 events, 29 of them in "
               "the regime that carries it. Needs an intraday SPY series back "
               "to 1993."),
    ),

    "crt": Registration(
        strategy=CRTStrategy,
        deployment=Deployment.GATED,
        instruments=("XAUUSD", "XAGUSD"),
        consensus_weight=0.0,
        basis=("Refuted against its own bias-matched control. 7557 trades "
               "across two specifications (4H->M15 over 4.2 years, 1H->M5 over "
               "17 months) and two metals. XAUUSD Spec B nets +0.021R at t 0.43 "
               "against a control of -0.024R - Welch +0.92. The validation "
               "symbol fails outright, t -3.83 and -4.75. Modern-third t is "
               "0.38 against a required 2.00 and shorts are negative, so "
               "directional symmetry fails too. The control did clear it of the "
               "beta charge: long share is 46-49% on every run, so gold's +141% "
               "drift is not flowing into the signal and the near-zero result is "
               "real. Structurally this is the Donchian failure trade at a "
               "different anchor, now refused on six instruments across three "
               "asset classes. Re-run under the 4-point microstructure protocol "
               "with the spread in the fills and the full 16-cell grid "
               "(sweep 0.10/0.25 x killzones on/off x two specs x two metals): "
               "zero cells clear the control at Welch 2.00, the best is +1.65, "
               "only three have positive expectancy at all and the largest is "
               "+0.016R. Silver is negative in all eight of its cells."),
    ),

    "artemis_squeeze": Registration(
        strategy=ArtemisSqueezeStrategy,
        deployment=Deployment.GATED,
        instruments=("XAUUSD", "XAGUSD"),
        consensus_weight=0.0,
        basis=("Underpowered on gold, refuted on silver. 30 cells over XAUUSD "
               "and XAGUSD H1, 99k bars each, 2009-2026. No cell passes all "
               "four gates. The best gold cell - pinch 12, ADX > 20, momentum "
               "cross exit - nets +0.231R at t 1.67 on n=91, and passes modern "
               "third (t 2.15) and directional symmetry (long +0.202R, short "
               "+0.256R) while failing out-of-sample (t 1.96 on 19 trades "
               "against a Bonferroni 3.21) and the control (Welch 1.51). The "
               "only two cells clearing the control at Welch 2.80 and 2.24 are "
               "silver cells netting -0.003R and -0.001R - they beat a control "
               "that loses -0.11R, which is not an edge but a demonstration "
               "that Welch must be read alongside the level. All 15 atr_trail "
               "cells are negative, to t -8.82 at n=973, on the same entries "
               "the momentum-cross exit takes to roughly zero: a 2-ATR trail "
               "on an H1 metal ratchets into noise. Two spec faults were fixed "
               "before the grid: the filed |slope| > 5.0 is absolute on a "
               "price-scaling quantity and fires on 0.1% of gold bars and 0.0% "
               "of silver, and ATR-normalising it must be calibrated on "
               "release bars rather than all bars. UNRESOLVED: this "
               "BB(20,2.0)/KC(20,1.5) construction finds 973 gold releases at "
               "pinch 6 against 2,316 reported by the collaborating scan, so "
               "the Keltner parameters under test differ and this verdict does "
               "not transfer to that construction."),
    ),

    "orb_london_0830": Registration(
        strategy=LondonORBStrategy,
        deployment=Deployment.GATED,
        instruments=("GBPUSD", "EURUSD"),
        consensus_weight=0.0,
        basis=("Refuted. 3,782 trades on GBPUSD M15 primary and EURUSD M15 "
               "validation, 1,033 sessions 2022-2026, at two target "
               "geometries. Zero of four cells pass the gates. The decisive "
               "measurement is gross versus net: with zero spread and zero "
               "commission on the same entries, expectancy is statistically "
               "nil in all four cells (best t 1.40), so there is no edge for "
               "the uniform 0.05-0.07R toll to consume and no execution "
               "improvement reaches a positive number. The filed measured-move "
               "target is a specification defect - risk is 1.32x the range "
               "height because the fill follows a close beyond the near edge "
               "while the stop sits at the far one, making a 1.0x-height "
               "target only 0.52R from entry, which needs a 66% win rate to "
               "break even and gets exactly 66%. All four cells land within "
               "three points of their arithmetic breakeven win rate. The one "
               "non-negative cell (GBPUSD 1:1.5, +0.002R) clears the control "
               "at Welch 2.10 only because the control loses -0.080R, the "
               "third time in this programme that gate has been satisfied by a "
               "strategy earning nothing. EURUSD is negative in both "
               "geometries to t -3.14. JPY controls could not be run at "
               "specification: no M15 export exists and an H1 bar cannot "
               "resolve an 08:30-08:45 range; at the 08:00 H1 anchor - a "
               "different hypothesis - all four cells are negative over 16 "
               "years and 9,665 trades. Also recorded: 56.4% of EURUSD "
               "entry-window bars quote spread=0, an export artefact floored "
               "at the non-zero median, without which the cost model would "
               "let half the sample trade free."),
    ),

    "meanrev": Registration(
        strategy=MeanReversionStrategy,
        deployment=Deployment.GATED,
        instruments=("EURUSD", "GBPUSD"),
        consensus_weight=0.0,
        basis=("Underpowered, not refuted - the strongest gated candidate in "
               "the programme. 3,450 trades over EURUSD H4 primary and GBPUSD "
               "H4 validation, 24,812 bars each, 2010-2026, across 8 cells. No "
               "cell passes all five gates. The pre-registered primary arm "
               "nets +0.112R on n=384 (+0.337 ATR/trade, reproducing the "
               "engine's filed +0.3175) and is the FIRST candidate to pass the "
               "amended control gate on merit: Welch +2.13 with a genuinely "
               "positive expectancy rather than a less-negative one. Era "
               "stability is the best seen here - +0.115/+0.131/+0.056/+0.135R "
               "over four eras, no decay - and the beta charge is disposed of, "
               "since the composite fires 192 long / 192 short and the matched "
               "control shows only a 0.024R short tilt across a sample where "
               "EURUSD went 1.3327 to 1.1626. It fails on power: OOS clustered "
               "t +1.69 against 2.96, modern third +1.76 against 2.00, and the "
               "validation pair fails the control gate at Welch +0.94 with a "
               "negative short leg. A stationary block bootstrap gives "
               "P(mean<=0) = 0.028 against an 8-cell Bonferroni bar of 0.006. "
               "MATERIAL CORRECTION TO THE PRIOR: the engine's clustered t "
               "figures (+3.42, +2.23, +1.82) are all monthly clustered and "
               "all inflated, because equal-weighting months changes the "
               "estimand - months with 1 trade return +0.928R against -0.239R "
               "for months with 4, monotonically, so the monthly average "
               "upweights the quiet months that carry the result and shifts "
               "+0.112R to +0.306R. The more extension signals fire in a "
               "month, the worse they do. The true prior is weaker than the "
               "record states. Also recorded: the filed 5-factor list does not "
               "match what meanrev_engine.py computes - only the Donchian term "
               "is close - and both were run, the filed list scoring worse on "
               "the primary. Promotion needs an independent sample, not "
               "another pass over these sixteen years."),
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
