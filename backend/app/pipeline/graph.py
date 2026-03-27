"""
LangGraph DAG — 9-agent multi-agent signal pipeline.

Stage 1 (parallel): 7 analysts (Fundamental, Technical, Sentiment, Macro, OrderFlow, RegimeChange, Correlation)
Stage 2: Quant validation (reviews analyst outputs for statistical rigor)
Stage 3: Bull/Bear researcher debate
Stage 4: Trader Agent synthesizes final decision (Opus tier)
Stage 5: Risk Manager validates position sizing
Stage 6: Risk Gate — 15 hard veto rules (pure Python, no AI)
Stage 7: Fund Manager final approval & signal packaging
"""
import asyncio
import time
from langgraph.graph import StateGraph, END
from app.pipeline.state import TradingState
from app.agents.schema import AgentOutput
from app.agents.fundamental import FundamentalAnalyst
from app.agents.technical import TechnicalAnalyst
from app.agents.sentiment import SentimentAnalyst
from app.agents.macro import MacroAnalyst
from app.agents.order_flow import OrderFlowAnalyst
from app.agents.regime_change import RegimeChangeAnalyst
from app.agents.correlation import CorrelationAnalyst
from app.agents.quant import QuantAnalyst
from app.agents.risk_manager import RiskManager
from app.agents.trader import TraderAgent
from app.pipeline.risk_gate import run_risk_gate

# Instantiate agents (shared across requests — they are stateless)
_fundamental = FundamentalAnalyst()
_technical = TechnicalAnalyst()
_sentiment = SentimentAnalyst()
_macro = MacroAnalyst()
_order_flow = OrderFlowAnalyst()
_regime_change = RegimeChangeAnalyst()
_correlation = CorrelationAnalyst()
_quant = QuantAnalyst()
_risk = RiskManager()
_trader = TraderAgent()


# ─── Helper: wrap agent result with AgentOutput ─────────────────────────────

def _wrap(agent_name: str, result: dict, data_sources: list[str] | None = None) -> dict:
    """Convert raw agent dict into AgentOutput, then back to state dict."""
    return AgentOutput.from_analysis(agent_name, result, data_sources).to_state_dict()


# ─── Stage 1: Parallel analyst nodes ─────────────────────────────────────────

async def run_fundamental(state: TradingState) -> TradingState:
    result = await _fundamental.analyze(state)
    return {**state, "fundamental_analysis": _wrap("fundamental", result, ["earnings", "valuation"])}


async def run_technical(state: TradingState) -> TradingState:
    result = await _technical.analyze(state)
    return {**state, "technical_analysis": _wrap("technical", result, ["price_action", "indicators"])}


async def run_sentiment(state: TradingState) -> TradingState:
    result = await _sentiment.analyze(state)
    sources = ["live_news"] if result.get("_live_news") else ["estimated_news"]
    return {**state, "sentiment_analysis": _wrap("sentiment", result, sources)}


async def run_macro(state: TradingState) -> TradingState:
    result = await _macro.analyze(state)
    sources = ["live_macro"] if result.get("_live_news") else ["estimated_macro"]
    return {**state, "macro_analysis": _wrap("macro", result, sources)}


async def run_order_flow(state: TradingState) -> TradingState:
    result = await _order_flow.analyze(state)
    return {**state, "order_flow_analysis": _wrap("order_flow", result, ["volume", "vwap", "obv"])}


async def run_regime_change(state: TradingState) -> TradingState:
    result = await _regime_change.analyze(state)
    return {**state, "regime_change_analysis": _wrap("regime_change", result, ["vix", "credit_spreads"])}


async def run_correlation(state: TradingState) -> TradingState:
    result = await _correlation.analyze(state)
    return {**state, "correlation_analysis": _wrap("correlation", result, ["portfolio_corr"])}


# ─── Stage 2: Quant validation ──────────────────────────────────────────────

async def run_quant(state: TradingState) -> TradingState:
    result = await _quant.analyze(state)
    return {**state, "quant_validation": _wrap("quant", result, ["backtest", "statistics"])}


# ─── Stage 3: Bull / Bear debate ────────────────────────────────────────────

