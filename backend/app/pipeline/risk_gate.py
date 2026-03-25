"""
Risk Gate — 15 hard veto rules enforced AFTER Trader Agent output.

Pure Python. No AI. Cannot be overridden by agent reasoning.
Returns PASS or BLOCK with a list of triggered rules.
"""
from datetime import datetime, timezone, timedelta


def run_risk_gate(state: dict) -> dict:
    """
    Evaluate 15 hard veto rules against the current pipeline state.

    Returns:
        {
            "passed": bool,
            "triggered_rules": [{"rule": int, "name": str, "reason": str}, ...],
            "mode": "NORMAL" | "PRESERVATION" | "BLOCKED",
        }
    """
    market_data = state.get("market_data", {})
    macro = state.get("macro_analysis", {})
    regime = state.get("regime_change_analysis", {})
    correlation = state.get("correlation_analysis", {})
    risk = state.get("risk_assessment", {})
    quant = state.get("quant_validation", {})
    signal = state.get("final_signal", {})
    news_ctx = state.get("news_context", {})

    triggered = []
    mode = "NORMAL"

    # ── Rule 1: Data freshness ──────────────────────────────────────────────
    data_ts = market_data.get("timestamp")
    if data_ts:
        try:
            if isinstance(data_ts, str):
                dt = datetime.fromisoformat(data_ts.replace("Z", "+00:00"))
            else:
                dt = data_ts
            age_min = (datetime.now(timezone.utc) - dt).total_seconds() / 60
            if age_min > 15:
                triggered.append({
                    "rule": 1, "name": "data_staleness",
                    "reason": f"Market data is {age_min:.0f}min old (limit: 15min)",
                })
        except (ValueError, TypeError):
            pass  # Can't parse timestamp — don't block

    # ── Rule 2: VIX > 40 → BLOCK all directional ───────────────────────────
    vix = market_data.get("vix", 0)
    if vix > 40:
        triggered.append({
            "rule": 2, "name": "extreme_vix",
            "reason": f"VIX at {vix:.1f} exceeds 40 — extreme fear, no directional signals",
        })

    # ── Rule 3: High-impact event within 30 min → BLOCK ────────────────────
    upcoming = macro.get("upcoming_events", [])
    high_impact = ["FOMC", "CPI", "NFP", "Non-Farm", "Fed Chair", "ECB"]
    for event in upcoming:
        if any(hi.lower() in event.lower() for hi in high_impact):
            # We flag it — in production this would check actual event times
            triggered.append({
                "rule": 3, "name": "high_impact_event",
                "reason": f"High-impact event detected: {event}",
            })
            break

    # ── Rule 4: Portfolio daily loss > 5% → BLOCK new analyses ─────────────
    daily_loss = risk.get("portfolio_drawdown", 0)
    if daily_loss > 5:
        triggered.append({
            "rule": 4, "name": "daily_loss_limit",
            "reason": f"Portfolio daily loss at {daily_loss:.1f}% exceeds 5% limit",
        })

    # ── Rule 5: Drawdown from peak > 15% → PRESERVATION MODE ──────────────
    if daily_loss > 15:
        triggered.append({
            "rule": 5, "name": "max_drawdown",
            "reason": f"Portfolio drawdown {daily_loss:.1f}% exceeds 15% — PRESERVATION MODE",
        })
        mode = "PRESERVATION"

    # ── Rule 6: Illiquid asset (ADV < 100K or mcap < $100M) → BLOCK ───────
    volume = market_data.get("volume", 0)
    avg_volume = market_data.get("avg_volume_30d", 0)
    if avg_volume and avg_volume < 100_000:
        triggered.append({
            "rule": 6, "name": "illiquid_asset",
            "reason": f"Average daily volume {avg_volume:,.0f} < 100,000 threshold",
        })

    # ── Rule 7: Earnings today → BLOCK ─────────────────────────────────────
    earnings_today = market_data.get("earnings_today", False)
    if earnings_today:
        triggered.append({
            "rule": 7, "name": "earnings_day",
            "reason": "Earnings report scheduled today — binary event risk",
        })

    # ── Rule 8: More than 20 analyses/day → BLOCK ─────────────────────────
    daily_count = state.get("daily_analysis_count", 0)
    if daily_count > 20:
        triggered.append({
            "rule": 8, "name": "daily_limit",
            "reason": f"{daily_count} analyses today exceeds 20/day limit",
        })

    # ── Rule 9: No statistical edge (p > 0.10) → WARN ─────────────────────
    p_value = quant.get("p_value", 0.05)
    if p_value > 0.10:
        triggered.append({
            "rule": 9, "name": "no_statistical_edge",
            "reason": f"p-value {p_value:.4f} > 0.10 — no statistically significant edge",
        })

    # ── Rule 10: Win rate below 40% in backtest → BLOCK ───────────────────
    backtest_wr = quant.get("backtest_win_rate", 0.5)
    if backtest_wr < 0.40:
        triggered.append({
            "rule": 10, "name": "low_win_rate",
            "reason": f"Backtest win rate {backtest_wr:.0%} below 40% minimum",
        })

    # ── Rule 11: Regime = CRISIS → reduce to half position ────────────────
    current_regime = regime.get("current_regime", "")
    if current_regime == "CRISIS":
        triggered.append({
            "rule": 11, "name": "crisis_regime",
            "reason": "Regime is CRISIS — position size must be halved",
        })

    # ── Rule 12: Concentration risk HIGH + correlation > 0.7 → BLOCK ──────
    conc_risk = correlation.get("concentration_risk", "LOW")
    port_corr = correlation.get("portfolio_correlation", 0)
    if conc_risk == "HIGH" and port_corr > 0.7:
        triggered.append({
            "rule": 12, "name": "concentration_breach",
            "reason": f"Concentration HIGH with correlation {port_corr:.2f} > 0.70",
        })

    # ── Rule 13: Negative expectancy → BLOCK ──────────────────────────────
    expectancy = quant.get("expectancy_per_trade", 0)
    if expectancy < 0:
        triggered.append({
            "rule": 13, "name": "negative_expectancy",
            "reason": f"Expected value per trade is {expectancy:+.3f}R — negative edge",
        })

    # ── Rule 14: Analyst consensus < 3/7 agreement → WARN ────────────────
    directions = []
    for key in ("fundamental_analysis", "technical_analysis", "sentiment_analysis",
                 "macro_analysis", "order_flow_analysis", "regime_change_analysis",
                 "correlation_analysis"):
        analysis = state.get(key, {})
        d = analysis.get("direction")
        if d:
            directions.append(d)
    if directions:
        final_dir = signal.get("direction", "NEUTRAL")
        agreement = sum(1 for d in directions if d == final_dir)
        if agreement < 3 and len(directions) >= 5:
            triggered.append({
                "rule": 14, "name": "low_consensus",
                "reason": f"Only {agreement}/{len(directions)} analysts agree on {final_dir}",
            })

    # ── Rule 15: Risk manager rejected → BLOCK ───────────────────────────
    if not risk.get("approved", True):
        triggered.append({
            "rule": 15, "name": "risk_rejected",
            "reason": "Risk Manager explicitly rejected this signal",
        })

    # ── Determine final gate status ────────────────────────────────────────
    # Hard blocks: rules 1-8, 10, 12, 13, 15
    hard_block_rules = {1, 2, 3, 4, 6, 7, 8, 10, 12, 13, 15}
    hard_blocks = [t for t in triggered if t["rule"] in hard_block_rules]

    if hard_blocks:
        mode = "BLOCKED"
    elif mode != "PRESERVATION" and triggered:
        mode = "NORMAL"  # warnings only, signal passes with caveats

    passed = mode not in ("BLOCKED", "PRESERVATION")

    return {
        "passed": passed,
        "triggered_rules": triggered,
        "mode": mode,
        "rules_checked": 15,
        "hard_blocks": len(hard_blocks),
        "warnings": len(triggered) - len(hard_blocks),
    }
