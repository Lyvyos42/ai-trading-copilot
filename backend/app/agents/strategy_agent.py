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
other agent toward the middle.

EACH STRATEGY GETS THE BARS IT IS DEFINED ON

Month-end flow and overnight drift are daily strategies, meanrev is H4, the VWAP
and 10:00 rules are intraday. One interval cannot serve all of them, and feeding
a daily rule intraday bars answers a different question with the same code.
`evaluate_symbol_multi` hands every strategy the first interval it declares that
is present, and abstains - with the reason - when none is.

BARS COME FROM TRADINGVIEW ONLY (app/data/tv_bars.py). No other vendor is
substituted when TradingView cannot answer; the affected strategies abstain.

NO BROKER. Nothing here imports an execution venue, an account, a lot size or a
margin model. The output is direction, conviction and price geometry.
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional, Sequence

import structlog

from app.strategies import registry
from app.strategies.base import BarSeries, Direction, SignalResult
from app.strategies.evidence_snapshot import for_strategy

log = structlog.get_logger()

# Display names used in strategy_sources and the reasoning chain.
LABELS = {
    "cme_rebal_flow": "CME Rebalance Flow (Mandated)",
    "cme_rebal_flow_nasdaq": "CME Rebalance Flow - Nasdaq (observer)",
    "institutional_vwap": "Institutional VWAP Reversion",
    "institutional_vwap_london": "Institutional VWAP Reversion - London anchor (observer)",
    "overnight_drift": "Overnight Equity Risk Premium Drift",
    "ten_am_macro": "10:00 ET Macro Sweep Reversal (observer)",
    "meanrev": "H4 Extension Mean Reversion (observer)",
}

# The holding horizon each rule is defined by, stated in its own unit.
HORIZONS = {
    "cme_rebal_flow": "4-SESSION",
    "cme_rebal_flow_nasdaq": "4-SESSION",
    "institutional_vwap": "INTRADAY",
    "institutional_vwap_london": "INTRADAY",
    "overnight_drift": "OVERNIGHT",
    "ten_am_macro": "INTRADAY (to 16:00 ET)",
    "meanrev": "8-DAY (48 H4 bars)",
}

_INTERVAL_ALIASES = {
    "1d": ("1d", "1day", "D1", "daily"),
    "4h": ("4h", "H4", "240m"),
}


def label(name: str) -> str:
    return LABELS.get(name, name)


def _vote_confidence(result: SignalResult, weight: float) -> float:
    """Confidence a live strategy contributes, scaled by its registered weight.

    The strategy's own conviction is a size hint on its own terms; the weight
    is how much this project trusts the strategy. Multiplying keeps the two
    judgements separate and visible.
    """
    return max(0.0, min(1.0, result.conviction)) * max(0.0, weight)


def _canonical(interval: str) -> str:
    for canon, aliases in _INTERVAL_ALIASES.items():
        if interval in aliases:
            return canon
    return interval


def _pick_bars(strategy_intervals: Sequence[str],
               bars_by_interval: dict[str, BarSeries]) -> Optional[BarSeries]:
    if not strategy_intervals:
        # A strategy that declares no interval takes the finest bars supplied.
        for iv in ("1m", "5m", "15m", "30m", "1h", "4h", "1d"):
            if iv in bars_by_interval:
                return bars_by_interval[iv]
        return next(iter(bars_by_interval.values()), None)
    for iv in strategy_intervals:
        b = bars_by_interval.get(_canonical(iv)) or bars_by_interval.get(iv)
        if b is not None:
            return b
    return None


def _run(name: str, reg, bars: BarSeries) -> SignalResult:
    return registry.build(name).generate_signals(bars)