async def run_debate(state: TradingState) -> TradingState:
    """Build bull and bear cases from all 7 analyst outputs."""
    analysts = {
        "Fundamental": state.get("fundamental_analysis", {}),
        "Technical": state.get("technical_analysis", {}),
        "Sentiment": state.get("sentiment_analysis", {}),
        "Macro": state.get("macro_analysis", {}),
        "OrderFlow": state.get("order_flow_analysis", {}),
        "RegimeChange": state.get("regime_change_analysis", {}),
        "Correlation": state.get("correlation_analysis", {}),
    }

    ticker = state.get("ticker", "UNKNOWN")

    bull_points = []
    bear_points = []
    for name, analysis in analysts.items():
        direction = analysis.get("direction", "NEUTRAL")
        reasoning = analysis.get("reasoning", "")[:150]
        if direction == "LONG":
            bull_points.append(f"{name}: {reasoning}")
        elif direction == "SHORT":
            bear_points.append(f"{name}: {reasoning}")

    if not bull_points:
        bull_points = [f"Some analysts see relative value or mean-reversion opportunity in {ticker}."]
    if not bear_points:
        bear_points = [f"Valuation appears stretched or momentum is decelerating for {ticker}."]

    bull_case = " | ".join(bull_points)
    bear_case = " | ".join(bear_points)

    reasoning = state.get("reasoning_chain", [])
    reasoning.append(f"Bull researcher: {bull_case[:200]}")
    reasoning.append(f"Bear researcher: {bear_case[:200]}")

    # Inject quant validation summary
    quant = state.get("quant_validation", {})
    if quant.get("statistical_edge") is not None:
        edge_str = "CONFIRMED" if quant["statistical_edge"] else "NOT CONFIRMED"
        reasoning.append(
            f"Quant: statistical edge {edge_str} (p={quant.get('p_value', '?')}, "
            f"WR={quant.get('backtest_win_rate', '?'):.0%}, "
            f"Sharpe={quant.get('sharpe_estimate', '?')})"
        )

    # Inject top live headlines into reasoning chain
    news_ctx = state.get("news_context", {})
    if news_ctx.get("has_news"):
        top_hl = news_ctx.get("ticker_headlines", [])[:2] or news_ctx.get("market_headlines", [])[:2]
        for hl in top_hl:
            reasoning.append(f"Live intel: {hl[:180]}")
        sent = state.get("sentiment_analysis", {})
        for hl in sent.get("top_headlines", [])[:1]:
            reasoning.append(f"Sentiment driver: {hl[:180]}")
        macro = state.get("macro_analysis", {})
        for hl in macro.get("key_news_drivers", [])[:1]:
            reasoning.append(f"Macro driver: {hl[:180]}")

    return {**state, "bull_case": bull_case, "bear_case": bear_case, "reasoning_chain": reasoning}


# ─── Stage 4: Trader Agent ──────────────────────────────────────────────────

async def run_trader(state: TradingState) -> TradingState:
    signal = await _trader.analyze(state)
    reasoning = state.get("reasoning_chain", [])
    reasoning.extend(signal.get("reasoning_chain", []))
    return {**state, "final_signal": signal, "reasoning_chain": reasoning}


# ─── Stage 5: Risk Manager ──────────────────────────────────────────────────

async def run_risk(state: TradingState) -> TradingState:
    risk = await _risk.analyze(state)
    reasoning = state.get("reasoning_chain", [])
    reasoning.append(f"Risk Manager: {risk.get('reasoning', '')[:200]}")
    return {**state, "risk_assessment": risk, "reasoning_chain": reasoning}


# ─── Stage 6: Risk Gate (pure Python, no AI) ────────────────────────────────

async def run_risk_gate_stage(state: TradingState) -> TradingState:
    gate_result = run_risk_gate(state)
    reasoning = state.get("reasoning_chain", [])

    if gate_result["passed"]:
        reasoning.append(
            f"Risk Gate: PASSED ({gate_result['rules_checked']} rules checked, "
            f"{gate_result['warnings']} warnings)"
        )
    else:
        reasons = [t["reason"] for t in gate_result["triggered_rules"][:3]]
        reasoning.append(
            f"Risk Gate: {gate_result['mode']} — {'; '.join(reasons)}"
        )

    return {**state, "risk_gate_result": gate_result, "reasoning_chain": reasoning}


