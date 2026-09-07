"""Post-Earnings Announcement Drift, with a time-series SUE.

REFERENCES
Ball & Brown (1968); Bernard & Thomas (1989, 1990) for the drift itself;
Foster, Olsen & Shevlin (1984) for the time-series standardisation used here.

WHY NOT THE ANALYST-DISPERSION SUE

The textbook SUE is

    SUE = (actual EPS - consensus EPS) / stdev(analyst forecasts)

and the denominator is the problem. Forecast dispersion is I/B/E/S-class data.
Checked on 2026-09-06: Yahoo's quoteSummary endpoint, which used to carry
earningsTrend, now returns HTTP 401 behind a crumb, and the chart API exposes
no earnings events at all. No free source publishes per-analyst forecast
distributions, so that denominator cannot be computed here at any price the
project has agreed to pay.

THE SUBSTITUTE IS NOT A DEGRADED VERSION, IT IS THE ORIGINAL

Foster, Olsen & Shevlin standardise against the firm's OWN earnings history
rather than against analysts:

    expected_q  = EPS[q-4] + drift          (seasonal random walk)
    drift       = mean of the last K year-over-year changes
    SUE         = (EPS[q] - expected_q) / stdev(those changes)

It predates widespread analyst data and is what much of the original PEAD
literature actually used. It needs only historical actual quarterly EPS, which
Finnhub's free tier supplies. Where the two are both computable they rank
firms similarly; where they differ, this one is measuring surprise against the
firm's own seasonality rather than against a consensus that may itself be
stale.

WHAT THIS MODULE DOES NOT CLAIM

No backtest is attached. Unlike overnight_drift, which was measured over 8457
sessions before it was written, this ships unvalidated because the data to
validate it is not yet connected - FINNHUB_API_KEY is not set on this
deployment. Until a key exists and a study has run, `require_validation`
defaults to True and the screener abstains rather than emitting a signal whose
performance nobody here has checked.

The drift window is 1 to 60 calendar days after the announcement. Day 1 is the
opening drive; the documented drift runs for roughly a quarter and decays.
Outside that window the strategy has nothing to say and returns
NO_EARNINGS_DRIFT_ACTIVE, which is an abstention rather than a flat opinion.
"""
from __future__ import annotations

import math
import os
import statistics as st
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional, Sequence

import httpx

from app.strategies.base import (
    BarSeries, BaseStrategy, DataNeed, Direction, SignalResult,
)

FINNHUB_BASE = "https://finnhub.io/api/v1"

# Day 1 is the opening drive. Bernard & Thomas document drift persisting for
# about a quarter; past 60 days it is not distinguishable from noise here.
DRIFT_WINDOW_DAYS = (1, 60)
OPENING_DRIVE_DAYS = 1
MIN_HISTORY_QUARTERS = 8      # two years: enough for a seasonal difference series
# Historical variation below this fraction of the earnings level is too small
# to standardise against - see time_series_sue.
MIN_RELATIVE_SIGMA = 0.02


def expected_from(history, drift: float) -> float:
    """Seasonal random walk forecast for the latest quarter."""
    return history[-5].actual + drift


def finnhub_key() -> Optional[str]:
    return (os.getenv("FINNHUB_API_KEY") or "").strip() or None


@dataclass(frozen=True)
class EarningsQuarter:
    period: date
    actual: float
    estimate: Optional[float] = None
    surprise_pct: Optional[float] = None


@dataclass(frozen=True)
class SUEScore:
    sue: float
    actual: float
    expected: float
    sigma: float
    quarters_used: int
    method: str
    period: date

    def to_dict(self) -> dict[str, Any]:
        return {"sue": round(self.sue, 4), "actual": self.actual,
                "expected": round(self.expected, 4), "sigma": round(self.sigma, 6),
                "quarters_used": self.quarters_used, "method": self.method,
                "period": self.period.isoformat()}


