"""
Session Risk Gate — 14 hard veto rules for Session Mode.
Pure Python. No AI. Cannot be overridden by agent reasoning.
"""


def run_session_risk_gate(state: dict) -> dict:
    timer = state.get("timer_analysis", {})
    market = state.get("market_data", {})
    risk = state.get("session_risk", {})
    trader = state.get("session_trader_signal", {})
    coach = state.get("coach_feedback", {})

    triggered = []
    mode = "NORMAL"
    direction = trader.get("direction", "NEUTRAL")

    # Rule 1: No kill zone active → BLOCK new entries
    if not timer.get("kill_zone_active", False) and direction != "NEUTRAL":
        triggered.append({"rule": 1, "name": "no_kill_zone",
            "reason": "No kill zone active — new entries blocked outside institutional hours"})

    # Rule 2: Kill zone closing (< 5 min) → BLOCK
    kz_remaining = timer.get("kill_zone_minutes_remaining", 999)
    if timer.get("kill_zone_active") and kz_remaining < 5 and direction != "NEUTRAL":
        triggered.append({"rule": 2, "name": "kill_zone_closing",
            "reason": f"Kill zone closing in {kz_remaining}min — no new entries"})

    # Rule 3: Session drawdown > 3% → BLOCKED
    session_dd = state.get("session_drawdown_pct", 0)
    if session_dd > 3:
        triggered.append({"rule": 3, "name": "session_max_drawdown",
            "reason": f"Session drawdown {session_dd:.1f}% exceeds 3% limit"})

    # Rule 4: Session drawdown > 1.5% → COOLDOWN
    if 1.5 < session_dd <= 3:
        triggered.append({"rule": 4, "name": "session_drawdown_warning",
            "reason": f"Session drawdown {session_dd:.1f}% — cooldown, halve sizes"})
        if mode == "NORMAL":
            mode = "COOLDOWN"

    # Rule 5: More than 10 trades → BLOCK
    trade_count = state.get("session_trade_count", 0)
    if trade_count >= 10:
        triggered.append({"rule": 5, "name": "overtrading",
            "reason": f"{trade_count} trades — overtrading limit reached"})

    # Rule 6: More than 5 trades → COOLDOWN
    if 5 < trade_count < 10:
        triggered.append({"rule": 6, "name": "overtrading_warning",
            "reason": f"{trade_count} trades — approaching limit, be selective"})
        if mode == "NORMAL":
            mode = "COOLDOWN"

    # Rule 7: VIX > 35 → BLOCK
    vix = market.get("vix", 0)
    if vix > 35:
        triggered.append({"rule": 7, "name": "session_extreme_vix",
            "reason": f"VIX at {vix:.1f} — too volatile for intraday"})

    # Rule 8: SessionRisk says STOP_TRADING → BLOCK
    if risk.get("recommended_action") == "STOP_TRADING":
        triggered.append({"rule": 8, "name": "risk_agent_stop",
            "reason": "Session Risk agent recommends stopping"})

    # Rule 9: Coach tilt severity >= 7 → BLOCK
    if coach.get("tilt_severity", 0) >= 7:
        triggered.append({"rule": 9, "name": "tilt_detected",
            "reason": f"Coach detected tilt (severity {coach.get('tilt_severity')}/10) — {coach.get('tilt_type', 'UNKNOWN')}"})

    # Rule 10: Coach recommends END_SESSION → BLOCK
    if coach.get("recommendation") == "END_SESSION":
        triggered.append({"rule": 10, "name": "coach_end_session",
            "reason": "Coach recommends ending session"})

    # Rule 11: Session > 4 hours → BLOCK
    elapsed = timer.get("session_elapsed_minutes", 0)
    if elapsed > 240:
        triggered.append({"rule": 11, "name": "session_too_long",
            "reason": f"Session running {elapsed}min (>4 hours) — fatigue risk"})

    # Rule 12: 3 consecutive losses → COOLDOWN
    trades = state.get("session_trades", [])
    if len(trades) >= 3:
        if all(t.get("result") == "LOSS" for t in trades[-3:]):
            triggered.append({"rule": 12, "name": "consecutive_losses",
                "reason": "3 consecutive losses — take a break"})
            if mode == "NORMAL":
                mode = "COOLDOWN"

    # Rule 13: Position size > 1.5% in COOLDOWN → BLOCK
    pos_size = trader.get("position_size_pct", 0)
    if mode == "COOLDOWN" and pos_size > 1.5:
        triggered.append({"rule": 13, "name": "cooldown_size_limit",
            "reason": f"Position size {pos_size:.1f}% too large for cooldown (max 1.5%)"})

    # Rule 14: Agent agreement < 2/5 → BLOCK
    if trader.get("agent_agreement", 5) < 2 and direction != "NEUTRAL":
        triggered.append({"rule": 14, "name": "low_session_consensus",
            "reason": f"Only {trader.get('agent_agreement', 0)}/5 agents agree"})

    # Determine final status
    hard_block_rules = {1, 2, 3, 5, 7, 8, 9, 10, 11, 14}
    hard_blocks = [t for t in triggered if t["rule"] in hard_block_rules]
    if hard_blocks:
        mode = "BLOCKED"

    return {
        "passed": mode != "BLOCKED",
        "triggered_rules": triggered,
        "mode": mode,
        "rules_checked": 14,
        "hard_blocks": len(hard_blocks),
        "warnings": len(triggered) - len(hard_blocks),
    }