# ─── Stage 7: Fund Manager (final approval & signal packaging) ──────────────

async def run_fund_manager(state: TradingState) -> TradingState:
    signal = state.get("final_signal", {})
    risk = state.get("risk_assessment", {})
    gate = state.get("risk_gate_result", {})
    quant = state.get("quant_validation", {})
    correlation = state.get("correlation_analysis", {})

    # Apply risk manager's position size
    if risk.get("position_size_pct"):
        signal["position_size_pct"] = risk["position_size_pct"]

    # Apply Kelly adjustment from correlation analysis
    kelly_adj = correlation.get("kelly_adjustment", 1.0)
    if kelly_adj and kelly_adj != 1.0:
        signal["position_size_pct"] = round(
            signal.get("position_size_pct", 2.0) * kelly_adj, 2
        )

    # Apply Risk Gate results
    if not gate.get("passed", True):
        if gate.get("mode") == "BLOCKED":
            signal["position_size_pct"] = 0.0
            signal["status"] = "RISK_GATE_BLOCKED"
            signal["risk_gate_reasons"] = [
                t["reason"] for t in gate.get("triggered_rules", [])
            ]
        elif gate.get("mode") == "PRESERVATION":
            signal["position_size_pct"] = round(
                signal.get("position_size_pct", 0) * 0.25, 2
            )
            signal["status"] = "PRESERVATION_MODE"

    # Crisis regime → halve position
    regime = state.get("regime_change_analysis", {})
    if regime.get("current_regime") == "CRISIS" and signal.get("status") not in ("RISK_GATE_BLOCKED",):
        signal["position_size_pct"] = round(
            signal.get("position_size_pct", 0) * 0.5, 2
        )

    # If risk not approved, zero out
    if not risk.get("approved", True) and signal.get("status") != "RISK_GATE_BLOCKED":
        signal["position_size_pct"] = 0.0
        signal["status"] = "RISK_REJECTED"

    # Set default status and attach profile
    signal.setdefault("status", "APPROVED")
    signal["strategy_profile"] = state.get("strategy_profile", "balanced")

    # Attach attribution data from all agents
    signal["agent_attribution"] = _build_attribution(state)
    signal["quant_summary"] = {
        "statistical_edge": quant.get("statistical_edge"),
        "p_value": quant.get("p_value"),
        "backtest_win_rate": quant.get("backtest_win_rate"),
        "sharpe_estimate": quant.get("sharpe_estimate"),
    }
    signal["risk_gate"] = {
        "passed": gate.get("passed", True),
        "mode": gate.get("mode", "NORMAL"),
        "triggered_rules": gate.get("triggered_rules", []),
    }

    # Conviction tier (based on probability score, not raw confidence)
    prob = signal.get("probability_score") or signal.get("confidence_score") or signal.get("confidence") or 50
    conf = signal.get("confidence_score") or signal.get("confidence") or 50
    # Use the stronger of probability_score or confidence for conviction
    conviction_input = max(prob, conf)
    if conviction_input >= 75:
        signal["conviction_tier"] = "HIGH"
    elif conviction_input >= 60:
        signal["conviction_tier"] = "MODERATE"
    elif conviction_input >= 50:
        signal["conviction_tier"] = "LOW"
    else:
        signal["conviction_tier"] = "NEUTRAL"

    # Ensure probability fields are preserved from trader output
    for key in ("probability_score", "bullish_pct", "bearish_pct",
                "research_target", "invalidation_level", "risk_reward_ratio",
                "analytical_window", "bull_case", "bear_case"):
        signal.setdefault(key, None)

    reasoning = state.get("reasoning_chain", [])
    lean = "BULLISH" if prob >= 50 else "BEARISH"
    reasoning.append(
        f"Fund Manager: {signal['status']} "
        f"— {prob:.0f}% {lean}, position size {signal.get('position_size_pct', 0):.1f}% of equity. "
        f"Conviction: {signal.get('conviction_tier', 'N/A')}."
    )

    return {**state, "final_signal": signal, "reasoning_chain": reasoning}