def time_series_sue(history: Sequence[EarningsQuarter],
                    drift_window: int = 8) -> Optional[SUEScore]:
    """Foster/Olsen/Shevlin SUE from the firm's own quarterly EPS.

    `history` must be sorted oldest first and be the same fiscal quarters in
    order - a missing quarter shifts the seasonal lag and silently compares Q3
    against Q2. Callers get None rather than a number computed on a gap.
    """
    if len(history) < MIN_HISTORY_QUARTERS:
        return None

    # Year-over-year changes. The seasonal lag is 4 by construction, so this
    # requires quarterly - not annual, not semi-annual - reporting.
    deltas: list[float] = []
    for i in range(4, len(history)):
        deltas.append(history[i].actual - history[i - 4].actual)
    if len(deltas) < 4:
        return None

    latest = history[-1]
    prior_deltas = deltas[:-1][-drift_window:]
    if len(prior_deltas) < 3:
        return None

    drift = st.mean(prior_deltas)
    sigma = st.pstdev(prior_deltas)
    if sigma <= 0:
        # Perfectly regular earnings. A surprise cannot be standardised against
        # zero variance, and dividing by an epsilon would manufacture an
        # enormous SUE from a rounding difference.
        return None

    # The same failure one step short of zero. When the historical variation is
    # a rounding error next to the earnings level, the ratio is not a measure
    # of surprise, it is a measure of how quiet the past happened to be: a
    # sigma of 0.037 against EPS near 1.50 turns a 48 cent beat into SUE 13,
    # which would then be read as an extraordinary event. Standardisation
    # needs something to standardise against.
    scale = max(abs(latest.actual), abs(expected_from(history, drift)), 1e-9)
    if sigma / scale < MIN_RELATIVE_SIGMA:
        return None

    expected = expected_from(history, drift)
    return SUEScore(
        sue=(latest.actual - expected) / sigma,
        actual=latest.actual, expected=expected, sigma=sigma,
        quarters_used=len(prior_deltas), method="foster_olsen_shevlin_1984",
        period=latest.period,
    )


async def fetch_earnings_history(symbol: str,
                                 client: Optional[httpx.AsyncClient] = None
                                 ) -> list[EarningsQuarter]:
    """Actual quarterly EPS from Finnhub, oldest first.

    Free tier: 60 calls/minute. The caller is responsible for batching a
    screener run inside that.
    """
    key = finnhub_key()
    if not key:
        raise RuntimeError("FINNHUB_API_KEY not set")

    own = client is None
    client = client or httpx.AsyncClient(timeout=15.0)
    try:
        r = await client.get(f"{FINNHUB_BASE}/stock/earnings",
                             params={"symbol": symbol.upper(), "token": key})
        r.raise_for_status()
        rows = r.json() or []
    finally:
        if own:
            await client.aclose()

    out: list[EarningsQuarter] = []
    for row in rows:
        try:
            actual = row.get("actual")
            if actual is None:
                continue
            out.append(EarningsQuarter(
                period=datetime.strptime(row["period"], "%Y-%m-%d").date(),
                actual=float(actual),
                estimate=(float(row["estimate"]) if row.get("estimate") is not None else None),
                surprise_pct=(float(row["surprisePercent"])
                              if row.get("surprisePercent") is not None else None),
            ))
        except (KeyError, TypeError, ValueError):
            continue
    out.sort(key=lambda q: q.period)
    return out


