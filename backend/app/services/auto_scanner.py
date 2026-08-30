"""
Auto-scanner — pure technical analysis screener.

Scans each user's configured symbols using RSI, EMA crossover, MACD, and
volume indicators. When confluence >= 70, generates a full Signal record
via the existing pipeline in force_fallback mode (Python rule-based, no AI
API calls).

Runs alongside the existing AI-powered scanner (scanner.py) as a separate,
zero-cost system. Signals are tagged with signal_mode="AUTO_SCAN" so the
frontend can distinguish them from manual AI analysis.
"""
import asyncio
from datetime import datetime, timedelta

import structlog

from app.data.market_data import fetch_market_data
from app.db.database import AsyncSessionLocal
from app.models.alert import ScannerConfig
from app.models.signal import Signal
from app.services.market_hours import market_status
from app.services.signal_resolver import window_to_hours
from sqlalchemy import select

log = structlog.get_logger()

# Measured, not guessed. scripts/backtest_screener.py, 3y of real daily bars over
# 20 liquid symbols, best geometry (tp 3.5 / sl 1.0 ATR, 10-bar hold):
#
#   threshold  trades  TP-win%  expectancy
#          65    1266    18.7%    +0.152R
#          70     498    25.1%    +0.325R   <- ship this
#          75     411    23.9%    +0.265R
#          85       0        -          -
CONFLUENCE_THRESHOLD = 70

# The screener's long side carries the whole edge; its short side loses money.
# Same run, threshold 70, split by direction:
#
#   LONG   263 trades  34.7% win  +0.701R  PF 2.37
#   SHORT  235 trades  15.1% win  -0.096R  PF 0.86
#
# Long-only also beats a long-only random-entry baseline by +0.377R per trade, and
# the edge holds in both out-of-sample halves (+0.370R / +0.201R) across 18 of 20
# symbols — so this is signal, not bull-market drift. The sample is a rising market
# though: re-run the backtest before enabling shorts on the strength of a bear tape.
AUTO_SCAN_LONG_ONLY = True


# ── Pure technical indicator calculations ────────────────────────────────────


def _compute_rsi(closes: list[float], period: int = 14) -> float:
    """Standard RSI(14) calculation. Returns 50.0 if insufficient data."""
    if len(closes) < period + 1:
        return 50.0

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    recent = deltas[-(period + 50):]  # use extra bars for smoothing

    gains = [d if d > 0 else 0.0 for d in recent]
    losses = [-d if d < 0 else 0.0 for d in recent]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _compute_ema(closes: list[float], period: int) -> list[float]:
    """Exponential moving average. Returns list same length as closes."""
    if not closes:
        return []
    multiplier = 2.0 / (period + 1)
    ema = [closes[0]]
    for price in closes[1:]:
        ema.append(price * multiplier + ema[-1] * (1.0 - multiplier))
    return ema


def _compute_macd(
    closes: list[float],
    fast: int = 12,
    slow: int = 26,
    signal_period: int = 9,
) -> tuple[float, float, float]:
    """MACD(12,26,9). Returns (macd_line, signal_line, histogram).

    Returns (0, 0, 0) if insufficient data.
    """
    if len(closes) < slow + signal_period:
        return 0.0, 0.0, 0.0

    ema_fast = _compute_ema(closes, fast)
    ema_slow = _compute_ema(closes, slow)

    macd_line_series = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line_series = _compute_ema(macd_line_series, signal_period)

    macd_val = macd_line_series[-1]
    signal_val = signal_line_series[-1]
    histogram = macd_val - signal_val

    return macd_val, signal_val, histogram


# ── Confluence scoring ───────────────────────────────────────────────────────