def _build_attribution(state: TradingState) -> list[dict]:
    """Build per-agent attribution list for the signal card."""
    attribution = []
    agent_keys = [
        ("fundamental_analysis", "Fundamental"),
        ("technical_analysis", "Technical"),
        ("sentiment_analysis", "Sentiment"),
        ("macro_analysis", "Macro"),
        ("order_flow_analysis", "Order Flow"),
        ("regime_change_analysis", "Regime Change"),
        ("correlation_analysis", "Correlation"),
    ]
    for key, label in agent_keys:
        analysis = state.get(key, {})
        if analysis:
            attribution.append({
                "agent": label,
                "direction": analysis.get("direction", "NEUTRAL"),
                "confidence": analysis.get("confidence", 50),
                "bullish_contribution": analysis.get("bullish_contribution", 0),
                "bearish_contribution": analysis.get("bearish_contribution", 0),
                "reasoning": analysis.get("reasoning", "")[:200],
            })
    return attribution


# ─── Build the LangGraph DAG ──────────────────────────────────────────────

def _build_graph() -> StateGraph:
    g = StateGraph(TradingState)

    # Add nodes
    g.add_node("fundamental", run_fundamental)
    g.add_node("technical", run_technical)
    g.add_node("sentiment", run_sentiment)
    g.add_node("macro", run_macro)
    g.add_node("order_flow", run_order_flow)
    g.add_node("regime_change", run_regime_change)
    g.add_node("correlation", run_correlation)
    g.add_node("quant", run_quant)
    g.add_node("debate", run_debate)
    g.add_node("trader", run_trader)
    g.add_node("risk", run_risk)
    g.add_node("risk_gate", run_risk_gate_stage)
    g.add_node("fund_manager", run_fund_manager)

    # Stage 1: all 7 analysts → debate
    g.set_entry_point("fundamental")
    for node in ("fundamental", "technical", "sentiment", "macro",
                 "order_flow", "regime_change", "correlation"):
        g.add_edge(node, "debate")

    # Sequential stages
    g.add_edge("debate", "trader")
    g.add_edge("trader", "risk")
    g.add_edge("risk", "risk_gate")
    g.add_edge("risk_gate", "fund_manager")
    g.add_edge("fund_manager", END)

    return g


# ─── Public API ───────────────────────────────────────────────────────────