class PEADTimeScreener(BaseStrategy):
    """Drift after an earnings surprise, scored by time-series SUE."""

    name = "pead_time_sue"
    requires = (DataNeed.OHLC, DataNeed.EARNINGS)
    validated_on = ()   # nothing yet - see the module docstring

    def __init__(self, sue_threshold: float = 1.0,
                 drift_window: tuple[int, int] = DRIFT_WINDOW_DAYS,
                 require_validation: bool = True):
        super().__init__(sue_threshold=sue_threshold,
                         drift_window=drift_window,
                         require_validation=require_validation)
        self.sue_threshold = sue_threshold
        self.drift_window = drift_window
        self.require_validation = require_validation

    def min_bars(self) -> int:
        return 30

    def evaluate_with_earnings(self, bars: BarSeries,
                               history: Sequence[EarningsQuarter],
                               as_of: Optional[date] = None) -> SignalResult:
        """The real entry point: bars alone cannot answer this question.

        generate_signals() abstains, because BaseStrategy's contract passes
        only bars and there is no honest way to infer an earnings surprise
        from a price series - inferring it from the price move would be
        reading the outcome and calling it the cause.
        """
        if self.require_validation:
            return SignalResult.abstain(
                self.name, bars.symbol,
                "PEAD_NOT_VALIDATED: no backtest has been run on this "
                "implementation. FINNHUB_API_KEY is unset, so no earnings "
                "history has been fetched and no study exists. Set the key, "
                "run the study, then set require_validation=False.")

        today = as_of or datetime.now(timezone.utc).date()

        if not history:
            return SignalResult.abstain(
                self.name, bars.symbol, "NO_EARNINGS_HISTORY")

        score = time_series_sue(history)
        if score is None:
            return SignalResult.abstain(
                self.name, bars.symbol,
                f"SUE_NOT_COMPUTABLE: needs {MIN_HISTORY_QUARTERS} consecutive "
                f"quarters with non-zero variance in year-over-year change; "
                f"have {len(history)}")

        days_since = (today - score.period).days
        lo, hi = self.drift_window
        evidence = {**score.to_dict(), "days_since_report": days_since,
                    "drift_window_days": [lo, hi]}

        if days_since < lo or days_since > hi:
            return SignalResult.abstain(
                self.name, bars.symbol,
                f"NO_EARNINGS_DRIFT_ACTIVE: {days_since} days since the last "
                f"report, outside the {lo}-{hi} day drift window")

        if abs(score.sue) < self.sue_threshold:
            return SignalResult(
                strategy=self.name, symbol=bars.symbol, direction=Direction.FLAT,
                reason=(f"SUE {score.sue:+.2f} inside the +/-{self.sue_threshold} "
                        f"band - the quarter was not a surprise"),
                evidence=evidence)

        direction = Direction.LONG if score.sue > 0 else Direction.SHORT
        phase = "opening_drive" if days_since <= OPENING_DRIVE_DAYS else "drift"

        # Conviction decays across the window. The drift is strongest
        # immediately after the report and is largely gone by the next one;
        # a flat conviction across 60 days would size the tail like the head.
        decay = max(0.0, 1.0 - (days_since - lo) / max(1.0, hi - lo))
        conviction = min(0.9, (0.35 + min(abs(score.sue), 4.0) * 0.12) * (0.5 + 0.5 * decay))

        return SignalResult(
            strategy=self.name, symbol=bars.symbol, direction=direction,
            conviction=conviction,
            entry=bars.close[-1],
            stop=None,       # a multi-week drift is not managed by a price stop
            target=None,
            horizon_bars=max(1, hi - days_since),
            reason=(f"SUE {score.sue:+.2f} ({score.method}), {days_since} days "
                    f"after {score.period.isoformat()} - {phase}"),
            evidence={**evidence, "phase": phase},
        )

    def _evaluate(self, bars: BarSeries) -> SignalResult:
        return SignalResult.abstain(
            self.name, bars.symbol,
            "PEAD needs earnings history; call evaluate_with_earnings() with "
            "the quarters from fetch_earnings_history()")


async def screen(symbols: Sequence[str], bars_by_symbol: dict[str, BarSeries],
                 sue_threshold: float = 1.0,
                 require_validation: bool = True,
                 as_of: Optional[date] = None) -> list[dict]:
    """Batch screener. Returns one row per symbol, abstentions included.

    Abstentions are returned rather than filtered out so the caller can see
    that a symbol was considered and why it produced nothing. A screener that
    silently drops them looks like it examined only the symbols it liked.
    """
    strat = PEADTimeScreener(sue_threshold=sue_threshold,
                             require_validation=require_validation)
    out: list[dict] = []
    if not finnhub_key():
        return [SignalResult.abstain(strat.name, s, "FINNHUB_API_KEY not set").to_dict()
                for s in symbols]

    async with httpx.AsyncClient(timeout=15.0) as client:
        for sym in symbols:
            bars = bars_by_symbol.get(sym)
            if bars is None:
                out.append(SignalResult.abstain(strat.name, sym, "no bars").to_dict())
                continue
            try:
                hist = await fetch_earnings_history(sym, client)
            except Exception as exc:
                out.append(SignalResult.abstain(
                    strat.name, sym, f"earnings fetch failed: "
                                     f"{type(exc).__name__}: {exc}").to_dict())
                continue
            out.append(strat.evaluate_with_earnings(bars, hist, as_of).to_dict())
    return out
