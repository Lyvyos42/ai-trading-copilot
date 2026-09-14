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
from app.strategies.cme_rebal_flow import CMERebalFlowStrategy
from app.strategies.consensus_9 import Consensus9Strategy
from app.strategies.crt import CRTStrategy
from app.strategies.decasteljau import DecasteljauStrategy
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
from app.strategies.postfix_reversion import PostFixReversionStrategy
from app.strategies.pead import PEADTimeScreener
from app.strategies.ten_am_macro import TenAMMacroStrategy
from app.strategies.tsmom import TSMomentumStrategy
from app.strategies.turn_of_month import TurnOfMonthStrategy
from app.strategies.vp_auction import VolumeProfileAuctionStrategy
from app.strategies.vpa_smc import VPASMCStrategy
from app.strategies.wmr_month_end import WMRMonthEndStrategy
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
               "per 100k and gated on the funding plan permitting the hold. "
               "IBS gate audit (IBS_GATE_01, 7786 sessions): In-sample 1993-2016 "
               "+4.68 bp (t +2.11); OOS 2017-2023 -1.19 bp (t -0.26, sign inverted). "
               "Retained per §8 as live condition."),
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
        instruments=("ES", "NQ", "SPY", "QQQ", "MES", "MNQ", "US30", "YM", "MYM",
                     "6E", "6B", "6J"),
        consensus_weight=0.5,
        basis=("Rule ported 2026-09-13 from Institutional Edge "
               "core/research_strategies/institutional_vwap.py so both systems read the "
               "same bar identically: 09:30 ET anchored VWAP, volume-weighted 2-sigma "
               "pierce-and-reject between 10:00 and 15:30, target VWAP, stop 2.5 sigma, "
               "incoherent geometry declined. NOT BACKTESTED in either project - it is "
               "an execution benchmark and its value is the reference level, not a "
               "measured directional edge. Traded-volume series only; US30 abstains "
               "unless its bars carry traded volume (the cash index does not)."),
        params={"anchor": "ny_rth"},
    ),

    "institutional_vwap_london": Registration(
        strategy=InstitutionalVWAPStrategy,
        deployment=Deployment.OBSERVER,
        instruments=("XAUUSD", "EURUSD", "GBPUSD", "USDJPY"),
        consensus_weight=0.0,
        basis=("UNTESTED VARIANT, observer only. The same pierce-and-reject rule "
               "anchored at 08:00 Europe/London. The source module never ran a London "
               "anchor, so this is a new hypothesis rather than a deployment. Bars are "
               "the CME tape (GC, 6E, 6B) shifted onto TradingView spot, because spot "
               "has no traded volume; USDJPY has no same-orientation contract (6J is "
               "the reciprocal) and abstains."),
        params={"anchor": "london"},
    ),

    "cme_rebal_flow": Registration(
        strategy=CMERebalFlowStrategy,
        deployment=Deployment.LIVE,
        instruments=("ES", "YM", "RTY", "MES", "MYM", "M2K", "SPY", "DIA", "IWM"),
        consensus_weight=0.7,
        excludes=("turn_of_month",),
        basis=("CME_REBAL_FLOW_01, CANDIDATE. Edge +30.06 bp per event, 95% CI "
               "[+1.89, +58.23], net t +2.34, z +2.63 against a 1,000-draw "
               "sign-permutation null, mid-month placebo dissociates by 57.9 bp. Gate 4 "
               "fails on one era (2020-23, t -0.24). Validated on ES/YM/RTY 2010-2023 and "
               "368 SPY months; deployed on those indices, their micros and the ETFs on "
               "the same index (DIA, IWM). Registered rule only: z from the 5th-to-last "
               "session close, no threshold, entry at the 4th-to-last open, exit at "
               "month-end settlement, NO stop and NO target. K from the published "
               "exchange calendar. Equity leg only - the bond leg is not modelled."),
    ),

    "cme_rebal_flow_nasdaq": Registration(
        strategy=CMERebalFlowStrategy,
        deployment=Deployment.OBSERVER,
        instruments=("QQQ", "NQ", "MNQ"),
        consensus_weight=0.0,
        basis=("Observer only. The Nasdaq-100 was never in the CME_REBAL_FLOW_01 panel "
               "(ES, YM, RTY, SPY), so a vote here would extend a measured result to an "
               "unmeasured index. Forward-tracked for a future pre-registration."),
    ),

    "ten_am_macro": Registration(
        strategy=TenAMMacroStrategy,
        deployment=Deployment.OBSERVER,
        instruments=("SPY", "QQQ", "US30", "ES", "NQ", "EURUSD", "GBPUSD", "XAUUSD"),
        consensus_weight=0.0,
        basis=("OBSERVE in Institutional Edge: no backtest, no control, no cost model. "
               "Mechanism checks only (anchor lands on 10:00 ET across DST, causal on "
               "99,000 XAUUSD M5 bars, one setup per session, R:R floor honoured). Rule "
               "is the source module's defaults on M5 bars. Forward data only."),
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

    "vpa_smc": Registration(
        strategy=VPASMCStrategy,
        deployment=Deployment.GATED,
        instruments=("EURUSD", "GBPUSD"),
        consensus_weight=0.0,
        basis=("Refuted on FX M15, unconditioned AND macro-conditioned. 1,761 "
               "trades over EURUSD primary and GBPUSD validation, 99,000 M15 "
               "bars each 2022-2026, six cells, using the engine's own "
               "structural SL/TP. All six negative unconditioned (-0.065 to "
               "-0.171R) with Welch negative in every cell - it loses to a "
               "bias-matched random entry - and both legs negative throughout. "
               "Conditioning on Fed policy epochs (hiking->short only, "
               "cutting->long only, hold->no permission) makes it WORSE in 5 "
               "of 6. Against 1,000 circular block permutations of the epoch "
               "labels, p ranges 0.399-0.911 and the true labelling does worse "
               "than the median random rotation in 5 of 6 cells. THE NULL "
               "DISTRIBUTION IS THE LASTING RESULT: a meaningless rotated "
               "regime yields positive conditioned expectancy ~33% of the time "
               "and reaches +0.203R at best, which is exactly the magnitude a "
               "macro-conditioning study reports as a discovery - so any "
               "conditioned figure without this null is uninterpretable. SCOPE: "
               "this conditions a strategy with no edge, and no filter turns "
               "nothing into something; it does not refute Tier 1 conditioning "
               "in general. A fair test of that thesis needs a base signal with "
               "a measurable edge, i.e. meanrev H4. Structural note: the "
               "adapter checks continuation breakout BEFORE the CRS score, so "
               "continuation share runs 21%/79%/99% across crs_min 6/7/8 and "
               "the threshold barely binds. Window fixed at 600 bars to make "
               "the engine's O(history) continuation loop O(600); validated at "
               "119/119 signal agreement against a 1500-bar window on both "
               "pairs."),
    ),

    "wmr_month_end": Registration(
        strategy=WMRMonthEndStrategy,
        deployment=Deployment.OBSERVER,
        instruments=("GBPUSD",),
        consensus_weight=0.0,
        basis=(
            "Mechanism established, execution not. London 16:00 WMR month-end equ"
            "ity-rebalancing flow (Melvin and Prins 2015), GBPUSD H1 primary / EU"
            "RUSD validation, 2010-2026, 167 strict month-ends. Independently rep"
            "licated: fix-hour beta +192.6 (t +3.31, r +0.249), pre-fix +51.1, po"
            "st-fix INVERTS to -71.1 (t -1.84), ambient non-month-end placebo +52"
            ".4 on n=3,970. The surge-and-invert across the fix is the strongest "
            "single piece of evidence in the programme - the shape a non-discreti"
            "onary flow exhausting at a benchmark should make. EURUSD is flat (t "
            "-0.41), consistent with Euro-area funds using the ECB 14:15 CET fix."
            " FIRST candidate filed with an a priori power calculation (sigma 15."
            "5 pips, N=192 detects r >= 0.120). LIMITS: carried by about 10 month"
            "s - dropping the 10 largest |SPY| takes t from +3.31 to +1.10, one o"
            "f the five most extreme months has the WRONG sign, and Spearman is +"
            "0.173 (t +2.26) against Pearson +0.249. The sign strategy nets +2.98"
            " pips at t +1.17 against a pre-registered 1.65, Era 1 is NEGATIVE (-"
            "1.13), and the 1.30-pip toll is about 40% of the effect. Promotion c"
            "ontract is outlier-proof by design: positive MEDIAN net AND positive"
            " Spearman over 24 forward month-ends, logged in macro_state_audit.js"
            "onl. PORTFOLIO: combined equal-risk with meanrev EURUSD H4 and tsmom"
            " XAUUSD H1 the three are effectively uncorrelated (mean |rho| 0.053,"
            " every pair within one SE of zero) and reach t +2.76 at annualised S"
            "harpe 0.69 over 191 months - the first figure here to clear anything"
            ". In-sample, and it inherits the selection of all three components. "
            "At the risk level where max drawdown fits a 10% prop limit the portf"
            "olio returns about 3% a year, and its longest drawdown is 63 months."
        ),
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

    "tsmom": Registration(
        strategy=TSMomentumStrategy,
        deployment=Deployment.GATED,
        instruments=("XAUUSD", "USDJPY"),
        consensus_weight=0.0,
        basis=("Underpowered on gold, refuted on the validation instrument. 12 "
               "cells over XAUUSD and USDJPY H1, 16-17 years. No cell passes; "
               "best is 2 of 5. XAUUSD at lookback 480 with the trailing-band "
               "exit nets +0.310R on n=200 and PASSES directional symmetry "
               "with its SHORT leg ahead of its long (+0.431R vs +0.194R) "
               "across a +322% gold market - the cleanest beta acquittal in "
               "the programme, since a trend follower on a tripling asset "
               "would normally be pure long beta. Retention +2.07 and a "
               "stationary block bootstrap gives P(mean<=0)=0.042, short of "
               "the 12-cell Bonferroni bar of 0.004. It fails OOS (t +1.05 on "
               "40 trades vs 2.96), modern third (t +1.12) and control (Welch "
               "+1.43). CONCENTRATION IS THE REAL LIMIT: median trade -0.401R, "
               "skew +6.11, and the top 5% of trades carry 174% of the profit "
               "- remove the best ten of two hundred and it is negative. That "
               "is the accepted shape of a trend payoff rather than a defect, "
               "but it means the effective sample is nearer ten than two "
               "hundred and no choice of statistic repairs it. USDJPY fails "
               "outright: its largest cell (+0.748R) is long +1.825R against "
               "short -0.329R on a pair that went 84 to 154, with OOS t -3.27 "
               "and retention -4.90 - a carry position with a momentum label, "
               "caught by the symmetry gate. SPEC DEFECT: the filed momentum-"
               "flip exit holds a median of 3-5 bars against the band exit's "
               "208-285, because entry fires at the zero crossing where the "
               "sign is unstable; half the grid was not testing time-series "
               "momentum. Promotion needs more INSTRUMENTS, not more "
               "parameters - the published result is cross-sectional over 58 "
               "futures because no single market supplies enough independent "
               "trends. CANDIDATE 20 RAN THAT TEST AND IT FAILED. Identical "
               "LB480 band logic across ten macro instruments, 2,135 trades "
               "2009-2026, pools to -0.016R at naive t -0.41 and Welch +0.03; "
               "1 of 5 gates, and the one it passes (retention +2.16) is "
               "meaningless on a negative mean. Effective breadth was measured "
               "first: N_eff 3.75 against a nominal 10, top eigenvalue 45% of "
               "variance, mean |rho| 0.39 - and for a trend follower the sign "
               "does not help, since long EURUSD and short USDCHF at -0.66 is "
               "one bet twice. If the gold effect were general the pooled t "
               "would have been ~+2.83; it is -0.41. Four of ten are positive "
               "(gold, silver, AUD, NZD) but xauusd-xagusd correlate +0.78 and "
               "audusd-nzdusd +0.83, so that is two coupled pairs, not four "
               "successes, and selecting them is hindsight. Concentration did "
               "not improve with breadth either: in every grouping the top 5% "
               "of trades exceeds the entire profit and the other 95% is "
               "negative, because the losing tail scales with trade count just "
               "as the winning tail does. The commodity/risk-asset split is "
               "recorded as a hypothesis for a future pre-registration on an "
               "untested universe, not as a finding."),
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

    "decasteljau": Registration(
        strategy=DecasteljauStrategy,
        deployment=Deployment.GATED,
        instruments=("USDJPY", "EURJPY"),
        consensus_weight=0.0,
        basis=("Refuted on JPY H1. 12,796 trades over USDJPY primary and "
               "EURJPY validation, 99,000 H1 bars each 2010-2026, two modes "
               "and both pip conventions. Zero of five gates on all eight "
               "cells; best is +0.020R at t 0.57. Corrected, the realised win "
               "rate sits 0.2-1.7 points from arithmetic breakeven in every "
               "cell - fair odds, no edge - reproducing and explaining the "
               "engine's own recorded -0.009R at quality 60. FOUND AND FIXED A "
               "LIVE DEFECT: _calc_sl_tp hardcoded pip_size=0.0001 for all "
               "non-gold symbols, so max_sl_pips_fx=60 became a 0.006 cap on a "
               "pair with ATR ~0.15; the cap crushed every stop and the "
               "atr*0.3 floor restored it, pinning every JPY stop at 0.30*ATR "
               "with rr 3.33 regardless of mode, swing structure or "
               "sl_mult_override. USDJPY was live in the watchlist. Cost "
               "measured at -0.247R per trade (-1,967R over 7,977 trades) "
               "because that geometry needs a 23.1% win rate and gets 16-21%, "
               "stopping out on the ENTRY BAR in the median case - 79-84% "
               "stopped at a median hold of 1 bar, against 62-64% and 19-22 "
               "bars corrected. Patched in the live engine 2026-09-07. Fourth "
               "instance of the control-gate shadow artefact and the clearest: "
               "every broken cell posts a POSITIVE Welch (+0.58 to +1.63) "
               "while netting -0.198 to -0.312R, because the matched control "
               "is destroyed by the same 4-pip stop; Welch alone would have "
               "preferred the broken configuration, and the amended gate "
               "rejects all eight. Carry is not leaking in - long and short "
               "agree within a tenth of an R across a sample where USDJPY ran "
               "+83.5%. DOES NOT refute the M5 configuration the engine was "
               "written for: every lookback denominates in bars and means "
               "something different on H1. That remains unmeasured."),
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

    "consensus_9": Registration(
        strategy=Consensus9Strategy,
        deployment=Deployment.GATED,
        instruments=("EURUSD", "GBPUSD"),
        consensus_weight=0.0,
        basis=("Refuted on FX M15. 34,000 trades over EURUSD primary and "
               "GBPUSD validation, 99,000 bars each 2022-2026. All 16 testable "
               "cells negative, to t -6.94, longs and shorts negative in every "
               "one; best is -0.135R. GROSS is also negative in all eight "
               "checked (-0.032 to -0.068R), so the filed +2.00 prior is not a "
               "cost story - it was the best of 16 cells against a 2.96 bar "
               "and does not reproduce at full depth with the engine's own "
               "value-area levels. Inverting does not rescue it either: "
               "+0.067R gross against a 0.111R toll is -0.044R. Welch against "
               "a bias-matched control is negative in EVERY cell, to -2.41 - "
               "the reverse of the shadow artefact, it loses to a random entry "
               "with matched geometry. THE CONVICTION SCORE RUNS BACKWARDS: "
               "raising min_conviction 0.55 -> 0.62 is worse in 7 of 8 cells, "
               "the second engine to show this after decasteljau (quality>=70 "
               "at -0.167R vs >=60 at -0.009R). That matters more than either "
               "verdict, because a confidence score that inverts is worse than "
               "none - it is used to size. Half the filed grid was never "
               "testable: min_votes=3 gives 30-47 signals against 6,200, "
               "because correlation, macro and sentiment vote NEUTRAL on every "
               "bar and 3 concordant votes cannot come from an effective "
               "roster of 4. Those three agents read LIVE news and calendar "
               "state, never the bar timestamp, returning identical votes on "
               "2022 and 2026 bars - symbol= and symbol=None disagree on 0 of "
               "3,200 decisions across both pairs and all four threshold "
               "combos, at 10x the compute. A backtest validity problem, not a "
               "live defect: live those agents read current news for the "
               "current bar. But any historical figure for this engine is a "
               "four-specialist figure, not a nine-agent one. HARNESS TRAP: "
               "the frame must be lowercase ohlcv WITH a 'Date' column; a "
               "DatetimeIndex makes the technical agent vote SHORT at 0.90 "
               "confidence on a NaN RSI while three specialists abstain on a "
               "swallowed ValueError - prior scans should be checked for which "
               "frame they passed."),
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
        deployment=Deployment.OBSERVER,
        instruments=("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD", "USDCHF"),
        consensus_weight=0.0,
        # Observers are never counted, so emitting is safe; with the default
        # require_validation=True it abstained on every bar and the forward record
        # its own promotion criterion depends on could never accumulate.
        params={"require_validation": False},
        basis=("Forward demo tracking on EURUSD H4 (w=0.0). Does not pass "
               "re-calibrated live gates on three counts: (1) The OOS clustered "
               "t +1.69 measures an untradeable month-equal-weighted portfolio "
               "where quiet 1-trade months make +0.928R while active 4-trade "
               "months lose -0.239R; the causal per-trade naive OOS t is +1.20 "
               "(and 2021-2026 naive t is +0.77), both failing the 1.65 bar. "
               "(2) GBPUSD validation fails 4 of 5 gates: net +0.038R, Welch "
               "+0.94, short leg -0.019R (symmetry fail), OOS naive t +0.88. "
               "(3) EURUSD long leg is statistical noise (t +0.35); edge is "
               "short-only, and cross-asset pooling drops t from +1.53 to +1.23. "
               "PRE-REGISTERED PROMOTION CRITERION: n >= 40 forward demo trades "
               "on EURUSD H4 with Net E[R] >= +0.05R and the short leg still "
               "carrying it, logged point-in-time in macro_state_audit.jsonl. "
               "At ~24 trades/year this requires ~20 months of paper tracking. "
               "2026-09-13: forward-tracking widened to the seven G10 USD pairs for the "
               "record; promotion remains EURUSD-specific. A directive to set it LIVE at "
               "weight 0.5 was not applied because this criterion is unmet."),
    ),

    "postfix_reversion": Registration(
        strategy=PostFixReversionStrategy,
        deployment=Deployment.GATED,
        instruments=("EURUSD","GBPUSD","AUDUSD","NZDUSD","USDCAD","USDCHF"),
        consensus_weight=0.0,
        basis=(
            "Refuted, and the control is the whole result. Daily post-fix reversi"
            "on at the London 16:00 WMR fix, six USD pairs, 24,825 sessions 2010-"
            "2026 - 24.8x the month-end sample. The fix-hour beta is negative and"
            " significant on four pairs (EUR t -3.85, AUD -4.38, NZD -4.55, CHF -"
            "8.34), but bid-ask bounce makes EVERY adjacent hour-pair revert, so "
            "the pre-registered test was whether the fix hour beats the same pair"
            "'s other 23 hourly betas. It fails on all six: rank 4th to 15th of 2"
            "3, never below the 5th percentile. GBPUSD, the pair the month-end re"
            "sult was built on, has the WEAKEST fix-hour reversion of the six (be"
            "ta -0.0101, t -0.86, rank 15/23). The trade loses on every pair - gr"
            "oss +0.18 to +0.82 bp against a toll of 0.64 to 1.87 bp - out of sam"
            "ple and in both eras. REUSABLE FINDING: reversion concentrates in th"
            "in-liquidity hours (mean beta -0.0334 for 20:00-07:00 London vs -0.0"
            "159 for 08:00-19:00), with the extremes at 22:00-23:00 and 01:00-02:"
            "00. Anyone measuring short-horizon FX mean reversion without an hour"
            "-of-day control will find a large effect that is entirely a spread a"
            "rtefact. The usdchf 09->10 cell at t -43.36 needs a data-quality che"
            "ck before it is treated as anything. This does NOT overturn the mont"
            "h-end finding, which regressed the post-fix hour on the SPY MONTH re"
            "turn - a conditional and different quantity. First candidate in the "
            "programme where cost, not statistical power, was the binding constra"
            "int."
        ),
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