def _evaluate(symbol: str, choose) -> dict[str, Any]:
    votes: list[tuple[str, float]] = []
    contributions: list[dict] = []
    observations: list[dict] = []
    abstentions: list[dict] = []

    for name, reg in registry.live(symbol):
        bars, why = choose(name)
        if bars is None:
            abstentions.append({"strategy": name, "label": label(name), "reason": why})
            continue
        try:
            result = _run(name, reg, bars)
        except Exception as exc:
            log.warning("strategy_failed", strategy=name, symbol=symbol,
                        error=f"{type(exc).__name__}: {exc}")
            abstentions.append({"strategy": name, "label": label(name), "reason":
                                f"raised {type(exc).__name__}: {exc}"})
            continue

        base = {**result.to_dict(), "registration": name, "label": label(name),
                "horizon": HORIZONS.get(name), "consensus_weight": reg.consensus_weight,
                "deployment": "live", "interval": bars.interval, "bars_source": bars.source,
                "evidence_record": for_strategy(result.strategy)}
        if result.abstained:
            abstentions.append({"strategy": name, "label": label(name), "reason": result.reason})
            continue
        if result.direction is Direction.FLAT:
            contributions.append({**base, "counted": False})
            continue

        conf = _vote_confidence(result, reg.consensus_weight)
        if conf <= 0:
            contributions.append({**base, "counted": False})
            continue

        votes.append((result.direction.value, conf))
        contributions.append({**base, "vote_confidence": round(conf, 4), "counted": True})

    for name, reg in registry.observers(symbol):
        bars, why = choose(name)
        if bars is None:
            observations.append({"strategy": name, "registration": name, "label": label(name),
                                 "abstained": True, "reason": why, "direction": "FLAT",
                                 "consensus_weight": 0.0, "counted": False,
                                 "deployment": "observer", "basis": reg.basis})
            continue
        try:
            result = _run(name, reg, bars)
        except Exception as exc:
            log.warning("observer_failed", strategy=name, symbol=symbol,
                        error=f"{type(exc).__name__}: {exc}")
            continue
        # Recorded whatever it says, including FLAT and abstain. The point of
        # an observer is the record, and a record with the quiet days removed
        # would overstate how often it has an opinion.
        observations.append({
            **result.to_dict(),
            "registration": name,
            "label": label(name),
            "horizon": HORIZONS.get(name),
            "consensus_weight": 0.0,
            "counted": False,
            "deployment": "observer",
            "interval": bars.interval,
            "bars_source": bars.source,
            "basis": reg.basis,
            "evidence_record": for_strategy(result.strategy),
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


def evaluate_symbol(symbol: str, bars: BarSeries) -> dict[str, Any]:
    """Run every registered strategy that applies to `symbol` on ONE series.

    Strategies defined on another interval abstain through their own interval
    check, which is the correct outcome rather than a reason to pass wrong bars.
    """
    return _evaluate(symbol, lambda name: (bars, ""))


def evaluate_symbol_multi(symbol: str,
                          bars_by_interval: dict[str, BarSeries]) -> dict[str, Any]:
    """Run every applicable strategy on the interval it is defined on."""
    def choose(name):
        strat_cls = registry.REGISTRY[name].strategy
        b = _pick_bars(strat_cls.intervals, bars_by_interval)
        if b is None:
            want = "/".join(strat_cls.intervals) or "any"
            have = ", ".join(sorted(bars_by_interval)) or "none"
            return None, f"no {want} bars available (have: {have})"
        return b, ""
    return _evaluate(symbol, choose)


def merge_into_votes(existing: list[tuple[str, float]],
                     strategy_block: dict) -> list[tuple[str, float]]:
    """Append the LIVE strategy votes to the agent tally.

    Only `votes` is read. `observations` is deliberately not reachable from
    here: there is no argument this function could be passed that would make
    an observer count.
    """
    return list(existing) + list(strategy_block.get("votes") or [])


# ─── Pipeline integration ────────────────────────────────────────────────────

def _registrations_for(symbol: str):
    return list(registry.live(symbol)) + list(registry.observers(symbol))


def needed_intervals(symbol: str) -> dict[str, bool]:
    """{interval: wants_traded_volume} for every strategy applicable to `symbol`."""
    from app.strategies.base import DataNeed
    out: dict[str, bool] = {}
    for _name, reg in _registrations_for(symbol):
        cls = reg.strategy
        ivs = cls.intervals or ("5m",)
        iv = _canonical(ivs[0])
        traded = DataNeed.TRADED_VOLUME in cls.requires
        out[iv] = out.get(iv, False) or traded
    return out


def bar_series_from_candles(symbol: str, interval: str, payload: dict,
                            asset_class: str = "stocks") -> BarSeries:
    c = payload.get("candles") or []
    return BarSeries(
        symbol=symbol, interval=interval,
        time=[int(x["time"]) for x in c],
        open=[float(x["open"]) for x in c], high=[float(x["high"]) for x in c],
        low=[float(x["low"]) for x in c], close=[float(x["close"]) for x in c],
        volume=[float(x.get("volume") or 0.0) for x in c],
        volume_kind=payload.get("volume_kind", "none"),
        is_continuous=asset_class in ("fx", "crypto"),
        source=payload.get("source", "unknown"),
    )


async def load_bars(symbol: str, asset_class: str, market_data: dict | None,
                    timeout_s: float = 20.0) -> tuple[dict[str, BarSeries], list[dict]]:
    """TradingView bars for every interval the applicable strategies need.

    `market_data["bars_by_interval"]`, when present, is used as-is - the injection
    seam for replay and tests - and nothing is fetched for those intervals.
    """
    from app.data import tv_bars

    need = needed_intervals(symbol)
    injected = (market_data or {}).get("bars_by_interval") or {}
    series: dict[str, BarSeries] = {}
    failures: list[dict] = []

    for iv, payload in injected.items():
        series[_canonical(iv)] = bar_series_from_candles(symbol, _canonical(iv), payload, asset_class)

    async def _one(iv: str, traded: bool):
        try:
            payload = await asyncio.wait_for(
                tv_bars.fetch_bars(symbol, iv, want_traded_volume=traded), timeout=timeout_s)
            return iv, payload, None
        except Exception as exc:
            return iv, None, f"{type(exc).__name__}: {exc}"

    todo = [(iv, traded) for iv, traded in need.items() if iv not in series]
    for iv, payload, err in await asyncio.gather(*(_one(iv, t) for iv, t in todo)):
        if payload is not None and payload.get("candles"):
            series[iv] = bar_series_from_candles(symbol, iv, payload, asset_class)
        else:
            failures.append({"interval": iv, "reason": err or "no candles"})
    return series, failures


async def evaluate_for_pipeline(ticker: str, asset_class: str,
                                market_data: dict | None) -> dict[str, Any]:
    """The pipeline node's work: load bars, evaluate, and summarise for the chain."""
    symbol = tv_bar_symbol(ticker)
    if not _registrations_for(symbol):
        return {"symbol": symbol, "votes": [], "contributions": [], "observations": [],
                "abstentions": [], "counted": 0, "abstained": 0, "bar_failures": [],
                "reasoning": []}
    series, failures = await load_bars(symbol, asset_class, market_data)
    block = evaluate_symbol_multi(symbol, series)
    block["bar_failures"] = failures
    block["reasoning"] = summarise(block)
    return block


def tv_bar_symbol(ticker: str) -> str:
    return (ticker or "").upper().replace("=F", "").replace("=X", "").replace("/", "").strip()


def summarise(block: dict) -> list[str]:
    """Pipeline-level lines only: what could NOT be evaluated and why.

    The per-strategy verdicts are written once, by the trader, next to the
    decision they fed - writing them here as well duplicated every line in the
    final reasoning chain.
    """
    lines = []
    n_abs = len(block.get("abstentions", []))
    if n_abs:
        lines.append(f"Quant strategies abstaining for lack of data: {n_abs} "
                     f"({'; '.join(a['strategy'] for a in block['abstentions'][:4])})")
    for f in block.get("bar_failures") or []:
        lines.append(f"TradingView bars unavailable for {f['interval']}: {f['reason'][:160]}")
    return lines