def _score_setup(data: dict) -> tuple[int, str, str]:
    """Score a symbol's technical setup. Returns (score, direction, summary).

    Score is 0-100 based on indicator confluence. Direction is LONG or SHORT.
    Summary is a human-readable description of which indicators fired.
    """
    closes = data.get("closes", [])
    highs = data.get("highs", [])
    lows = data.get("lows", [])

    if len(closes) < 30:
        return 0, "NEUTRAL", "Insufficient price history"

    current_price = closes[-1]

    rsi = _compute_rsi(closes)
    ema9 = _compute_ema(closes, 9)
    ema21 = _compute_ema(closes, 21)
    macd_line, signal_line, histogram = _compute_macd(closes)

    # Previous histogram for momentum check
    if len(closes) >= 36:
        _, _, prev_histogram = _compute_macd(closes[:-1])
    else:
        prev_histogram = histogram

    # Volume spike detection
    volumes = [data.get("volume", 0)]
    volume_ratio = data.get("volume_ratio", 1.0)
    has_volume_spike = volume_ratio >= 1.5

    # Price position within recent range
    recent_high = max(highs[-20:]) if len(highs) >= 20 else max(highs)
    recent_low = min(lows[-20:]) if len(lows) >= 20 else min(lows)
    price_range = recent_high - recent_low
    if price_range > 0:
        range_position = (current_price - recent_low) / price_range
    else:
        range_position = 0.5

    # Accumulate bullish and bearish scores independently
    bull_score = 0
    bear_score = 0
    signals_fired: list[str] = []

    # RSI
    if rsi < 30:
        bull_score += 20
        signals_fired.append(f"RSI oversold ({rsi:.0f})")
    elif rsi < 40:
        bull_score += 10
        signals_fired.append(f"RSI leaning bullish ({rsi:.0f})")
    elif rsi > 70:
        bear_score += 20
        signals_fired.append(f"RSI overbought ({rsi:.0f})")
    elif rsi > 60:
        bear_score += 10
        signals_fired.append(f"RSI leaning bearish ({rsi:.0f})")

    # EMA crossover
    ema9_val = ema9[-1]
    ema21_val = ema21[-1]
    if ema9_val > ema21_val:
        bull_score += 20
        signals_fired.append("EMA(9) > EMA(21)")
    else:
        bear_score += 20
        signals_fired.append("EMA(9) < EMA(21)")

    # MACD
    if macd_line > signal_line:
        bull_score += 15
        signals_fired.append("MACD bullish cross")
    else:
        bear_score += 15
        signals_fired.append("MACD bearish cross")

    # MACD histogram momentum
    if abs(histogram) > abs(prev_histogram):
        if histogram > 0:
            bull_score += 10
            signals_fired.append("MACD histogram expanding (bullish)")
        else:
            bear_score += 10
            signals_fired.append("MACD histogram expanding (bearish)")

    # Volume spike
    if has_volume_spike:
        # Volume confirms the dominant direction
        if bull_score > bear_score:
            bull_score += 15
        else:
            bear_score += 15
        signals_fired.append(f"Volume spike ({volume_ratio:.1f}x avg)")

    # Price vs EMA(21)
    if current_price > ema21_val:
        bull_score += 10
        signals_fired.append("Price above EMA(21)")
    else:
        bear_score += 10
        signals_fired.append("Price below EMA(21)")

    # Range position
    if range_position > 0.7:
        bull_score += 10
        signals_fired.append("Near range high")
    elif range_position < 0.3:
        bear_score += 10
        signals_fired.append("Near range low")

    # Final score is the dominant direction's score
    if bull_score >= bear_score:
        direction = "LONG"
        score = bull_score
    else:
        direction = "SHORT"
        score = bear_score

    summary = f"{direction} confluence {score}/100: " + ", ".join(signals_fired)
    return score, direction, summary


# ── Main auto-scan job ───────────────────────────────────────────────────────


async def _scan_symbol(ticker: str) -> tuple[int, str, str, dict] | None:
    """Fetch market data and score a single symbol. Returns None on failure."""
    if not market_status(ticker)["open"]:
        return None
    try:
        data = await fetch_market_data(ticker)
        score, direction, summary = _score_setup(data)
        return score, direction, summary, data
    except Exception as exc:
        log.warning("auto_scan_fetch_failed", ticker=ticker, error=str(exc))
        return None


async def _generate_signal_for_user(
    user_id: str,
    ticker: str,
    direction: str,
    confluence_score: int,
    summary: str,
) -> Signal | None:
    """Run the pipeline in fallback mode and persist a Signal record."""
    from app.pipeline.graph import run_pipeline

    try:
        state = await run_pipeline(
            ticker=ticker,
            force_fallback=True,
            user_id=user_id,
        )

        final = state.get("final_signal", {})
        if not final:
            log.warning("auto_scan_pipeline_empty", ticker=ticker)
            return None

        signal_direction = final.get("direction", direction)
        if signal_direction not in ("LONG", "SHORT"):
            signal_direction = direction

        # Build agent_votes and tag as AUTO_SCAN
        agent_votes = {}
        for key, label in [
            ("fundamental_analysis", "fundamental"),
            ("technical_analysis", "technical"),
            ("sentiment_analysis", "sentiment"),
            ("macro_analysis", "macro"),
            ("order_flow_analysis", "order_flow"),
            ("regime_change_analysis", "regime_change"),
            ("correlation_analysis", "correlation"),
        ]:
            analysis = state.get(key, {})
            agent_votes[label] = {
                "direction": analysis.get("direction"),
                "confidence": analysis.get("confidence"),
            }
        agent_votes["risk_approved"] = state.get("risk_assessment", {}).get("approved", True)
        agent_votes["quant_validated"] = state.get("quant_validation", {}).get("statistical_edge")
        agent_votes["signal_mode"] = "AUTO_SCAN"
        agent_votes["confluence_score"] = confluence_score
        agent_votes["auto_scan_summary"] = summary

        now = datetime.utcnow()
        signal = Signal(
            user_id=user_id,
            ticker=ticker,
            asset_class=final.get("asset_class", "stocks"),
            timeframe=final.get("timeframe", "1D"),
            direction=signal_direction,
            entry_price=final.get("entry_price", 0),
            stop_loss=final.get("stop_loss", 0),
            take_profit_1=final.get("take_profit_1", 0),
            take_profit_2=final.get("take_profit_2", 0),
            take_profit_3=final.get("take_profit_3", 0),
            confidence_score=final.get("confidence_score", 0),
            agent_votes=agent_votes,
            reasoning_chain=state.get("reasoning_chain", []),
            strategy_sources=final.get("strategy_sources", []),
            timeframe_levels=final.get("timeframe_levels", {}),
            status="ACTIVE",
            signal_mode="AUTO_SCAN",
            # Honour the thesis window. A hardcoded 24h gave a 3.5-ATR target
            # one day to be reached while the 1.5-ATR stop only needed a normal
            # session's range — the stop was reachable and the target was not,
            # so resolved signals were losses almost by construction.
            expiry_time=now + timedelta(hours=window_to_hours(final.get("analytical_window"))),
            probability_score=final.get("probability_score"),
            bullish_pct=final.get("bullish_pct"),
            bearish_pct=final.get("bearish_pct"),
            research_target=final.get("research_target"),
            invalidation_level=final.get("invalidation_level"),
            risk_reward_ratio=final.get("risk_reward_ratio"),
            analytical_window=final.get("analytical_window"),
            bull_case=final.get("bull_case"),
            bear_case=final.get("bear_case"),
            conviction_tier=final.get("conviction_tier"),
        )

        async with AsyncSessionLocal() as session:
            session.add(signal)
            await session.commit()
            await session.refresh(signal)

        return signal

    except Exception as exc:
        log.error("auto_scan_pipeline_failed", ticker=ticker, error=str(exc))
        return None


