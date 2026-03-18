"""
LangGraph DAG — 5-stage multi-agent signal pipeline.

Stage 1 (parallel): Fundamental + Technical + Sentiment + Macro analysts
Stage 2: Bull/Bear researcher debate
Stage 3: Trader Agent synthesizes final decision
Stage 4: Risk Manager validates
Stage 5: Fund Manager approves and builds final signal
"""
import asyncio
import time
from langgraph.graph import StateGraph, END
from app.pipeline.state import TradingState
from app.agents.fundamental import FundamentalAnalyst
from app.agents.technical import TechnicalAnalyst
from app.agents.sentiment import SentimentAnalyst
from app.agents.macro import MacroAnalyst
from app.agents.risk_manager import RiskManager
from app.agents.trader import TraderAgent

# Instantiate agents (shared across requests — they are stateless)
_fundamental = FundamentalAnalyst()
_technical = TechnicalAnalyst()
_sentiment = SentimentAnalyst()
_macro = MacroAnalyst()
_risk = RiskManager()
_trader = TraderAgent()


# ─── Stage 1: Parallel analyst nodes ─────────────────────────────────────────

async def run_fundamental(state: TradingState) -> TradingState:
    result = await _fundamental.analyze(state)
    return {**state, "fundamental_analysis": result}


async def run_technical(state: TradingState) -> TradingState:
    result = await _technical.analyze(state)
    return {**state, "technical_analysis": result}


async def run_sentiment(state: TradingState) -> TradingState:
    result = await _sentiment.analyze(state)
    return {**state, "sentiment_analysis": result}


async def run_macro(state: TradingState) -> TradingState:
    result = await _macro.analyze(state)
    return {**state, "macro_analysis": result}


# ─── Stage 2: Bull / Bear debate (sequential within, parallel possible) ───────

async def run_debate(state: TradingState) -> TradingState:
    """Two researcher agents form bull and bear cases from analyst outputs."""
    fund = state.get("fundamental_analysis", {})
    tech = state.get("technical_analysis", {})
    sent = state.get("sentiment_analysis", {})
    macro = state.get("macro_analysis", {})

    ticker = state.get("ticker", "UNKNOWN")

    # Build bull case from LONG signals
    bull_points = []
    if fund.get("direction") == "LONG":
        bull_points.append(f"Fundamentals: {fund.get('reasoning', '')[:150]}")
    if tech.get("direction") == "LONG":
        bull_points.append(f"Technical: {tech.get('reasoning', '')[:150]}")
    if sent.get("direction") == "LONG":
        bull_points.append(f"Sentiment: {sent.get('reasoning', '')[:150]}")
    if macro.get("macro_regime") == "RISK_ON":
        bull_points.append(f"Macro: {macro.get('reasoning', '')[:150]}")
    if not bull_points:
        bull_points = [f"Some analysts see relative value or mean-reversion opportunity in {ticker}."]

    # Build bear case from SHORT signals
    bear_points = []
    if fund.get("direction") == "SHORT":
        bear_points.append(f"Fundamentals: {fund.get('reasoning', '')[:150]}")
    if tech.get("direction") == "SHORT":
        bear_points.append(f"Technical: {tech.get('reasoning', '')[:150]}")
    if sent.get("direction") == "SHORT":
        bear_points.append(f"Sentiment: {sent.get('reasoning', '')[:150]}")
    if macro.get("macro_regime") == "RISK_OFF":
        bear_points.append(f"Macro: {macro.get('reasoning', '')[:150]}")
    if not bear_points:
        bear_points = [f"Valuation appears stretched or momentum is decelerating for {ticker}."]

    bull_case = " | ".join(bull_points)
    bear_case = " | ".join(bear_points)

    reasoning = state.get("reasoning_chain", [])
    reasoning.append(f"Bull researcher: {bull_case[:200]}")
    reasoning.append(f"Bear researcher: {bear_case[:200]}")

    # Inject top live headlines into reasoning chain for signal card display
    news_ctx = state.get("news_context", {})
    if news_ctx.get("has_news"):
        top_hl = news_ctx.get("ticker_headlines", [])[:2] or news_ctx.get("market_headlines", [])[:2]
        for hl in top_hl:
            reasoning.append(f"Live intel: {hl[:180]}")
        sent = state.get("sentiment_analysis", {})
        top_sent_hl = sent.get("top_headlines", [])[:1]
        for hl in top_sent_hl:
            reasoning.append(f"Sentiment driver: {hl[:180]}")
        macro = state.get("macro_analysis", {})
        top_macro_hl = macro.get("key_news_drivers", [])[:1]
        for hl in top_macro_hl:
            reasoning.append(f"Macro driver: {hl[:180]}")

    return {**state, "bull_case": bull_case, "bear_case": bear_case, "reasoning_chain": reasoning}