async def run_pipeline(ticker: str, asset_class: str = "stocks", timeframe: str = "1D", market_data: dict | None = None, profile: str = "balanced", user_id: str | None = None) -> TradingState:
    """
    Run the full 9-agent pipeline for a given ticker.
    Returns the completed TradingState with final_signal populated.
    """
    from app.data.market_data import fetch_market_data
    from app.services.news_context import get_news_context
    from app.profiles.manager import profile_manager

    # Fetch market data and live news context in parallel
    if market_data is None:
        market_data, news_ctx = await asyncio.gather(
            fetch_market_data(ticker, asset_class),
            get_news_context(ticker),
        )
    else:
        news_ctx = await get_news_context(ticker)

    # Build reasoning chain prefix describing news context quality
    reasoning_prefix = []
    if news_ctx.get("has_news"):
        n = news_ctx["article_count"]
        ticker_n = len(news_ctx.get("ticker_headlines", []))
        reasoning_prefix.append(
            f"News context: {n} live articles loaded "
            f"({ticker_n} direct {ticker} mentions, "
            f"avg sentiment {news_ctx['avg_sentiment']:+.2f}, "
            f"{news_ctx['positive_pct']:.0f}% bullish / {news_ctx['negative_pct']:.0f}% bearish)"
        )
        if news_ctx.get("crisis_headlines"):
            reasoning_prefix.append(
                f"CRISIS ALERT: {len(news_ctx['crisis_headlines'])} crisis articles detected — "
                f"elevated risk-off bias applied"
            )
        if news_ctx.get("ticker_headlines"):
            reasoning_prefix.append(
                f"Top {ticker} headline: {news_ctx['ticker_headlines'][0]}"
            )
    else:
        reasoning_prefix.append(
            "News context: scraper warming up — agents using estimated data"
        )

    # ── Memory Layer: retrieve user + agent memory ─────────────────────────
    memory_context = ""
    if user_id:
        try:
            from app.services.memory import memory_manager
            from app.config import settings
            if settings.memory_enabled:
                context_str = f"User analysing {ticker} ({asset_class}) on {timeframe} with {profile} profile"
                memory_context = memory_manager.build_memory_context(user_id, context_str)
                if memory_context:
                    reasoning_prefix.append(
                        f"Memory Layer: {len(memory_context.splitlines())} context lines injected from user history"
                    )
        except Exception as exc:
            import structlog
            structlog.get_logger().error("memory_retrieval_failed", error=str(exc))

    initial_state: TradingState = {
        "ticker":           ticker,
        "timeframe":        timeframe,
        "asset_class":      asset_class,
        "market_data":      market_data,
        "news_context":     news_ctx,
        "memory_context":   memory_context,
        "user_id":          user_id or "",
        "strategy_profile": profile,
        "reasoning_chain":  reasoning_prefix,
        "errors": [],
    }

    # ── Stage 1: Run all 7 analysts in parallel ─────────────────────────────
    t0 = time.monotonic()
    (fundamental_result, technical_result, sentiment_result, macro_result,
     order_flow_result, regime_change_result, correlation_result) = await asyncio.gather(
        _fundamental.analyze(initial_state),
        _technical.analyze(initial_state),
        _sentiment.analyze(initial_state),
        _macro.analyze(initial_state),
        _order_flow.analyze(initial_state),
        _regime_change.analyze(initial_state),
        _correlation.analyze(initial_state),
    )

    state_after_analysts: TradingState = {
        **initial_state,
        "fundamental_analysis":    _wrap("fundamental", fundamental_result, ["earnings", "valuation"]),
        "technical_analysis":      _wrap("technical", technical_result, ["price_action", "indicators"]),
        "sentiment_analysis":      _wrap("sentiment", sentiment_result,
                                         ["live_news"] if sentiment_result.get("_live_news") else ["estimated_news"]),
        "macro_analysis":          _wrap("macro", macro_result,
                                         ["live_macro"] if macro_result.get("_live_news") else ["estimated_macro"]),
        "order_flow_analysis":     _wrap("order_flow", order_flow_result, ["volume", "vwap", "obv"]),
        "regime_change_analysis":  _wrap("regime_change", regime_change_result, ["vix", "credit_spreads"]),
        "correlation_analysis":    _wrap("correlation", correlation_result, ["portfolio_corr"]),
    }

    # ── Apply strategy profile weight multipliers ───────────────────────────
    if profile != "balanced":
        analyst_keys = {
            "fundamental_analysis", "technical_analysis", "sentiment_analysis",
            "macro_analysis", "order_flow_analysis", "regime_change_analysis",
            "correlation_analysis",
        }
        analyst_data = {k: state_after_analysts[k] for k in analyst_keys if k in state_after_analysts}
        weighted = profile_manager.apply_weights(profile, analyst_data)
        state_after_analysts = {**state_after_analysts, **weighted}
        reasoning_prefix.append(f"Strategy profile: {profile.upper()} — analyst weights applied")

    # ── Stage 2: Quant validation ───────────────────────────────────────────
    quant_result = await _quant.analyze(state_after_analysts)
    state_after_quant: TradingState = {
        **state_after_analysts,
        "quant_validation": _wrap("quant", quant_result, ["backtest", "statistics"]),
    }

    # ── Stage 3-7: Sequential — debate → trader → risk → risk gate → fund manager
    state_after_debate = await run_debate(state_after_quant)
    state_after_trader = await run_trader(state_after_debate)
    state_after_risk = await run_risk(state_after_trader)
    state_after_gate = await run_risk_gate_stage(state_after_risk)
    final_state = await run_fund_manager(state_after_gate)

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    final_state["pipeline_latency_ms"] = elapsed_ms  # type: ignore[typeddict-unknown-key]

    return final_state