async def run_auto_scan_for_user(user_id: str, symbols: list[str]) -> list[dict]:
    """Scan symbols, generate signals where confluence is high enough.

    Returns list of result dicts (one per symbol that triggered).
    """
    from app.api.websocket import broadcast_signal

    results: list[dict] = []

    # Check for existing active (non-expired) signals to avoid duplicates
    now = datetime.utcnow()
    active_tickers: set[str] = set()
    async with AsyncSessionLocal() as session:
        existing = await session.execute(
            select(Signal.ticker)
            .where(Signal.user_id == user_id)
            .where(Signal.status == "ACTIVE")
            .where(Signal.expiry_time > now)
        )
        active_tickers = {row[0] for row in existing.all()}

    # Scan all symbols concurrently (lightweight -- just fetches data + math)
    scan_tasks = [_scan_symbol(sym) for sym in symbols]
    scan_results = await asyncio.gather(*scan_tasks, return_exceptions=True)

    for sym, result in zip(symbols, scan_results):
        if isinstance(result, Exception) or result is None:
            continue

        score, direction, summary, _data = result

        if not market_status(sym)["open"]:
            log.debug("auto_scan_market_closed", ticker=sym)
            continue

        if score < CONFLUENCE_THRESHOLD:
            log.debug("auto_scan_below_threshold", ticker=sym, score=score)
            continue

        if AUTO_SCAN_LONG_ONLY and direction != "LONG":
            log.debug("auto_scan_short_suppressed", ticker=sym, score=score)
            continue

        if sym in active_tickers:
            log.info("auto_scan_skip_active", ticker=sym, score=score)
            continue

        log.info("auto_scan_triggered", ticker=sym, score=score, direction=direction)

        signal = await _generate_signal_for_user(
            user_id=user_id,
            ticker=sym,
            direction=direction,
            confluence_score=score,
            summary=summary,
        )

        if signal:
            signal_dict = {
                "signal_id": str(signal.id),
                "ticker": signal.ticker,
                "direction": signal.direction,
                "confidence_score": signal.confidence_score,
                "entry_price": signal.entry_price,
                "stop_loss": signal.stop_loss,
                "signal_mode": "AUTO_SCAN",
                "confluence_score": score,
                "summary": summary,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            }
            results.append(signal_dict)

            try:
                await broadcast_signal(sym, {
                    **signal_dict,
                    "type": "auto_scan_signal",
                })
            except Exception as exc:
                log.warning("auto_scan_broadcast_failed", ticker=sym, error=str(exc))

    return results


async def auto_scan_job() -> None:
    """APScheduler entry point. Scans all enabled users' symbols."""
    now = datetime.utcnow()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ScannerConfig).where(ScannerConfig.enabled == True)  # noqa: E712
        )
        configs = result.scalars().all()

    if not configs:
        return

    log.info("auto_scan_job_start", configs=len(configs))

    for cfg in configs:
        symbols = cfg.symbols or []
        if not symbols:
            continue

        try:
            results = await run_auto_scan_for_user(cfg.user_id, symbols)
            if results:
                log.info(
                    "auto_scan_user_complete",
                    user_id=cfg.user_id,
                    symbols_scanned=len(symbols),
                    signals_generated=len(results),
                )
        except Exception as exc:
            log.error("auto_scan_user_failed", user_id=cfg.user_id, error=str(exc))