# ─── Stage 3: Trader Agent ────────────────────────────────────────────────────

async def run_trader(state: TradingState) -> TradingState:
    signal = await _trader.analyze(state)
    reasoning = state.get("reasoning_chain", [])
    reasoning.extend(signal.get("reasoning_chain", []))
    return {**state, "final_signal": signal, "reasoning_chain": reasoning}


# ─── Stage 4: Risk Manager ────────────────────────────────────────────────────

async def run_risk(state: TradingState) -> TradingState:
    risk = await _risk.analyze(state)
    reasoning = state.get("reasoning_chain", [])
    reasoning.append(f"Risk Manager: {risk.get('reasoning', '')[:200]}")
    return {**state, "risk_assessment": risk, "reasoning_chain": reasoning}


# ─── Stage 5: Fund Manager (final approval & signal packaging) ────────────────

async def run_fund_manager(state: TradingState) -> TradingState:
    signal = state.get("final_signal", {})
    risk = state.get("risk_assessment", {})

    # Override position size with risk manager's approved size
    if risk.get("position_size_pct"):
        signal["position_size_pct"] = risk["position_size_pct"]

    # If risk not approved, zero out size and flag
    if not risk.get("approved", True):
        signal["position_size_pct"] = 0.0
        signal["status"] = "RISK_REJECTED"

    reasoning = state.get("reasoning_chain", [])
    reasoning.append(
        f"Fund Manager: Signal {'APPROVED' if risk.get('approved', True) else 'REJECTED'} "
        f"— position size {signal.get('position_size_pct', 0):.1f}% of equity."
    )

    return {**state, "final_signal": signal, "reasoning_chain": reasoning}


# ─── Build the LangGraph DAG ──────────────────────────────────────────────────

def _build_graph() -> StateGraph:
    g = StateGraph(TradingState)

    # Add nodes
    g.add_node("fundamental", run_fundamental)
    g.add_node("technical", run_technical)
    g.add_node("sentiment", run_sentiment)
    g.add_node("macro", run_macro)
    g.add_node("debate", run_debate)
    g.add_node("trader", run_trader)
    g.add_node("risk", run_risk)
    g.add_node("fund_manager", run_fund_manager)

    # Stage 1: all analysts in parallel (LangGraph runs them concurrently)
    g.set_entry_point("fundamental")
    g.add_edge("fundamental", "debate")

    # We run technical, sentiment, macro as parallel branches too
    # LangGraph doesn't natively fan-out from a single entry point in v0.2
    # so we handle concurrency inside the run_analysts aggregator node
    g.add_edge("technical", "debate")
    g.add_edge("sentiment", "debate")
    g.add_edge("macro", "debate")

    # Sequential stages
    g.add_edge("debate", "trader")
    g.add_edge("trader", "risk")
    g.add_edge("risk", "fund_manager")
    g.add_edge("fund_manager", END)

    return g


# ─── Public API ───────────────────────────────────────────────────────────────

async def run_pipeline(ticker: str, asset_class: str = "stocks", timeframe: str = "1D", market_data: dict | None = None) -> TradingState:
    """
    Run the full multi-agent pipeline for a given ticker.
    Returns the completed TradingState with final_signal populated.
    """
    from app.data.market_data import fetch_market_data
    from app.services.news_context import get_news_context

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
                f"⚠ CRISIS ALERT: {len(news_ctx['crisis_headlines'])} crisis articles detected — "
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

    initial_state: TradingState = {
        "ticker":        ticker,
        "timeframe":     timeframe,
        "asset_class":   asset_class,
        "market_data":   market_data,
        "news_context":  news_ctx,
        "reasoning_chain": reasoning_prefix,
        "errors": [],
    }

    # Run all 4 analysts in parallel, then proceed through the DAG sequentially
    t0 = time.monotonic()
    fundamental_result, technical_result, sentiment_result, macro_result = await asyncio.gather(
        _fundamental.analyze(initial_state),
        _technical.analyze(initial_state),
        _sentiment.analyze(initial_state),
        _macro.analyze(initial_state),
    )

    state_after_analysts: TradingState = {
        **initial_state,
        "fundamental_analysis": fundamental_result,
        "technical_analysis": technical_result,
        "sentiment_analysis": sentiment_result,
        "macro_analysis": macro_result,
    }

    # Sequential: debate → trader → risk → fund manager
    state_after_debate = await run_debate(state_after_analysts)
    state_after_trader = await run_trader(state_after_debate)
    state_after_risk = await run_risk(state_after_trader)
    final_state = await run_fund_manager(state_after_risk)

    elapsed_ms = int((time.monotonic() - t0) * 1000)
    final_state["pipeline_latency_ms"] = elapsed_ms  # type: ignore[typeddict-unknown-key]

    return final_state
